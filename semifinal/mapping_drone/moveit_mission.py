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
ALTITUDE_TARGET_DEFAULT = 2.0      # org sample default (override per arena/floor)
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
DEFAULT_WAYPOINTS = [(2.0, 2.0), (3.0, 2.0), (4.0, 2.0), (5.0, 2.0)]  # (north, east), per move_it4


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
        self.detector = ArucoDetector(dict_name=getattr(args, "aruco_dict", "6X6_250"))
        self.grid = OccupancyGrid(resolution_m=0.05, size_m=20.0)
        self.sightings: list[ArucoSighting] = []
        self._seq = 0
        self._validity_cache: dict[int, Optional[bool]] = {}
        self._yaw_deg = 0.0
        self._stop = False
        self.state = "INIT"
        self.started_at = 0.0
        self._tasks: list[asyncio.Task] = []

    # ---- pose (UWB n/e + alt + mavsdk yaw) -------------------------
    def _pose(self):
        n, e, ready = self.uwb.get_position()    # n=pose.y, e=pose.x (matches move_it4)
        alt = self.uwb.get_altitude()
        alt = alt if alt is not None else float(self.args.takeoff_alt)
        return n, e, -alt, self._yaw_deg, ready

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
                "battery_pct": float("nan"),
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

    # ---- waypoint nav (faithful to move_it4) ----------------------
    async def _navigate_uwb(self, target_n: float, target_e: float, alt: float) -> bool:
        deadline = time.monotonic() + WAYPOINT_TIMEOUT_S
        while not self._stop:
            n, e, ready = self.uwb.get_position()
            if not ready:
                logger.warning("UWB lost — holding")
                await self.drone.offboard.set_position_velocity_ned(
                    PositionNedYaw(target_n, target_e, -alt, 0.0), VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
                await asyncio.sleep(0.5)
                continue
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
            await self.drone.offboard.set_position_velocity_ned(
                PositionNedYaw(target_n, target_e, -alt, 0.0),
                VelocityNedYaw(vel_n, vel_e, 0.0, 0.0))
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
                async for st in self.drone.core.connection_state():
                    if st.is_connected:
                        ok = True
                        logger.info("MAVSDK connected via %s", self.args.mavsdk_address)
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
            await drone.connect(system_address=self.args.mavsdk_address)
            async for st in drone.core.connection_state():
                if st.is_connected:
                    logger.info("MAVSDK connected via %s", self.args.mavsdk_address)
                    break
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

            self._tasks.append(asyncio.create_task(self._yaw_loop()))
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
            for idx, (wn, we) in enumerate(waypoints, start=1):
                if self._stop or time.monotonic() > deadline:
                    logger.warning("stop/time-limit before wp %d", idx)
                    break
                self.state = f"FLY_WP_{idx}"
                logger.info("WAYPOINT %d/%d -> N=%.2f E=%.2f", idx, len(waypoints), wn, we)
                await self._navigate_uwb(wn, we, alt)
                # hold position; MAVSDK keeps streaming the last setpoint while we scan
                await drone.offboard.set_position_velocity_ned(
                    PositionNedYaw(wn, we, -alt, 0.0), VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
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

    async def _land_and_disarm(self, *, aborted: bool) -> int:
        logger.info("landing + disarming")
        try:
            await self.drone.offboard.stop()
        except Exception:
            pass
        try:
            await self.drone.action.land()
        except Exception as exc:
            logger.error("land failed: %s", exc)
        await asyncio.sleep(6.0)
        try:
            await self.drone.action.disarm()
        except Exception:
            pass
        self.state = "ABORTED" if aborted else "DONE"
        return 1 if aborted else 0

    def request_stop(self) -> None:
        self._stop = True


def _load_waypoints(args) -> list[tuple[float, float]]:
    path = args.waypoints or args.waypoints_from_json
    if not path:
        return list(DEFAULT_WAYPOINTS)
    data = json.loads(Path(path).read_text())
    out = [(float(r[0]), float(r[1])) for r in data]   # (north, east); extra cols ignored
    if not out:
        raise ValueError(f"{path}: waypoints list is empty")
    return out


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Org-aligned MAVSDK mapping mission (move_it4 pattern)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--fly", action="store_true", help="MAVSDK autonomous survey (default)")
    mode.add_argument("--nofly", action="store_true", help="UWB+camera+artifacts, no arm")
    mode.add_argument("--check", action="store_true", help="connect + print pose, no arm")
    p.add_argument("--mavsdk-address", default="serial:///dev/ttyS6:921600")
    p.add_argument("--aruco-dict", default="6X6_250")
    p.add_argument("--waypoints", default=None)
    p.add_argument("--waypoints-from-json", default=None)
    p.add_argument("--takeoff-alt", type=float, default=ALTITUDE_TARGET_DEFAULT,
                   help="metres (org move_it4 uses 2.0; raise if the arena floor is higher)")
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
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.runs_dir).resolve() / f"run_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("run dir: %s | ArUco dict: %s | validity: %s", run_dir, args.aruco_dict, describe_rule())

    drone = None
    if args.fly or args.check:
        if not _MAVSDK_AVAILABLE:
            logger.error("mavsdk not importable (%s). On the drone: pip install mavsdk, or use --nofly.",
                         _MAVSDK_IMPORT_ERROR)
            return 2
        drone = System()

    uwb = UwbNode()
    realsense = RealsenseNode()
    run_writer = RunWriter(run_dir, run_ts)

    mission: Optional[MoveItMission] = None
    aborted = False
    try:
        uwb.start()
        realsense.start()
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
