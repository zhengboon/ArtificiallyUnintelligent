"""Main asyncio controller for the BrainHack 2026 mapping drone.

Orchestrates UWB position, MAVSDK flight, Realsense capture, ArUco detection,
top-down occupancy mapping, and judge-readable artifact writing.

Run with mocks (no hardware needed):
    python3 -m mapping_drone.controller --mock-all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .mapping import ArucoDetector, ArucoSighting, OccupancyGrid, camera_to_world
from .realsense import (
    MockRealsenseNode,
    RealsenseAdapter,
    RealsenseFrame,
    RealsenseNode,
    deproject_pixel_to_camera_xyz,
)
from .run_writer import RunWriter
from .uwb import MockUwbNode, UwbAdapter, UwbNode
from .validity import decide_landing_validity, describe_rule

logger = logging.getLogger("mapping_drone.controller")

# Velocity controller gains (carry-over from kolomee.py)
KP_XY = 0.1
KP_Z = 0.1
MAX_VEL_XY = 0.5
MAX_VEL_Z = 0.3
MAX_HOVER_XY = 0.15
HOVER_DEADBAND = 0.03
N_THRESHOLD = 0.1
E_THRESHOLD = 0.1
D_THRESHOLD = 0.1
LOOP_HZ = 10.0
TAKEOFF_HEIGHT = 0.8

# Safety thresholds
UWB_LOSS_GRACE_S = 1.0
UWB_LOSS_LAND_S = 5.0
UWB_NEVER_FIX_GRACE_S = 8.0  # extra grace after takeoff for first ever UWB fix
STUCK_GRACE_S = 10.0
STUCK_WINDOW_S = 20.0
STUCK_MIN_MOVE_M = 0.3
BATTERY_LAND_PCT = 15.0
HEALTH_TIMEOUT_S = 15.0
LAND_DISARM_TIMEOUT_S = 15.0
LAND_DISARM_HARD_CAP_S = 60.0
HOVER_SETTLE_S = 0.8

# Sighting dedupe radius
DEDUPE_RADIUS_M = 0.5

# Frames to grab per waypoint pause
FRAMES_PER_WAYPOINT = 8
WAYPOINT_PAUSE_S = 2.0

# 4 waypoint lawn-mower sweep. Final return-to-origin is implicit via land()
# (PX4 lands in place); add an explicit (0,0) waypoint to the JSON file when a
# physical return is required.
DEFAULT_WAYPOINTS = [
    (0.0, 0.0, 1.5),
    (2.0, 0.0, 1.5),
    (2.0, 2.0, 1.5),
    (0.0, 2.0, 1.5),
]


# ============================================================
# Mock MAVSDK
# ============================================================
@dataclass
class _MockPosVelNedInner:
    north_m: float = 0.0
    east_m: float = 0.0
    down_m: float = 0.0


@dataclass
class _MockVelNedInner:
    north_m_s: float = 0.0
    east_m_s: float = 0.0
    down_m_s: float = 0.0


@dataclass
class _MockHealth:
    is_global_position_ok: bool = True
    is_home_position_ok: bool = True
    is_local_position_ok: bool = True
    is_armable: bool = True


@dataclass
class _MockBattery:
    remaining_percent: float = 95.0


class _MockVelocityNedYaw:
    def __init__(self, n: float, e: float, d: float, yaw: float) -> None:
        self.north_m_s = n
        self.east_m_s = e
        self.down_m_s = d
        self.yaw_deg = yaw


class MockMavsdk:
    """Pretend drone — mirrors the subset of MAVSDK System() we use.

    Exposes telemetry.position_velocity_ned() yielding objects with NESTED
    position/velocity attributes (matching the real MAVSDK shape used by
    kolomee.py: pvn.position.down_m).
    """

    def __init__(self) -> None:
        self._pos = _MockPosVelNedInner(down_m=0.0)
        self._vel = _MockVelNedInner()
        self._in_air = False
        self._armed = False
        self._offboard_active = False
        self._heading_deg = 0.0
        self._last_update = time.monotonic()
        self.action = _MockAction(self)
        self.offboard = _MockOffboard(self)
        self.telemetry = _MockTelemetry(self)

    async def connect(self, system_address: str | None = None) -> None:
        await asyncio.sleep(0.05)
        logger.info("MockMavsdk connect: %s", system_address)

    def _tick(self) -> None:
        now = time.monotonic()
        dt = now - self._last_update
        self._last_update = now
        if self._in_air or self._offboard_active:
            self._pos.north_m += self._vel.north_m_s * dt
            self._pos.east_m += self._vel.east_m_s * dt
            self._pos.down_m += self._vel.down_m_s * dt

    def _snapshot_pvn(self) -> SimpleNamespace:
        """Return a SimpleNamespace shaped like real MAVSDK PositionVelocityNed."""
        return SimpleNamespace(
            position=SimpleNamespace(
                north_m=self._pos.north_m,
                east_m=self._pos.east_m,
                down_m=self._pos.down_m,
            ),
            velocity=SimpleNamespace(
                north_m_s=self._vel.north_m_s,
                east_m_s=self._vel.east_m_s,
                down_m_s=self._vel.down_m_s,
            ),
        )


class _MockAction:
    def __init__(self, drone: MockMavsdk) -> None:
        self._d = drone

    async def arm(self) -> None:
        await asyncio.sleep(0.05)
        self._d._armed = True
        logger.info("MockMavsdk: armed")

    async def disarm(self) -> None:
        await asyncio.sleep(0.05)
        self._d._armed = False
        logger.info("MockMavsdk: disarmed")

    async def takeoff(self) -> None:
        await asyncio.sleep(0.1)
        self._d._in_air = True
        self._d._pos.down_m = -TAKEOFF_HEIGHT
        logger.info("MockMavsdk: takeoff")

    async def land(self) -> None:
        await asyncio.sleep(0.1)
        self._d._vel.north_m_s = 0.0
        self._d._vel.east_m_s = 0.0
        self._d._vel.down_m_s = 0.0
        self._d._pos.down_m = 0.0
        self._d._in_air = False
        logger.info("MockMavsdk: landed")

    async def set_takeoff_altitude(self, alt_m: float) -> None:
        await asyncio.sleep(0.01)


class _MockOffboard:
    def __init__(self, drone: MockMavsdk) -> None:
        self._d = drone

    async def set_velocity_ned(self, vel: _MockVelocityNedYaw) -> None:
        self._d._tick()
        self._d._vel.north_m_s = vel.north_m_s
        self._d._vel.east_m_s = vel.east_m_s
        self._d._vel.down_m_s = vel.down_m_s
        self._d._heading_deg = float(vel.yaw_deg)

    async def start(self) -> None:
        await asyncio.sleep(0.05)
        self._d._offboard_active = True
        logger.info("MockMavsdk: offboard started")

    async def stop(self) -> None:
        await asyncio.sleep(0.05)
        self._d._offboard_active = False


class _MockTelemetry:
    def __init__(self, drone: MockMavsdk) -> None:
        self._d = drone

    async def position_velocity_ned(self):
        while True:
            self._d._tick()
            yield self._d._snapshot_pvn()
            await asyncio.sleep(0.05)

    async def attitude_euler(self):
        while True:
            self._d._tick()
            yield SimpleNamespace(
                roll_deg=0.0,
                pitch_deg=0.0,
                yaw_deg=float(self._d._heading_deg),
            )
            await asyncio.sleep(0.1)

    async def in_air(self):
        while True:
            yield self._d._in_air
            await asyncio.sleep(0.2)

    async def health(self):
        while True:
            yield _MockHealth()
            await asyncio.sleep(0.5)

    async def battery(self):
        while True:
            yield _MockBattery()
            await asyncio.sleep(1.0)


# ============================================================
# Real MAVSDK loader (deferred import)
# ============================================================
def _load_real_mavsdk() -> tuple[Any, Any]:
    """Returns (System, VelocityNedYaw). Raises ImportError if mavsdk missing."""
    from mavsdk import System  # type: ignore
    from mavsdk.offboard import VelocityNedYaw  # type: ignore
    return System, VelocityNedYaw


# ============================================================
# Shared flight state
# ============================================================
@dataclass
class FlightState:
    """Snapshot of drone + run progress; consumed by status writer task."""
    state: str = "INIT"
    started_at: float = 0.0
    airborne_at: float = 0.0  # set the first time in_air becomes True
    drone_n: float = 0.0
    drone_e: float = 0.0
    drone_down: float = 0.0
    drone_yaw: float = 0.0
    battery_pct: float = 100.0
    in_air: bool = False
    last_uwb_ts: float = 0.0
    aborted: bool = False
    abort_reason: str = ""
    stop_requested: bool = False
    position_history: list[tuple[float, float, float, float]] = field(default_factory=list)


# ============================================================
# Controller class
# ============================================================
class MappingController:
    def __init__(
        self,
        args: argparse.Namespace,
        uwb: UwbAdapter,
        realsense: RealsenseAdapter,
        drone: Any,
        run_writer: RunWriter,
        velocity_cls: Any,
    ) -> None:
        self.args = args
        self.uwb = uwb
        self.realsense = realsense
        self.drone = drone
        self.run_writer = run_writer
        self.VelocityNedYaw = velocity_cls

        self.state = FlightState()
        aruco_dict = getattr(args, "aruco_dict", "6X6_250")
        self.detector = ArucoDetector(dict_name=aruco_dict)
        self.grid = OccupancyGrid(resolution_m=0.05, size_m=20.0)
        self.sightings: list[ArucoSighting] = []
        # Cache: aruco_id -> validity, decided at FIRST sighting. Ensures
        # STATUS.txt and landing_pads.json never disagree even if the rule
        # behaviour changes (e.g., env var flipped mid-run).
        self._validity_cache: dict[int, bool] = {}
        self._sighting_seq = 0
        self._stop_event = asyncio.Event()
        self._telem_task: asyncio.Task | None = None
        self._attitude_task: asyncio.Task | None = None
        self._battery_task: asyncio.Task | None = None
        self._in_air_task: asyncio.Task | None = None
        self._status_task: asyncio.Task | None = None
        self._is_mock_drone = isinstance(drone, MockMavsdk)

    # ----- validity helper -----
    def _validity_for(self, aruco_id: int) -> bool:
        """Return cached validity, populating on first sighting."""
        cached = self._validity_cache.get(int(aruco_id))
        if cached is not None:
            return cached
        decided = bool(decide_landing_validity(int(aruco_id)))
        self._validity_cache[int(aruco_id)] = decided
        return decided

    # ----- telemetry pump -----
    async def _telemetry_loop(self) -> None:
        """Mirrors kolomee.pos_task: reads pvn.position.down_m (NESTED)."""
        try:
            async for pvn in self.drone.telemetry.position_velocity_ned():
                # NESTED access — matches kolomee.py and real MAVSDK shape.
                self.state.drone_down = float(pvn.position.down_m)
                # In mock mode, mirror MAVSDK's integrated NED position into
                # the mock UWB so the controller perceives motion. Without
                # this the drone looks "stuck at (0, 0)" forever and the
                # position-stuck watchdog would fire. We deliberately do this
                # BEFORE reading uwb.get_position() below so the very next
                # line picks up the fresh mock-injected fix.
                if isinstance(self.uwb, MockUwbNode) and isinstance(self.drone, MockMavsdk):
                    try:
                        self.uwb.set_position(
                            float(pvn.position.north_m),
                            float(pvn.position.east_m),
                        )
                    except Exception:
                        logger.debug("mock UWB set_position failed", exc_info=True)
                n, e, ready = self.uwb.get_position()
                if ready:
                    self.state.drone_n = n
                    self.state.drone_e = e
                    self.state.last_uwb_ts = self.uwb.last_update_ts
                self.state.position_history.append(
                    (time.monotonic(), self.state.drone_n, self.state.drone_e, -self.state.drone_down)
                )
                if len(self.state.position_history) > 4096:
                    self.state.position_history = self.state.position_history[-2048:]
                if self._stop_event.is_set():
                    return
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("telemetry loop ended: %s", exc)

    async def _attitude_loop(self) -> None:
        """Mirrors kolomee.attitude_task: subscribes telemetry.attitude_euler()."""
        try:
            async for a in self.drone.telemetry.attitude_euler():
                self.state.drone_yaw = float(a.yaw_deg)
                if self._stop_event.is_set():
                    return
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("attitude loop ended: %s", exc)

    async def _battery_loop(self) -> None:
        try:
            async for b in self.drone.telemetry.battery():
                self.state.battery_pct = float(b.remaining_percent)
                if self._stop_event.is_set():
                    return
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.debug("battery loop ended: %s", exc)

    async def _in_air_loop(self) -> None:
        try:
            async for v in self.drone.telemetry.in_air():
                was_in_air = self.state.in_air
                self.state.in_air = bool(v)
                if self.state.in_air and not was_in_air and self.state.airborne_at == 0.0:
                    self.state.airborne_at = time.monotonic()
                    logger.info("first airborne tick (airborne_at set)")
                if self._stop_event.is_set():
                    return
        except asyncio.CancelledError:
            return
        except Exception:
            return

    # ----- status writer -----
    async def _status_writer_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                self._write_status()
                await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            self._write_status()
            return

    def _write_status(self) -> None:
        unique = self._unique_pads()
        flight_s = (
            time.monotonic() - self.state.started_at if self.state.started_at > 0 else None
        )
        snapshot = {
            "state": self.state.state,
            "flight_seconds_or_none": flight_s,
            "drone_pose_or_none": (
                self.state.drone_n,
                self.state.drone_e,
                -self.state.drone_down,
                self.state.drone_yaw,
            ),
            "num_sightings": len(self.sightings),
            "unique_pads": unique,
            "battery_pct": self.state.battery_pct,
        }
        try:
            self.run_writer.write_status(snapshot)
        except Exception as exc:
            logger.warning("status write failed: %s", exc)

    def _unique_pads(self) -> list[dict]:
        seen: dict[int, ArucoSighting] = {}
        for s in self.sightings:
            cur = seen.get(s.aruco_id)
            if cur is None or s.confidence > cur.confidence:
                seen[s.aruco_id] = s
        out = []
        for aid, s in seen.items():
            out.append(
                {
                    "aruco_id": aid,
                    "world_xyz_m": s.world_xyz_m,
                    "valid": self._validity_for(aid),
                }
            )
        return out

    # ----- safety -----
    def _check_safety(self) -> str | None:
        """Returns abort reason or None."""
        now = time.monotonic()
        if self.state.battery_pct < BATTERY_LAND_PCT:
            return f"battery low ({self.state.battery_pct:.0f}%)"

        # UWB watchdog. Two cases:
        #   (a) we had a fix and lost it for too long -> abort
        #   (b) in --real mode we never got a fix at all and we're past
        #       takeoff + grace -> abort (sensor probably broken)
        if self.state.last_uwb_ts > 0:
            since = now - self.state.last_uwb_ts
            if since > UWB_LOSS_LAND_S:
                return f"UWB lost for {since:.1f}s"
        else:
            using_real_uwb = isinstance(self.uwb, UwbNode)
            if (
                using_real_uwb
                and self.state.airborne_at > 0
                and now - self.state.airborne_at > UWB_NEVER_FIX_GRACE_S
            ):
                return "UWB never produced a fix (real mode)"

        # position-stuck only after takeoff + grace, NOT from started_at
        # (which would fire while we are still on the ground waiting for arm).
        if (
            self.state.airborne_at > 0
            and now - self.state.airborne_at > STUCK_GRACE_S
        ):
            window_start = now - STUCK_WINDOW_S
            window = [
                p for p in self.state.position_history if p[0] >= window_start
            ]
            if len(window) >= 2:
                ns = [p[1] for p in window]
                es = [p[2] for p in window]
                ds = max(ns) - min(ns)
                de = max(es) - min(es)
                moved = math.hypot(ds, de)
                if moved < STUCK_MIN_MOVE_M and now - window[0][0] >= STUCK_WINDOW_S - 1.0:
                    return f"position-stuck (moved {moved:.2f}m in {STUCK_WINDOW_S:.0f}s)"
        return None

    # ----- flight primitives -----
    async def _send_velocity(self, vn: float, ve: float, vd: float, yaw_deg: float = 0.0) -> None:
        try:
            await self.drone.offboard.set_velocity_ned(
                self.VelocityNedYaw(vn, ve, vd, yaw_deg)
            )
        except Exception as exc:
            logger.warning("set_velocity_ned failed: %s", exc)

    async def _offboard_prewarm(self) -> None:
        logger.info("offboard pre-warm (20x zero velocity)")
        for _ in range(20):
            await self._send_velocity(0.0, 0.0, 0.0, 0.0)
            await asyncio.sleep(0.05)
        try:
            await self.drone.offboard.start()
        except Exception as exc:
            logger.error("offboard.start() failed: %s", exc)
            raise

    async def hover_for(self, seconds: float) -> None:
        """Active hover with P-controller correction for ``seconds`` seconds.

        Used both at waypoint arrival (brief settle) and during the per-waypoint
        scan window. Locks the position at entry and corrects drift, instead of
        sending raw zeros which let the drone drift in wind.
        """
        if seconds <= 0:
            return
        hover_n = self.state.drone_n
        hover_e = self.state.drone_e
        hover_d = self.state.drone_down
        deadline = time.monotonic() + float(seconds)
        dt = 1.0 / LOOP_HZ
        while time.monotonic() < deadline:
            if self._stop_event.is_set() or self.state.aborted:
                return
            err_n = hover_n - self.state.drone_n
            err_e = hover_e - self.state.drone_e
            err_d = hover_d - self.state.drone_down
            vn = max(-MAX_HOVER_XY, min(MAX_HOVER_XY, err_n * KP_XY))
            ve = max(-MAX_HOVER_XY, min(MAX_HOVER_XY, err_e * KP_XY))
            vd = max(-MAX_VEL_Z, min(MAX_VEL_Z, err_d * KP_Z))
            if abs(err_n) < HOVER_DEADBAND:
                vn = 0.0
            if abs(err_e) < HOVER_DEADBAND:
                ve = 0.0
            if abs(err_d) < HOVER_DEADBAND:
                vd = 0.0
            await self._send_velocity(vn, ve, vd)
            await asyncio.sleep(dt)

    async def fly_to_position_velocity(
        self, target_n: float, target_e: float, target_alt_m: float, timeout_s: float = 30.0
    ) -> bool:
        """Velocity-loop P-controller (adapted from kolomee.py). Returns reached."""
        logger.info("fly_to (%.2f, %.2f, alt=%.2f)", target_n, target_e, target_alt_m)
        target_down = -target_alt_m
        deadline = time.monotonic() + timeout_s
        dt = 1.0 / LOOP_HZ
        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                return False
            abort = self._check_safety()
            if abort:
                self.state.aborted = True
                self.state.abort_reason = abort
                logger.error("abort during fly_to: %s", abort)
                return False
            n = self.state.drone_n
            e = self.state.drone_e
            d = self.state.drone_down
            err_n = target_n - n
            err_e = target_e - e
            err_d = target_down - d
            if (
                abs(err_n) < N_THRESHOLD
                and abs(err_e) < E_THRESHOLD
                and abs(err_d) < D_THRESHOLD
            ):
                logger.debug("arrived at waypoint — settling")
                # Active hover for ~1s before reporting reached, so callers
                # don't immediately tear into the scan with the drone still
                # drifting.
                await self.hover_for(HOVER_SETTLE_S)
                return True
            vn = max(-MAX_VEL_XY, min(MAX_VEL_XY, err_n * KP_XY * 5.0))
            ve = max(-MAX_VEL_XY, min(MAX_VEL_XY, err_e * KP_XY * 5.0))
            vd = max(-MAX_VEL_Z, min(MAX_VEL_Z, err_d * KP_Z * 5.0))
            await self._send_velocity(vn, ve, vd)
            await asyncio.sleep(dt)
        logger.warning("fly_to timeout (%.1fs)", timeout_s)
        return False

    async def _wait_until_landed(self, timeout_s: float) -> bool:
        """Poll state.in_air at 2 Hz until False or timeout. Returns True if landed."""
        deadline = time.monotonic() + float(timeout_s)
        while time.monotonic() < deadline:
            if not self.state.in_air:
                return True
            await asyncio.sleep(0.5)
        return not self.state.in_air

    async def _safe_disarm_after_land(self) -> None:
        """Only disarm once telemetry confirms we are on the ground.

        If the initial timeout elapses while still airborne we keep waiting up
        to a hard cap before giving up — disarming a hovering drone is the
        worst possible failure mode here.
        """
        if await self._wait_until_landed(LAND_DISARM_TIMEOUT_S):
            try:
                await self.drone.action.disarm()
            except Exception as exc:
                logger.debug("disarm failed: %s", exc)
            return
        logger.warning(
            "land did not confirm in_air=False within %.0fs — continuing to wait "
            "(hard cap %.0fs) and refusing to disarm while airborne",
            LAND_DISARM_TIMEOUT_S,
            LAND_DISARM_HARD_CAP_S,
        )
        remaining = LAND_DISARM_HARD_CAP_S - LAND_DISARM_TIMEOUT_S
        if remaining > 0 and await self._wait_until_landed(remaining):
            try:
                await self.drone.action.disarm()
            except Exception as exc:
                logger.debug("disarm failed: %s", exc)
            return
        logger.error(
            "drone still reports in_air after %.0fs — NOT disarming (safety)",
            LAND_DISARM_HARD_CAP_S,
        )

    async def emergency_land(self) -> None:
        logger.warning("EMERGENCY LAND")
        self.state.state = "EMERGENCY_LAND"
        try:
            await self._send_velocity(0.0, 0.0, 0.0)
        except Exception:
            pass
        try:
            await self.drone.offboard.stop()
        except Exception as exc:
            logger.debug("offboard.stop failed: %s", exc)
        try:
            await self.drone.action.land()
        except Exception as exc:
            logger.error("action.land failed: %s", exc)
        await self._safe_disarm_after_land()

    # ----- mapping & detection -----
    async def _scan_at_waypoint(self) -> None:
        """Grab N frames, detect ArUco, integrate depth, register sightings."""
        logger.info("scanning at waypoint (%d frames)", FRAMES_PER_WAYPOINT)
        for i in range(FRAMES_PER_WAYPOINT):
            frame = self.realsense.grab()
            if frame is None:
                await asyncio.sleep(0.1)
                continue
            pose = (
                self.state.drone_n,
                self.state.drone_e,
                self.state.drone_down,
                self.state.drone_yaw,
            )
            try:
                self.grid.integrate(frame, pose, self.args.gimbal_pitch)
            except Exception as exc:
                logger.warning("grid integrate failed: %s", exc)
            detections = self.detector.detect_in_frame(frame)
            for aruco_id, pixel_center, bbox in detections:
                self._register_sighting(frame, aruco_id, pixel_center, bbox)
            await asyncio.sleep(0.1)

    def _register_sighting(
        self,
        frame: RealsenseFrame,
        aruco_id: int,
        pixel_center: tuple[int, int],
        bbox: tuple[int, int, int, int],
    ) -> None:
        u, v = pixel_center
        cam_xyz: tuple[float, float, float] | None = None
        world_xyz: tuple[float, float, float] | None = None
        confidence = 0.5
        h, w = frame.depth_mm.shape[:2]
        if 0 <= u < w and 0 <= v < h:
            depth_mm = int(frame.depth_mm[v, u])
            if depth_mm > 0:
                depth_m = depth_mm / 1000.0
                try:
                    cam_xyz = deproject_pixel_to_camera_xyz(
                        frame.intrinsics, u, v, depth_m
                    )
                    world_xyz = camera_to_world(
                        cam_xyz,
                        self.state.drone_n,
                        self.state.drone_e,
                        -self.state.drone_down,
                        self.state.drone_yaw,
                        self.args.gimbal_pitch,
                    )
                    confidence = 1.0
                except Exception as exc:
                    logger.debug("deproject failed for id=%d: %s", aruco_id, exc)

        # dedupe
        if world_xyz is not None:
            for prior in self.sightings:
                if (
                    prior.aruco_id == aruco_id
                    and prior.world_xyz_m is not None
                    and _world_distance(prior.world_xyz_m, world_xyz) < DEDUPE_RADIUS_M
                ):
                    return

        self._sighting_seq += 1
        img_path = None
        try:
            img_path = self.run_writer.save_marker_image(
                frame.color_bgr, aruco_id, self._sighting_seq, bbox_xyxy=bbox
            )
        except Exception as exc:
            logger.warning("save marker image failed: %s", exc)

        sighting = ArucoSighting(
            aruco_id=aruco_id,
            pixel_center=pixel_center,
            bbox_xyxy=bbox,
            cam_xyz_m=cam_xyz,
            world_xyz_m=world_xyz,
            confidence=confidence,
            saved_image_path=img_path,
            first_seen_at=time.monotonic(),
        )
        self.sightings.append(sighting)
        # Decide validity exactly once per id and reuse for both STATUS and JSON.
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
        logger.info(
            "sighting id=%d world=%s valid=%s",
            aruco_id,
            world_xyz,
            valid,
        )

    # ----- top-level mission -----
    async def run_mission(self, waypoints: list[tuple[float, float, float]]) -> None:
        self.state.state = "STARTING"
        self.state.started_at = time.monotonic()

        # background pumps
        self._telem_task = asyncio.create_task(self._telemetry_loop())
        self._attitude_task = asyncio.create_task(self._attitude_loop())
        self._battery_task = asyncio.create_task(self._battery_loop())
        self._in_air_task = asyncio.create_task(self._in_air_loop())
        self._status_task = asyncio.create_task(self._status_writer_loop())

        offboard_started = False
        try:
            # await UWB ready
            self.state.state = "AWAITING_UWB"
            for _ in range(50):
                _, _, ready = self.uwb.get_position()
                if ready:
                    break
                await asyncio.sleep(0.2)
            else:
                logger.warning("UWB not ready after 10s — continuing anyway")

            # health: wait for is_local_position_ok with a 15s timeout.
            # Default is_armable=False (NOT True) when the field is missing —
            # we'd rather refuse to arm than arm blind.
            self.state.state = "AWAITING_HEALTH"
            health_ok = await self._await_health(HEALTH_TIMEOUT_S)
            if not health_ok:
                self.state.aborted = True
                self.state.abort_reason = (
                    f"health check failed within {HEALTH_TIMEOUT_S:.0f}s "
                    "(is_local_position_ok / is_armable)"
                )
                logger.error("aborting before arm: %s", self.state.abort_reason)
                return

            # arm + takeoff
            self.state.state = "ARMING"
            await self.drone.action.arm()
            self.state.state = "TAKEOFF"
            try:
                await self.drone.action.set_takeoff_altitude(TAKEOFF_HEIGHT)
            except Exception:
                pass
            await self.drone.action.takeoff()
            await asyncio.sleep(3.0)

            # offboard pre-warm
            self.state.state = "OFFBOARD_PREWARM"
            await self._offboard_prewarm()
            offboard_started = True

            # mission deadline
            deadline = time.monotonic() + float(self.args.max_flight_time_s)

            self.state.state = "MISSION"
            for idx, (wn, we, walt) in enumerate(waypoints):
                if self._stop_event.is_set() or self.state.aborted:
                    break
                if time.monotonic() > deadline:
                    logger.warning("max flight time reached")
                    self.state.aborted = True
                    self.state.abort_reason = "max_flight_time"
                    break
                logger.info(
                    "WAYPOINT %d/%d -> (%.2f, %.2f, %.2f)",
                    idx + 1, len(waypoints), wn, we, walt,
                )
                reached = await self.fly_to_position_velocity(
                    wn, we, walt, timeout_s=30.0
                )
                if not reached and self.state.aborted:
                    break
                # hover & scan in parallel; hover_for keeps the drone steady
                # while _scan_at_waypoint pulls frames.
                self.state.state = f"SCAN_WP_{idx + 1}"
                scan_task = asyncio.create_task(self._scan_at_waypoint())
                hover_task = asyncio.create_task(self.hover_for(WAYPOINT_PAUSE_S))
                try:
                    await asyncio.wait_for(scan_task, timeout=WAYPOINT_PAUSE_S + 5.0)
                except asyncio.TimeoutError:
                    logger.warning("scan task timed out at waypoint %d", idx + 1)
                    scan_task.cancel()
                    try:
                        await scan_task
                    except (asyncio.CancelledError, Exception):
                        pass
                except Exception as exc:
                    # Realsense.grab() / detector.detect_in_frame() can raise
                    # uncaught hardware/RKNN/OpenCV exceptions. Without this
                    # handler they would escape run_mission, bypass the
                    # emergency_land path, and leave the cancelled scan_task
                    # un-awaited (asyncio warning + half-written file I/O).
                    logger.warning("scan task failed at waypoint %d: %s", idx + 1, exc)
                    if not scan_task.done():
                        scan_task.cancel()
                        try:
                            await scan_task
                        except (asyncio.CancelledError, Exception):
                            pass
                try:
                    await hover_task
                except (asyncio.CancelledError, Exception):
                    pass

            if self.state.aborted:
                # Honour the safety-abort: explicit emergency_land here so we
                # don't fall through to the "normal" land sequence with stale
                # setpoints.
                logger.error(
                    "safety abort detected (%s) — emergency landing",
                    self.state.abort_reason,
                )
                await self.emergency_land()
                return

            # normal landing
            self.state.state = "LANDING"
            try:
                await self._send_velocity(0.0, 0.0, 0.0)
            except Exception:
                pass
        finally:
            # Always stop offboard + land, regardless of how we got here.
            # emergency_land already does both; only do them again if it didn't run.
            if self.state.state != "EMERGENCY_LAND":
                try:
                    if offboard_started:
                        await self.drone.offboard.stop()
                except Exception as exc:
                    logger.debug("offboard.stop failed: %s", exc)
                try:
                    await self.drone.action.land()
                except Exception as exc:
                    logger.warning("land failed: %s", exc)
                await self._safe_disarm_after_land()

            self.state.state = "DONE" if not self.state.aborted else "ABORTED"

            # stop background pumps
            self._stop_event.set()
            for t in (
                self._telem_task,
                self._attitude_task,
                self._battery_task,
                self._in_air_task,
                self._status_task,
            ):
                if t is not None:
                    t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass

    async def _await_health(self, timeout_s: float) -> bool:
        """Wait for is_local_position_ok AND is_armable within timeout_s.

        Missing fields default to FALSE (refuse to arm blind), matching the
        kolomee.py pattern of explicitly checking is_local_position_ok.
        """
        deadline = time.monotonic() + float(timeout_s)
        try:
            async for h in self.drone.telemetry.health():
                local_ok = bool(getattr(h, "is_local_position_ok", False))
                armable = bool(getattr(h, "is_armable", False))
                if local_ok and armable:
                    logger.info("health OK: local_position_ok=%s armable=%s", local_ok, armable)
                    return True
                if time.monotonic() > deadline:
                    logger.warning(
                        "health timeout: local_position_ok=%s armable=%s",
                        local_ok, armable,
                    )
                    return False
                await asyncio.sleep(0.2)
        except Exception as exc:
            logger.warning("health stream failed: %s", exc)
            return False
        return False


def _world_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# ============================================================
# Adapter wiring
# ============================================================
def _build_uwb(args: argparse.Namespace) -> UwbAdapter:
    if args.mock_uwb or args.mock_all:
        node = MockUwbNode()
        node.set_position(0.0, 0.0)
        return node
    return UwbNode()


def _build_realsense(args: argparse.Namespace) -> RealsenseAdapter:
    if args.mock_realsense or args.mock_all:
        return MockRealsenseNode()
    return RealsenseNode()


async def _build_drone(args: argparse.Namespace) -> tuple[Any, Any]:
    if args.mock_mavsdk or args.mock_all:
        drone = MockMavsdk()
        await drone.connect(args.mavsdk_address)
        return drone, _MockVelocityNedYaw
    System, VelocityNedYaw = _load_real_mavsdk()
    drone = System()
    logger.info("connecting MAVSDK to %s", args.mavsdk_address)
    await drone.connect(system_address=args.mavsdk_address)
    # wait for connection
    async for cs in drone.core.connection_state():
        if cs.is_connected:
            logger.info("MAVSDK connected")
            break
    return drone, VelocityNedYaw


def _load_waypoints(path: str | None) -> list[tuple[float, float, float]]:
    if not path:
        return list(DEFAULT_WAYPOINTS)
    data = json.loads(Path(path).read_text())
    out: list[tuple[float, float, float]] = []
    for row in data:
        if len(row) != 3:
            raise ValueError(f"waypoint must be [n, e, alt], got {row}")
        out.append((float(row[0]), float(row[1]), float(row[2])))
    if not out:
        raise ValueError("waypoints file is empty")
    return out


def _setup_logging(level: str, run_dir: Path) -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(lvl)
    for h in list(root.handlers):
        root.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    fh = logging.FileHandler(run_dir / "log.txt")
    fh.setFormatter(fmt)
    root.addHandler(fh)


# ============================================================
# Main entry points
# ============================================================
async def run(args: argparse.Namespace) -> tuple[int, RunWriter | None, "MappingController | None"]:
    """Returns (exit_code, run_writer_or_None, controller_or_None).

    The outer main() needs the RunWriter handle so it can call finalise() even
    on KeyboardInterrupt — which is why we return it instead of swallowing it.
    """
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(args.runs_dir).resolve()
    run_dir = base / f"run_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    _setup_logging(args.log_level, run_dir)
    logger.info("run dir: %s", run_dir)
    logger.info("args: %s", vars(args))
    logger.info("ArUco dictionary: %s", getattr(args, "aruco_dict", "6X6_250"))
    logger.info("validity rule: %s", describe_rule())

    run_writer = RunWriter(run_dir, run_ts)

    # Load waypoints BEFORE acquiring any hardware. A malformed/empty
    # waypoints JSON raises JSONDecodeError / FileNotFoundError / ValueError;
    # doing this early means we fail fast without leaking the UWB rclpy spin
    # thread, Realsense pipeline, or MAVSDK connection.
    waypoints = _load_waypoints(args.waypoints)
    logger.info("waypoints: %s", waypoints)

    uwb = _build_uwb(args)
    realsense = _build_realsense(args)

    try:
        uwb.start()
    except Exception as exc:
        logger.error("uwb start failed: %s", exc)
        return 2, run_writer, None
    try:
        realsense.start()
    except Exception as exc:
        logger.error("realsense start failed: %s", exc)
        uwb.stop()
        return 2, run_writer, None

    try:
        drone, velocity_cls = await _build_drone(args)
    except Exception as exc:
        logger.error("drone connect failed: %s", exc)
        uwb.stop()
        realsense.stop()
        return 2, run_writer, None

    controller = MappingController(args, uwb, realsense, drone, run_writer, velocity_cls)

    # Ctrl-C handling
    loop = asyncio.get_running_loop()
    stop_requested = asyncio.Event()

    def _on_signal() -> None:
        logger.warning("signal received, requesting stop")
        controller.state.stop_requested = True
        try:
            loop.call_soon_threadsafe(stop_requested.set)
        except RuntimeError:
            stop_requested.set()
        controller._stop_event.set()

    # Unix: prefer add_signal_handler. Windows: fall back to signal.signal()
    # for SIGINT so Ctrl-C still routes through our stop path. Note that
    # signal.signal callbacks run in the main thread but we keep the work
    # tiny (just set an asyncio Event via call_soon_threadsafe).
    signal_installed = False
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
            signal_installed = True
        except (NotImplementedError, RuntimeError):
            pass
    if not signal_installed and threading.current_thread() is threading.main_thread():
        def _sig_fallback(_signum, _frame):  # type: ignore[no-untyped-def]
            _on_signal()
        try:
            signal.signal(signal.SIGINT, _sig_fallback)
        except (ValueError, OSError):
            logger.debug("signal.signal(SIGINT) fallback failed", exc_info=True)

    aborted = False
    try:
        mission_task = asyncio.create_task(controller.run_mission(waypoints))
        stop_task = asyncio.create_task(stop_requested.wait())
        done, pending = await asyncio.wait(
            {mission_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if stop_task in done and not mission_task.done():
            logger.warning("user-requested abort — emergency landing")
            aborted = True
            controller.state.aborted = True
            controller.state.abort_reason = "user_interrupt"
            mission_task.cancel()
            try:
                await mission_task
            except (asyncio.CancelledError, Exception):
                pass
            try:
                await controller.emergency_land()
            except Exception as exc:
                logger.error("emergency land failed: %s", exc)
        else:
            stop_task.cancel()
            try:
                await mission_task
            except Exception as exc:
                logger.exception("mission failed: %s", exc)
                aborted = True
                try:
                    await controller.emergency_land()
                except Exception:
                    pass
    finally:
        total_s = (
            time.monotonic() - controller.state.started_at
            if controller.state.started_at > 0
            else 0.0
        )
        try:
            run_writer.finalise(
                controller.grid,
                total_s,
                aborted or controller.state.aborted,
            )
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

    exit_code = 1 if (aborted or controller.state.aborted) else 0
    return exit_code, run_writer, controller


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BrainHack mapping drone controller")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--real", action="store_true", help="use all real hardware (default)")
    mode.add_argument("--mock-all", action="store_true", help="mock UWB, MAVSDK, Realsense")
    p.add_argument("--mock-uwb", action="store_true")
    p.add_argument("--mock-mavsdk", action="store_true")
    p.add_argument("--mock-realsense", action="store_true")
    p.add_argument(
        "--mavsdk-address",
        default="serial:///dev/ttyS6:921600",
        help="MAVSDK system address",
    )
    p.add_argument("--waypoints", default=None, help="JSON file: list of [n_m, e_m, alt_m]")
    p.add_argument(
        "--gimbal-pitch",
        type=float,
        default=-90.0,
        help="degrees; -90=straight down (canonical for top-down mapping)",
    )
    p.add_argument(
        "--aruco-dict",
        default="6X6_250",
        help="ArUco dictionary name (e.g. 6X6_250, 4X4_50)",
    )
    p.add_argument("--max-flight-time-s", type=int, default=240)
    p.add_argument(
        "--runs-dir",
        default="mapping_drone/runs",
        help="parent directory for run_<ts> output dirs (relative to CWD; "
             "operators running from the repo root can override with --runs-dir)",
    )
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args(argv)
    if not (args.real or args.mock_all or args.mock_uwb or args.mock_mavsdk or args.mock_realsense):
        args.real = True
    return args


def main() -> int:
    args = _parse_args()
    # We wrap asyncio.run() so a KeyboardInterrupt that escapes the inner
    # signal-handling path still gives us a chance to call run_writer.finalise()
    # and leave a coherent run_<ts>/ artifact directory behind.
    result_box: dict[str, Any] = {"code": 130, "writer": None, "controller": None}

    async def _outer() -> None:
        code, writer, controller = await run(args)
        result_box["code"] = code
        result_box["writer"] = writer
        result_box["controller"] = controller

    def _best_effort_finalise(box: dict[str, Any]) -> None:
        """Run RunWriter.finalise() best-effort from an outer exception path.

        Called when an exception (KeyboardInterrupt or any unexpected error)
        escapes asyncio.run() and bypasses run()'s own finally block. If the
        writer was never built (early failure in waypoints/RunWriter/UWB
        construction) box["writer"] is None and we silently skip.
        """
        writer = box.get("writer")
        controller = box.get("controller")
        if writer is None:
            return
        try:
            total_s = 0.0
            aborted_flag = True
            grid: Any = None
            if controller is not None:
                if controller.state.started_at > 0:
                    total_s = time.monotonic() - controller.state.started_at
                aborted_flag = bool(
                    controller.state.aborted or controller.state.stop_requested
                )
                grid = controller.grid
            if grid is None:
                grid = OccupancyGrid(resolution_m=0.05, size_m=20.0)
            writer.finalise(grid, total_s, aborted_flag)
        except Exception:
            logger.exception("best-effort finalise failed")

    try:
        asyncio.run(_outer())
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt at top level — attempting best-effort finalise")
        _best_effort_finalise(result_box)
        return 130
    except Exception:
        # Any unguarded exception that escapes run() (e.g. _load_waypoints
        # ValueError on empty file, ImportError from _load_real_mavsdk,
        # unexpected crash in _build_drone) would otherwise dump a raw
        # traceback and skip finalise. Log it cleanly and still try to leave
        # a coherent run_<ts>/ directory behind.
        logger.exception("run() raised an unhandled exception — attempting best-effort finalise")
        _best_effort_finalise(result_box)
        return 1
    return int(result_box.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
