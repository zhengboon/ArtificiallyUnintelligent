"""Org-aligned Challenge-1 mapping mission (MAVSDK), modeled on the organiser's
official move_it4.py (2026-06-10) — the SOURCE OF TRUTH for the flight path.

The org sample flies the real drone with:
  - MAVSDK over ``serial:///dev/ttyS6:921600`` (MAVLink, NOT the XRCE path)
  - offboard ``set_position_velocity_ned`` (position target + velocity feed-forward)
  - UWB ``/uwb_tag`` for horizontal waypoint feedback (East=pose.x, North=pose.y)
  - per-waypoint ArUco (``DICT_7X7_1000``) + depth scan

This module reproduces that exactly (connect → arm → offboard → position-setpoint
takeoff → UWB-feedback velocity-profiled waypoint tracking → land) and adds what the
sample lacks: our judge-artifact pipeline (run_writer: landing_pads.json, top_down.png/npy,
markers, STATUS, run_summary), validity classification, sighting dedup, a CLI, safety
(land+disarm on exit/Ctrl-C, max flight time), and a --nofly ground mode.

On the drone (MAVSDK path needs NO XRCE agent; it does need /uwb_tag):
    source ~/ros2_ws/install/setup.bash
    bash ~/start_uwb.sh                 # publishes /uwb_tag
    python3 -m mapping_drone.moveit_mission --aruco-dict 7X7_1000 \
        --waypoints-from-json configs/waypoints_10jun.json

Modes:  --fly (default, MAVSDK autonomous) | --nofly (UWB+camera+artifacts, no arm) | --check
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .mapping import ArucoDetector, ArucoSighting, OccupancyGrid, camera_to_world
from .realsense import RealsenseNode, RealsenseFrame, deproject_pixel_to_camera_xyz
from .run_writer import RunWriter
from .validity import decide_landing_validity, describe_rule
from .uwb import UwbNode

logger = logging.getLogger("mapping_drone.moveit_mission")

try:
    from mavsdk import System
    from mavsdk.offboard import OffboardError, PositionNedYaw, VelocityNedYaw
    _MAVSDK_AVAILABLE = True
    _MAVSDK_IMPORT_ERROR: Optional[Exception] = None
except Exception as _exc:  # mavsdk not installed (laptop dev / --nofly)
    System = None  # type: ignore
    _MAVSDK_AVAILABLE = False
    _MAVSDK_IMPORT_ERROR = _exc

# --- Tuning, matching the organiser's move_it4.py ---
CAGE_HEIGHT_M = 3.5                 # arena cage ceiling/net height (confirmed 2026-06-11)
MAX_SAFE_ALT_M = 3.2               # hard cap: keep >=0.3 m clearance below the net
ALTITUDE_TARGET_DEFAULT = 2.5      # default ~1 m below the 3.5 m cage; use --takeoff-alt 3.0 for the higher option
ALTITUDE_TOLERANCE = 0.10
HORIZONTAL_TOLERANCE = 0.20
MAX_SPEED = 1.5
MIN_SPEED = 0.2
SLOW_DOWN_RADIUS = 2.0
WAYPOINT_TIMEOUT_S = 25.0
LOCAL_POS_TIMEOUT_S = 30.0
FRAMES_PER_WAYPOINT = 8
WAYPOINT_SCAN_SETTLE_S = 2.0
DEDUPE_RADIUS_M = 0.5
DEFAULT_WAYPOINTS = [(2.0, 2.0), (3.0, 2.0), (4.0, 2.0), (5.0, 2.0)]  # (north, east), per move_it4 (alt = --takeoff-alt)

# --- Pose + safety watchdog tuning (ported from controller.py) ---
FC_POSE_STALE_S = 1.5         # FC telemetry older than this is considered stale
BATTERY_LAND_FRAC = 0.15      # land if battery drops below 15%
POSE_LOSS_LAND_S = 5.0        # airborne + no fresh fix this long -> abort/land
POSE_NEVER_FIX_S = 10.0       # airborne this long with no fix ever -> abort/land
STUCK_GRACE_S = 12.0          # ignore stuck check for the first N s airborne
STUCK_WINDOW_S = 30.0         # window over which to measure movement
STUCK_MIN_MOVE_M = 0.3        # < this movement over the window = stuck -> abort
VEL_FAIL_ABORT = 5            # consecutive setpoint send failures -> abort

# --- Arena bounds (confirmed 2026-06-10) for the waypoint sanity check ---
ARENA_W_M = 5.5               # width  (east extent)
ARENA_L_M = 11.0              # length (north extent)
ARENA_MARGIN_M = 0.7          # required wall margin


def _world_distance(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class MoveItMission:
    def __init__(self, args, uwb: UwbNode, realsense: RealsenseNode,
                 run_writer: RunWriter, drone) -> None:
        self.args = args
        self.uwb = uwb
        self.realsense = realsense
        self.run_writer = run_writer
        self.drone = drone                       # mavsdk System() or None (--nofly)
        self.detector = ArucoDetector(dict_name=getattr(args, "aruco_dict", "7X7_1000"))
        self.grid = OccupancyGrid(resolution_m=0.05, size_m=20.0)
        self.sightings: list[ArucoSighting] = []
        self._seq = 0
        self._validity_cache: dict[int, Optional[bool]] = {}
        self._yaw_deg = 0.0
        self._stop = False
        self.state = "INIT"
        self.started_at = 0.0
        self._tasks: list[asyncio.Task] = []
        # FC fused-NED telemetry (authoritative, DDS-immune — see --pose).
        self._fc_n = 0.0
        self._fc_e = 0.0
        self._fc_down = 0.0
        self._fc_ts = 0.0
        # Safety watchdog state (ported from controller.py).
        self._battery_frac: Optional[float] = None
        self._last_pose_ts = 0.0          # last time we had a fresh horizontal fix
        self._pos_history: list[tuple[float, float, float]] = []  # (t, n, e)
        self._vel_fail = 0
        self._abort_reason: Optional[str] = None

    # ---- pose -------------------------------------------------------
    def _pose(self):
        """Return (n, e, down, yaw_deg, ready).

        Horizontal source per --pose: 'fc' = MAVSDK fused NED (default,
        DDS-immune, the frame survey_box.py waypoints live in); 'uwb' = the
        ROS /uwb_tag topic (arena frame, org-recommended but unreliable under
        cross-team DDS). Altitude ALWAYS comes from the FC when available —
        the UWB tag publishes N-E only, never a usable Z (org slide 9).
        Yaw always from the FC attitude stream.
        """
        yaw = self._yaw_deg
        src = getattr(self.args, "pose", "auto")
        fc_fresh = self._fc_ts > 0.0 and (time.monotonic() - self._fc_ts) < FC_POSE_STALE_S
        down = self._fc_down if fc_fresh else -float(self.args.takeoff_alt)
        # Path 1: FC fused NED (DDS-immune) — for 'fc' and 'auto'.
        if src in ("fc", "auto") and fc_fresh:
            return self._fc_n, self._fc_e, self._fc_down, yaw, True
        # Path 2: UWB /uwb_tag (arena frame) — for 'uwb', and as 'auto' fallback.
        if src in ("uwb", "auto"):
            n, e, ready = self.uwb.get_position()
            if ready:
                return n, e, down, yaw, True
        # Neither source fresh -> not ready; caller holds position.
        return (self._fc_n if fc_fresh else 0.0), (self._fc_e if fc_fresh else 0.0), down, yaw, False

    # ---- scan / artifacts (shared with px4_mission) ----------------
    def _validity_for(self, aruco_id: int) -> Optional[bool]:
        aid = int(aruco_id)
        if aid not in self._validity_cache:
            self._validity_cache[aid] = decide_landing_validity(aid)
        return self._validity_cache[aid]

    def _unique_pads(self) -> list[dict]:
        seen: dict[int, ArucoSighting] = {}
        for s in self.sightings:
            cur = seen.get(s.aruco_id)
            if cur is None or s.confidence > cur.confidence:
                seen[s.aruco_id] = s
        return [{"aruco_id": aid, "world_xyz_m": s.world_xyz_m, "valid": self._validity_for(aid)}
                for aid, s in seen.items()]

    def _write_status(self) -> None:
        n, e, down, yaw, _ = self._pose()
        flight_s = time.monotonic() - self.started_at if self.started_at else None
        try:
            self.run_writer.write_status({
                "state": self.state,
                "flight_seconds_or_none": flight_s,
                "drone_pose_or_none": (n, e, -down, yaw),
                "num_sightings": len(self.sightings),
                "unique_pads": self._unique_pads(),
                "battery_pct": (self._battery_frac * 100.0) if self._battery_frac is not None else float("nan"),
            })
        except Exception as exc:
            logger.warning("status write failed: %s", exc)

    def _register_sighting(self, frame: RealsenseFrame, aruco_id, pixel_center, bbox) -> None:
        u, v = pixel_center
        cam_xyz = world_xyz = None
        confidence = 0.5
        h, w = frame.depth_mm.shape[:2]
        if 0 <= u < w and 0 <= v < h:
            depth_mm = int(frame.depth_mm[v, u])
            if depth_mm > 0:
                n, e, down, yaw, _ = self._pose()
                try:
                    cam_xyz = deproject_pixel_to_camera_xyz(frame.intrinsics, u, v, depth_mm / 1000.0)
                    world_xyz = camera_to_world(cam_xyz, n, e, -down, yaw, self.args.gimbal_pitch)
                    confidence = 1.0
                except Exception as exc:
                    logger.debug("deproject failed id=%d: %s", aruco_id, exc)
        if world_xyz is not None:
            for prior in self.sightings:
                if (prior.aruco_id == aruco_id and prior.world_xyz_m is not None
                        and _world_distance(prior.world_xyz_m, world_xyz) < DEDUPE_RADIUS_M):
                    return
        self._seq += 1
        img_path = None
        try:
            img_path = self.run_writer.save_marker_image(frame.color_bgr, aruco_id, self._seq, bbox_xyxy=bbox)
        except Exception as exc:
            logger.warning("save marker image failed: %s", exc)
        sighting = ArucoSighting(
            aruco_id=aruco_id, pixel_center=pixel_center, bbox_xyxy=bbox,
            cam_xyz_m=cam_xyz, world_xyz_m=world_xyz, confidence=confidence,
            saved_image_path=img_path, first_seen_at=time.monotonic())
        self.sightings.append(sighting)
        valid = self._validity_for(aruco_id)
        try:
            self.run_writer.add_sighting(sighting, valid)
        except Exception as exc:
            logger.warning("add_sighting failed: %s", exc)
        if world_xyz is not None:
            try:
                self.grid.mark_landing_pad(world_xyz, aruco_id, valid)
            except Exception:
                pass
        logger.info("sighting id=%d world=%s valid=%s", aruco_id, world_xyz, valid)

    def _scan_once(self) -> None:
        for _ in range(FRAMES_PER_WAYPOINT):
            if self._stop:
                return
            frame = self.realsense.grab()
            if frame is None:
                time.sleep(0.05)
                continue
            n, e, down, yaw, _ = self._pose()
            try:
                self.grid.integrate(frame, (n, e, down, yaw), self.args.gimbal_pitch)
            except Exception as exc:
                logger.debug("grid integrate failed: %s", exc)
            for aruco_id, pc, bbox in self.detector.detect_in_frame(frame):
                self._register_sighting(frame, aruco_id, pc, bbox)
            time.sleep(0.05)

    # ---- mavsdk background yaw (for camera->world) -----------------
    async def _yaw_loop(self) -> None:
        try:
            async for att in self.drone.telemetry.attitude_euler():
                self._yaw_deg = float(att.yaw_deg)
                if self._stop:
                    return
        except Exception:
            return

    async def _telem_loop(self) -> None:
        """Stream the FC's fused NED position (authoritative pose source)."""
        try:
            async for p in self.drone.telemetry.position_velocity_ned():
                self._fc_n = float(p.position.north_m)
                self._fc_e = float(p.position.east_m)
                self._fc_down = float(p.position.down_m)
                self._fc_ts = time.monotonic()
                if self._stop:
                    return
        except Exception:
            return

    async def _battery_loop(self) -> None:
        """Track battery for the low-battery failsafe."""
        try:
            async for b in self.drone.telemetry.battery():
                frac = float(b.remaining_percent)
                # MAVSDK reports 0.0-1.0; some firmwares report 0-100.
                self._battery_frac = frac / 100.0 if frac > 1.5 else frac
                if self._stop:
                    return
        except Exception:
            return

    def _check_safety(self) -> Optional[str]:
        """Return an abort reason if an in-flight safety limit is breached,
        else None. Called before each waypoint while airborne."""
        # Low battery
        if self._battery_frac is not None and self._battery_frac < BATTERY_LAND_FRAC:
            return f"battery {self._battery_frac*100:.0f}% < {BATTERY_LAND_FRAC*100:.0f}%"
        airborne_s = time.monotonic() - self.started_at if self.started_at else 0.0
        # Pose loss: never got a fix, or lost it mid-flight
        if self._last_pose_ts == 0.0:
            if airborne_s > POSE_NEVER_FIX_S:
                return f"no position fix after {POSE_NEVER_FIX_S:.0f}s airborne"
        else:
            stale = time.monotonic() - self._last_pose_ts
            if stale > POSE_LOSS_LAND_S:
                return f"position fix stale {stale:.1f}s (> {POSE_LOSS_LAND_S:.0f}s)"
        # Position-stuck: moved < STUCK_MIN_MOVE_M over the last STUCK_WINDOW_S
        if airborne_s > STUCK_GRACE_S and len(self._pos_history) >= 2:
            now = time.monotonic()
            window = [(t, n, e) for (t, n, e) in self._pos_history if now - t <= STUCK_WINDOW_S]
            if len(window) >= 2 and (now - window[0][0]) >= STUCK_WINDOW_S * 0.8:
                ns = [n for _, n, _ in window]
                es = [e for _, _, e in window]
                span = math.hypot(max(ns) - min(ns), max(es) - min(es))
                if span < STUCK_MIN_MOVE_M:
                    return f"position-stuck ({span:.2f}m moved in {STUCK_WINDOW_S:.0f}s)"
        return None

    # ---- waypoint nav (faithful to move_it4) ----------------------
    async def _set_setpoint(self, n, e, alt, vn, ve) -> None:
        """Send a position+velocity setpoint, counting consecutive failures
        so a wedged offboard link aborts instead of silently looping."""
        try:
            await self.drone.offboard.set_position_velocity_ned(
                PositionNedYaw(n, e, -alt, 0.0), VelocityNedYaw(vn, ve, 0.0, 0.0))
            self._vel_fail = 0
        except Exception as exc:
            self._vel_fail += 1
            logger.warning("setpoint send failed (%d/%d): %s", self._vel_fail, VEL_FAIL_ABORT, exc)
            if self._vel_fail >= VEL_FAIL_ABORT:
                self._abort_reason = "offboard setpoint failures"
                self._stop = True

    async def _navigate_uwb(self, target_n: float, target_e: float, alt: float) -> bool:
        deadline = time.monotonic() + WAYPOINT_TIMEOUT_S
        while not self._stop:
            reason = self._check_safety()
            if reason:
                self._abort_reason = reason
                logger.error("SAFETY ABORT mid-waypoint: %s", reason)
                self._stop = True
                return False
            n, e, down, _yaw, ready = self._pose()
            if not ready:
                logger.warning("no fresh position fix — holding")
                await self._set_setpoint(target_n, target_e, alt, 0.0, 0.0)
                await asyncio.sleep(0.3)
                continue
            self._last_pose_ts = time.monotonic()
            self._pos_history.append((self._last_pose_ts, n, e))
            if len(self._pos_history) > 600:
                self._pos_history = self._pos_history[-400:]
            err_n, err_e = target_n - n, target_e - e
            dist = math.hypot(err_n, err_e)
            if dist <= HORIZONTAL_TOLERANCE:
                logger.info("reached wp (drift %.2fm)", dist)
                return True
            if dist >= SLOW_DOWN_RADIUS:
                speed = MAX_SPEED
            else:
                speed = MIN_SPEED + (MAX_SPEED - MIN_SPEED) * (dist / SLOW_DOWN_RADIUS)
            vel_n = err_n / dist * speed
            vel_e = err_e / dist * speed
            await self._set_setpoint(target_n, target_e, alt, vel_n, vel_e)
            if time.monotonic() > deadline:
                logger.warning("wp timeout — scanning anyway")
                return False
            await asyncio.sleep(0.1)
        return False

    # ---- modes -----------------------------------------------------
    async def run_check(self) -> int:
        logger.info("CHECK: MAVSDK connect + UWB pose, no arm")
        ok = False
        if self.drone is not None:
            try:
                await asyncio.wait_for(self.drone.connect(system_address=self.args.mavsdk_address), timeout=8.0)
                ct = time.monotonic() + 12.0
                async for st in self.drone.core.connection_state():
                    if st.is_connected:
                        ok = True
                        logger.info("MAVSDK connected via %s", self.args.mavsdk_address)
                        break
                    if self._stop or time.monotonic() > ct:
                        break
            except Exception as exc:
                logger.error("MAVSDK connect failed on %s: %s", self.args.mavsdk_address, exc)
        for _ in range(10):
            n, e, down, yaw, ready = self._pose()
            logger.info("UWB pose n=%.3f e=%.3f alt=%.3f ready=%s | mavsdk=%s",
                        n, e, -down, ready, ok)
            await asyncio.sleep(1.0)
        return 0 if (ok or self.uwb.last_update_ts > 0) else 2

    def run_nofly(self) -> int:
        logger.info("NO-FLY: UWB + camera + scan/detect/map/artifacts, never arms (MAVSDK unused)")
        self.state = "NOFLY_SCAN"
        self.started_at = time.monotonic()
        deadline = time.monotonic() + float(self.args.max_flight_time_s)
        # let UWB settle briefly
        t0 = time.monotonic()
        while time.monotonic() - t0 < 10.0 and not self._stop:
            if self.uwb.get_position()[2]:
                break
            time.sleep(0.2)
        else:
            logger.warning("no UWB fix yet — continuing; world coords may be invalid")
        while time.monotonic() < deadline and not self._stop:
            self._scan_once()
            self._write_status()
            time.sleep(0.2)
        self.state = "DONE"
        return 0

    async def run_fly(self, waypoints) -> int:
        alt = float(self.args.takeoff_alt)
        self.started_at = time.monotonic()
        drone = self.drone
        try:
            self.state = "CONNECTING"
            await asyncio.wait_for(drone.connect(system_address=self.args.mavsdk_address), timeout=10.0)
            connected = False
            ct = time.monotonic() + 15.0
            async for st in drone.core.connection_state():
                if st.is_connected:
                    connected = True
                    logger.info("MAVSDK connected via %s", self.args.mavsdk_address)
                    break
                if self._stop or time.monotonic() > ct:
                    break
            if not connected:
                logger.error("MAVSDK did not connect on %s — refusing to fly", self.args.mavsdk_address)
                return 2
            self.state = "AWAIT_LOCAL_POS"
            ok = False
            t = time.monotonic() + LOCAL_POS_TIMEOUT_S
            async for h in drone.telemetry.health():
                if h.is_local_position_ok:
                    ok = True
                    logger.info("local position OK")
                    break
                if time.monotonic() > t:
                    break
            if not ok:
                logger.error("no local position estimate — refusing to fly")
                return 2

            # Background telemetry: yaw (camera->world), FC fused NED (pose),
            # battery (failsafe). These feed _pose() and _check_safety().
            self._tasks.append(asyncio.create_task(self._yaw_loop()))
            self._tasks.append(asyncio.create_task(self._telem_loop()))
            self._tasks.append(asyncio.create_task(self._battery_loop()))
            try:
                await drone.action.set_takeoff_altitude(alt)
            except Exception:
                pass

            self.state = "ARMING"
            await drone.action.arm()
            # pre-stream a setpoint, then engage offboard (matches move_it4)
            await drone.offboard.set_position_velocity_ned(
                PositionNedYaw(0.0, 0.0, 0.0, 0.0), VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
            try:
                await drone.offboard.start()
            except OffboardError as err:
                logger.error("offboard start failed: %s", err)
                await drone.action.disarm()
                return 2

            self.state = "TAKEOFF"
            logger.info("takeoff to %.1f m", alt)
            await drone.offboard.set_position_velocity_ned(
                PositionNedYaw(0.0, 0.0, -alt, 0.0), VelocityNedYaw(0.0, 0.0, -0.5, 0.0))
            await asyncio.sleep(4.0)

            deadline = self.started_at + float(self.args.max_flight_time_s)
            for idx, (wn, we, wz) in enumerate(waypoints, start=1):
                if self._stop or time.monotonic() > deadline:
                    logger.warning("stop/time-limit before wp %d", idx)
                    break
                alt_wp = wz if wz is not None else alt
                if alt_wp > MAX_SAFE_ALT_M:
                    logger.warning("wp %d alt %.1f > safe max %.1f — clamping", idx, alt_wp, MAX_SAFE_ALT_M)
                    alt_wp = MAX_SAFE_ALT_M
                self.state = f"FLY_WP_{idx}"
                logger.info("WAYPOINT %d/%d -> N=%.2f E=%.2f alt=%.2f", idx, len(waypoints), wn, we, alt_wp)
                await self._navigate_uwb(wn, we, alt_wp)
                if self._stop:
                    # safety abort fired mid-waypoint — land NOW, skip the scan/hold
                    logger.warning("abort during wp %d — landing immediately", idx)
                    break
                # hold position; MAVSDK keeps streaming the last setpoint while we scan
                await drone.offboard.set_position_velocity_ned(
                    PositionNedYaw(wn, we, -alt_wp, 0.0), VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
                self.state = f"SCAN_WP_{idx}"
                await asyncio.sleep(WAYPOINT_SCAN_SETTLE_S)
                await asyncio.to_thread(self._scan_once)
                self._write_status()

            self.state = "LANDING"
            return await self._land_and_disarm(aborted=self._stop)
        except Exception:
            logger.exception("fly mission crashed")
            try:
                await self._land_and_disarm(aborted=True)
            except Exception:
                pass
            return 1
        finally:
            # Stop the background telemetry loops so they don't leak/pend.
            for t in self._tasks:
                t.cancel()
            if self._tasks:
                try:
                    await asyncio.gather(*self._tasks, return_exceptions=True)
                except Exception:
                    pass
            self._tasks = []

    async def _land_and_disarm(self, *, aborted: bool) -> int:
        if self._abort_reason:
            logger.error("landing due to ABORT: %s", self._abort_reason)
        logger.info("landing + disarming")
        try:
            await self.drone.offboard.stop()
        except Exception:
            pass
        try:
            await self.drone.action.land()
        except Exception as exc:
            logger.error("land failed: %s", exc)
        # NEVER disarm while airborne: wait for in_air=False up to a hard cap.
        landed = False
        deadline = time.monotonic() + 40.0
        try:
            async for in_air in self.drone.telemetry.in_air():
                if not in_air:
                    landed = True
                    break
                if time.monotonic() > deadline:
                    break
        except Exception:
            pass
        if landed:
            try:
                await self.drone.action.disarm()
            except Exception:
                pass
        else:
            logger.error("still in_air after 40s — NOT disarming (safety); use the RC kill switch")
        self.state = "ABORTED" if aborted else "DONE"
        return 1 if aborted else 0

    def request_stop(self) -> None:
        self._stop = True


def _load_waypoints(args):
    """Return [(north, east, alt_or_None), ...]. Accepts [n,e] or [n,e,alt] rows."""
    path = args.waypoints or args.waypoints_from_json
    if not path:
        logger.warning("no --waypoints-from-json given — using tiny DEFAULT_WAYPOINTS demo, "
                       "NOT a real %sx%s arena sweep. Generate one with tools/survey_box.py.",
                       ARENA_W_M, ARENA_L_M)
        return [(n, e, None) for (n, e) in DEFAULT_WAYPOINTS]
    data = json.loads(Path(path).read_text())
    out = []
    for i, r in enumerate(data):
        if not (isinstance(r, (list, tuple)) and len(r) >= 2):
            raise ValueError(f"{path}: waypoint row {i} is malformed (need [n,e] or [n,e,alt]): {r!r}")
        try:
            out.append((float(r[0]), float(r[1]), (float(r[2]) if len(r) > 2 else None)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}: waypoint row {i} has non-numeric values {r!r}: {exc}")
    if not out:
        raise ValueError(f"{path}: waypoints list is empty")
    _sanity_check_waypoints(out, path)
    return out


def _sanity_check_waypoints(wps, path) -> None:
    """Heuristic sanity check vs the 5.5x11 arena. Warnings only (the NED
    frame origin/orientation is set by survey — bounds may be shifted)."""
    ns = [n for (n, _e, _a) in wps]
    es = [e for (_n, e, _a) in wps]
    n_span, e_span = max(ns) - min(ns), max(es) - min(es)
    usable_n, usable_e = ARENA_L_M - 2 * ARENA_MARGIN_M, ARENA_W_M - 2 * ARENA_MARGIN_M
    logger.info("waypoints: %d pts, north %.2f..%.2f (span %.2f), east %.2f..%.2f (span %.2f)",
                len(wps), min(ns), max(ns), n_span, min(es), max(es), e_span)
    # Over-coverage: a span wider than the arena+margin risks flying into a wall.
    if n_span > ARENA_L_M + 0.5 or e_span > ARENA_W_M + 0.5:
        logger.warning("waypoints span (%.1fx%.1f) EXCEEDS arena (%.1fx%.1f) — wall-collision risk! "
                       "Check the frame/scale in %s.", n_span, e_span, ARENA_L_M, ARENA_W_M, path)
    # Under-coverage: too small to map the arena (e.g. the legacy 4.4x7.85 file).
    if n_span < 0.6 * usable_n or e_span < 0.6 * usable_e:
        logger.warning("waypoints span (%.1fx%.1f) covers < 60%% of usable arena (%.1fx%.1f) — "
                       "may miss landing pads. Re-survey with tools/survey_box.py.",
                       n_span, e_span, usable_n, usable_e)


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Org-aligned MAVSDK mapping mission (move_it4 pattern)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--fly", action="store_true", help="MAVSDK autonomous survey (default)")
    mode.add_argument("--nofly", action="store_true", help="UWB+camera+artifacts, no arm")
    mode.add_argument("--check", action="store_true", help="connect + print pose, no arm")
    p.add_argument("--mavsdk-address", default="serial:///dev/ttyS6:921600")
    p.add_argument("--pose", choices=["auto", "fc", "uwb"], default="auto",
                   help="horizontal pose source (REDUNDANT): auto=FC fused NED, auto-fallback "
                        "to /uwb_tag if FC goes stale (default); fc=FC only (DDS-immune, matches "
                        "survey_box waypoints); uwb=/uwb_tag arena frame only. Altitude always from FC.")
    p.add_argument("--use-ir-for-aruco", action="store_true",
                   help="D450 (no-RGB) cameras: read left IR + synth BGR for ArUco")
    p.add_argument("--aruco-dict", default="7X7_1000,6X6_250",
                   help="comma-separated dicts scanned every frame. Default hedges both "
                        "7X7_1000 (assumed org dict) AND 6X6_250 so we don't miss markers "
                        "if the real dict differs; logs which dict each ID came from.")
    p.add_argument("--waypoints", default=None)
    p.add_argument("--waypoints-from-json", default=None)
    p.add_argument("--takeoff-alt", type=float, default=ALTITUDE_TARGET_DEFAULT,
                   help=f"flight altitude (m). Default {ALTITUDE_TARGET_DEFAULT}; cage ceiling is "
                        f"{CAGE_HEIGHT_M} m so values are hard-capped at {MAX_SAFE_ALT_M}. "
                        f"Use --takeoff-alt 3.0 for the higher option.")
    p.add_argument("--gimbal-pitch", type=float, default=-90.0)
    p.add_argument("--max-flight-time-s", type=int, default=420)
    p.add_argument("--runs-dir", default="mapping_drone/runs")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args(argv)
    if not (args.fly or args.nofly or args.check):
        args.fly = True
    return args


def main() -> int:
    args = _parse_args()
    # Isolate our ROS2 graph from other teams on the shared arena network.
    # Everything ROS2 runs on this one Orange Pi, so localhost-only is safe
    # and walls us off from cross-team DDS interference on ROS_DOMAIN_ID=0.
    os.environ.setdefault("ROS_LOCALHOST_ONLY", "1")
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger_pre = logging.getLogger("mapping_drone.moveit_mission")
    logger_pre.info("ROS_LOCALHOST_ONLY=%s | pose source=%s", os.environ.get("ROS_LOCALHOST_ONLY"), args.pose)
    # Hard altitude cap: the cage ceiling is CAGE_HEIGHT_M; never fly into the net.
    if args.takeoff_alt > MAX_SAFE_ALT_M:
        logger_pre.warning("--takeoff-alt %.1f m exceeds safe max %.1f m (cage %.1f m) — CLAMPING to %.1f",
                           args.takeoff_alt, MAX_SAFE_ALT_M, CAGE_HEIGHT_M, MAX_SAFE_ALT_M)
        args.takeoff_alt = MAX_SAFE_ALT_M

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.runs_dir).resolve() / f"run_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    # Mirror logs to run_dir/log.txt (run_summary.json advertises this artifact).
    try:
        _fh = logging.FileHandler(run_dir / "log.txt")
        _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(_fh)
    except Exception:
        pass
    logger.info("run dir: %s | ArUco dict: %s | validity: %s", run_dir, args.aruco_dict, describe_rule())
    _org_ids = (11, 45, 51, 67, 101)
    _cls = {i: decide_landing_validity(i) for i in _org_ids}
    logger.info("VALIDITY of org IDs %s -> %s", _org_ids, _cls)
    if all(v is False for v in _cls.values()):
        logger.warning("ALL FIVE org pads classify INVALID — set MAPPING_DRONE_VALIDITY before a scored run!")
    elif all(v is None for v in _cls.values()):
        logger.warning("ALL FIVE org pads classify UNKNOWN — validity lookup table not found; "
                       "run from semifinal/ or set MAPPING_DRONE_VALIDITY_LOOKUP to the JSON path.")
    elif all(v is True for v in _cls.values()):
        logger.warning("ALL FIVE org pads classify VALID — this is the DEFAULT pre-fill. "
                       "Confirm it matches the marshal's announced valid/invalid split; "
                       "edit configs/valid_ids_finals.json before a scored run!")

    drone = None
    if args.fly or args.check:
        if not _MAVSDK_AVAILABLE:
            logger.error("mavsdk not importable (%s). On the drone: pip install mavsdk, or use --nofly.",
                         _MAVSDK_IMPORT_ERROR)
            return 2
        drone = System()

    uwb = UwbNode()
    realsense = RealsenseNode(use_ir_for_aruco=args.use_ir_for_aruco)
    run_writer = RunWriter(run_dir, run_ts)

    mission: Optional[MoveItMission] = None
    aborted = False
    try:
        uwb.start()
        try:
            realsense.start()
        except Exception as exc:
            if args.check:
                logger.warning("RealSense unavailable (%s) — continuing --check without camera", exc)
            else:
                raise   # --nofly / --fly genuinely need the camera
        mission = MoveItMission(args, uwb, realsense, run_writer, drone)

        def _on_sig(*_a):
            logger.warning("signal — stopping")
            if mission is not None:
                mission.request_stop()
        for s in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(s, _on_sig)
            except Exception:
                pass

        if args.check:
            return asyncio.run(mission.run_check())
        if args.fly:
            code = asyncio.run(mission.run_fly(_load_waypoints(args)))
            aborted = code != 0
            return code
        code = mission.run_nofly()
        aborted = code != 0
        return code
    except Exception:
        logger.exception("mission crashed")
        aborted = True
        return 1
    finally:
        total_s = (time.monotonic() - mission.started_at) if (mission and mission.started_at) else 0.0
        try:
            run_writer.finalise(mission.grid if mission else OccupancyGrid(resolution_m=0.05, size_m=20.0),
                                total_s, aborted, abort_reason="moveit_mission" if aborted else None)
        except Exception as exc:
            logger.error("finalise failed: %s", exc)
        try:
            realsense.stop()
        except Exception:
            pass
        try:
            uwb.stop()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
