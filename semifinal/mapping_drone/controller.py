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
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from .mapping import (
    ArucoDetector,
    ArucoSighting,
    OccupancyGrid,
    camera_to_world,
    _normalize_dict_name,
)
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

# ============================================================
# Verbose dispatch + Tailscale log broadcast
# ============================================================
# Module-level toggle set by _parse_args / _setup_logging when --verbose is on.
# Used by _vinfo() below to promote "silent-but-useful" lines from DEBUG to
# INFO without flipping the entire root logger to DEBUG (which would also
# surface every third-party library DEBUG and drown the run log).
_VERBOSE = False


def _vinfo(msg: str, *args: Any) -> None:
    """Log at INFO when --verbose, DEBUG otherwise.

    Used for the hot-path lines (per-frame, per-tick, per-velocity-command,
    per-WP arrival distance) that are too chatty for the normal INFO floor
    but are exactly what we want during a Day-1 debugging session. Routed
    through this single dispatcher so the verbose level can be flipped from
    one place without rewriting call sites.
    """
    if _VERBOSE:
        logger.info(msg, *args)
    else:
        logger.debug(msg, *args)


class TailscaleHandler(logging.Handler):
    """logging.Handler that POSTs each formatted record to a log_sink URL.

    Matches the pre-existing tools/log_broadcaster/wrap.sh contract: POSTs
    the line as the request body to ``http://<host>:<port>/<tag>``. The
    receiving log_sink.py appends to D:/hackerverse/laptop_logs/<tag>.log.

    Failures are silently swallowed (the sink may be unreachable mid-flight
    over flaky wifi) — but a one-shot INFO line is emitted on the FIRST
    failure so the operator knows the broadcast isn't landing. Subsequent
    failures stay silent to avoid log spam.

    Uses stdlib urllib.request only — no `requests` dependency. Per-POST
    timeout is hard-coded to 2 s so a wedged sink can never block the
    controller's main thread for more than a tick.
    """

    POST_TIMEOUT_S = 2.0

    def __init__(self, host: str, tag: str) -> None:
        super().__init__()
        # Normalise: accept '100.x.y.z:9999' or '100.x.y.z' (default port).
        if ":" in host:
            self._host = host
        else:
            self._host = f"{host}:9999"
        self._tag = tag
        self._url = f"http://{self._host}/{self._tag}"
        self._failed_once = False

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            req = urllib.request.Request(
                self._url,
                data=line.encode("utf-8", errors="replace"),
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.POST_TIMEOUT_S):
                    pass
            except (urllib.error.URLError, OSError, TimeoutError):
                if not self._failed_once:
                    self._failed_once = True
                    # NOTE: we log via the module logger (which still has
                    # the stdout + file handlers) but bypass ourselves —
                    # otherwise a sink that's down would itself try to POST
                    # the "sink unreachable" line and recurse the failure.
                    logger.info(
                        "tailscale log sink unreachable at %s — "
                        "swallowing further POST errors silently",
                        self._url,
                    )
        except Exception:
            # Last-ditch swallow: a logging.Handler must NEVER raise out of
            # emit() or it can take down the controller thread.
            self.handleError(record)


# Velocity controller gains (carry-over from kolomee.py)
KP_XY = 0.1
KP_Z = 0.1
# Org rule (finals brief slide 5): mapping drone max horizontal speed is
# 0.3 m/s. We hard-cap the runtime value below this and refuse to honour any
# CLI override that exceeds it. kolomee.py's original 0.5 was the per-vehicle
# safe ceiling, not the assessment cap.
MAX_VEL_XY_HARD_CAP = 0.3
MAX_VEL_XY = MAX_VEL_XY_HARD_CAP
MAX_VEL_Z = 0.3
MAX_HOVER_XY = 0.15
HOVER_DEADBAND = 0.03
N_THRESHOLD = 0.1
E_THRESHOLD = 0.1
D_THRESHOLD = 0.1
LOOP_HZ = 10.0
# kolomee.py shipped 0.8 m, but the finals brief (slide 5, 2026-06-08) sets a
# 3.5 m minimum flight height for the mapping drone. action.takeoff() at 0.8 m
# followed by the offboard prewarm hover left the drone ~14 s under the floor
# while climbing at the 0.3 m/s cap. Push the PX4 takeoff target above the
# floor so the only sub-floor time is the few seconds it physically takes the
# vehicle to climb to TAKEOFF_HEIGHT after arming.
TAKEOFF_HEIGHT = 3.6

# Safety thresholds
UWB_LOSS_GRACE_S = 1.0
UWB_LOSS_LAND_S = 5.0
UWB_NEVER_FIX_GRACE_S = 8.0  # extra grace after takeoff for first ever UWB fix
STUCK_GRACE_S = 10.0
# Worst-case fly_to leg at the 0.3 m/s org cap (slide 5) over 2 m is ~6.7 s,
# plus per-waypoint scan dwell (~15 s). Window must be wider than scan dwell +
# one fly_to so a fresh fly_to is not pre-loaded with the previous scan's hover
# samples. 30 s gives margin without making real stalls invisible.
STUCK_WINDOW_S = 30.0
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
    (0.0, 0.0, 4.0),
    (2.0, 0.0, 4.0),
    (2.0, 2.0, 4.0),
    (0.0, 2.0, 4.0),
]

# Day-1 MAVSDK address fallback order. Tried in sequence when the operator
# passes --mavsdk-addresses (or its default). Covers the three serial ports
# we've seen the PX4 enumerate as across boots (ttyS6 / ttyACM0 / ttyUSB0)
# plus the standard SITL UDP ports so a bench laptop with jMAVSim or PX4 SITL
# also connects without flags.
DAY1_MAVSDK_TRY_ORDER = [
    "serial:///dev/ttyS6:921600",
    "serial:///dev/ttyACM0:115200",
    "serial:///dev/ttyUSB0:57600",
    "udp://:14540",
    "udp://:14550",
]

# Per-address connect timeout used by the fallback walker. Short enough that
# cycling through all 5 entries on a totally dead bus still completes inside
# the operator's patience budget (~25 s worst case).
MAVSDK_CONNECT_TIMEOUT_S = 5.0

# Trip the safety-abort path after this many CONSECUTIVE set_velocity_ned()
# failures. A handful of transient raises (mock or real PX4 backpressure) is
# fine and shouldn't kill a clean run; a sustained streak almost always means
# offboard has dropped and continuing to push setpoints is unsafe.
CONSECUTIVE_VELOCITY_FAIL_ABORT_THRESHOLD = 5


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
    # Counter incremented on every consecutive set_velocity_ned() raise; reset
    # to zero on the next successful call. When it hits
    # CONSECUTIVE_VELOCITY_FAIL_ABORT_THRESHOLD we trip the safety-abort path.
    consecutive_velocity_failures: int = 0


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

        # Resolve effective horizontal-speed cap. The org caps the mapping drone
        # at 0.3 m/s (finals brief slide 5); we hard-clamp anything above that
        # and log at INFO so the run log carries the cap on the record. Anything
        # at or below the cap is honoured as-is (operators may want a slower
        # value for low-clearance test flights).
        requested = float(getattr(args, "max_vel_xy", MAX_VEL_XY_HARD_CAP))
        if requested > MAX_VEL_XY_HARD_CAP:
            logger.info(
                "max_vel_xy=%.2f m/s exceeds org cap %.2f m/s — clamping to %.2f m/s",
                requested, MAX_VEL_XY_HARD_CAP, MAX_VEL_XY_HARD_CAP,
            )
            self.max_vel_xy = MAX_VEL_XY_HARD_CAP
        else:
            self.max_vel_xy = requested
        logger.info("horizontal speed cap: %.2f m/s (org max %.2f m/s)",
                    self.max_vel_xy, MAX_VEL_XY_HARD_CAP)

        self.state = FlightState()
        aruco_dict = getattr(args, "aruco_dict", "6X6_250")
        self.detector = ArucoDetector(dict_name=aruco_dict)
        self.grid = OccupancyGrid(resolution_m=0.05, size_m=20.0)
        self.sightings: list[ArucoSighting] = []
        # Cache: aruco_id -> validity, decided at FIRST sighting. Ensures
        # STATUS.txt and landing_pads.json never disagree even if the rule
        # behaviour changes (e.g., env var flipped mid-run). Value is None
        # when the active rule (e.g. 'lookup' with an unknown id) cannot
        # classify the marker — callers treat None and False the same when
        # rendering, but we preserve the distinction here so downstream code
        # can tell "unknown" apart from "explicitly invalid".
        self._validity_cache: dict[int, Optional[bool]] = {}
        self._sighting_seq = 0
        self._stop_event = asyncio.Event()
        self._telem_task: asyncio.Task | None = None
        self._attitude_task: asyncio.Task | None = None
        self._battery_task: asyncio.Task | None = None
        self._in_air_task: asyncio.Task | None = None
        self._status_task: asyncio.Task | None = None
        self._is_mock_drone = isinstance(drone, MockMavsdk)

    # ----- state-transition helper -----
    def _set_state(self, new_state: str) -> None:
        """Assign self.state.state and log the transition when --verbose.

        Centralises every controller state hop so --verbose surfaces the
        progression (INIT -> STARTING -> AWAITING_UWB -> AWAITING_HEALTH ->
        ARMING -> ...) at INFO without having to instrument each call site
        twice.
        """
        prev = self.state.state
        self.state.state = new_state
        if prev != new_state:
            _vinfo("state: %s -> %s", prev, new_state)

    # ----- validity helper -----
    def _validity_for(self, aruco_id: int) -> Optional[bool]:
        """Return cached validity, populating on first sighting.

        Returns True/False when the active rule can classify the id, or
        None when the rule (currently only ``lookup``) doesn't know the id.
        Do NOT wrap in bool() — that would silently collapse the
        "unknown" outcome into "invalid" and hide lookup-table gaps.
        """
        aid = int(aruco_id)
        if aid in self._validity_cache:
            return self._validity_cache[aid]
        decided = decide_landing_validity(aid)
        self._validity_cache[aid] = decided
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
                    _vinfo("uwb tick: n=%.3f e=%.3f (ready)", n, e)
                else:
                    _vinfo("uwb tick: no data (down_m=%.3f)",
                           self.state.drone_down)
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
        # Also skip during SCAN_WP_* states: those phases hover by design,
        # and counting them would flag legitimate scans as stuck.
        if (
            self.state.airborne_at > 0
            and now - self.state.airborne_at > STUCK_GRACE_S
            and not self.state.state.startswith("SCAN_WP_")
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
        _vinfo(
            "vel cmd: vn=%.3f ve=%.3f vd=%.3f yaw=%.1f",
            vn, ve, vd, yaw_deg,
        )
        try:
            await self.drone.offboard.set_velocity_ned(
                self.VelocityNedYaw(vn, ve, vd, yaw_deg)
            )
        except Exception as exc:
            self.state.consecutive_velocity_failures += 1
            logger.warning(
                "set_velocity_ned failed (%d/%d consecutive): %s",
                self.state.consecutive_velocity_failures,
                CONSECUTIVE_VELOCITY_FAIL_ABORT_THRESHOLD,
                exc,
            )
            if (
                self.state.consecutive_velocity_failures
                >= CONSECUTIVE_VELOCITY_FAIL_ABORT_THRESHOLD
                and not self.state.aborted
            ):
                self.state.aborted = True
                self.state.abort_reason = (
                    f"set_velocity_ned repeated failures "
                    f"(N={CONSECUTIVE_VELOCITY_FAIL_ABORT_THRESHOLD})"
                )
                logger.error(
                    "tripping safety-abort: %s", self.state.abort_reason
                )
            return
        # success path — clear the streak
        self.state.consecutive_velocity_failures = 0

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
            _vinfo(
                "wp arrival check: dn=%.3f de=%.3f dd=%.3f (thr %.2f/%.2f/%.2f)",
                err_n, err_e, err_d,
                N_THRESHOLD, E_THRESHOLD, D_THRESHOLD,
            )
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
            vn = max(-self.max_vel_xy, min(self.max_vel_xy, err_n * KP_XY * 5.0))
            ve = max(-self.max_vel_xy, min(self.max_vel_xy, err_e * KP_XY * 5.0))
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
        if getattr(self.args, "nofly", False):
            # Never armed in no-fly mode — issuing land/offboard.stop against a
            # grounded, disarmed PX4 would only log spurious errors.
            logger.info("no-fly mode: emergency-land is a no-op (drone never armed)")
            return
        logger.warning("EMERGENCY LAND")
        self._set_state("EMERGENCY_LAND")
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
        """Grab N frames, detect ArUco, integrate depth, register sightings.

        Each frame's grab / detect / integrate is offloaded via
        asyncio.to_thread because RealsenseNode.grab() blocks for up to 2 s on
        pipeline.wait_for_frames and the OpenCV ArUco + numpy integrate calls
        can spend tens of milliseconds on the venue depth resolution. Running
        them inline would starve the position-stuck watchdog and STATUS pump
        for up to FRAMES_PER_WAYPOINT * grab_timeout per waypoint on --real.
        Mock paths still pay the to_thread hop but it is cheap.
        """
        logger.info("scanning at waypoint (%d frames)", FRAMES_PER_WAYPOINT)
        for i in range(FRAMES_PER_WAYPOINT):
            frame = await asyncio.to_thread(self.realsense.grab)
            if frame is None:
                _vinfo("scan frame %d/%d: realsense grab returned None",
                       i + 1, FRAMES_PER_WAYPOINT)
                await asyncio.sleep(0.1)
                continue
            pose = (
                self.state.drone_n,
                self.state.drone_e,
                self.state.drone_down,
                self.state.drone_yaw,
            )
            try:
                await asyncio.to_thread(
                    self.grid.integrate, frame, pose, self.args.gimbal_pitch
                )
            except Exception as exc:
                logger.warning("grid integrate failed: %s", exc)
            detections = await asyncio.to_thread(self.detector.detect_in_frame, frame)
            _vinfo(
                "scan frame %d/%d: grabbed OK, %d detections",
                i + 1, FRAMES_PER_WAYPOINT, len(detections),
            )
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

    # ----- no-flight bench mode -----
    async def _run_nofly(self, waypoints: list[tuple[float, float, float]]) -> None:
        """Bench mode: sensing + detection + mapping + artifacts, never moves.

        Starts the same background telemetry/UWB/status pumps as a real
        mission so STATUS.txt and the pose used for deprojection are live,
        then loops ``_scan_at_waypoint`` in place until --max-flight-time-s
        elapses or Ctrl-C. It NEVER calls action.arm/takeoff/land or
        offboard.start/set_velocity_ned/set_position_ned, so the drone cannot
        leave the ground. ``waypoints`` is accepted for signature parity but
        is intentionally unused — a grounded drone cannot fly to them.
        """
        logger.info(
            "NO-FLY MODE: subsystems + scan/detect/map pipeline only. The drone "
            "will NOT arm, take off, go offboard, move, or land. World coords are "
            "not physically meaningful at ground level — this validates detection "
            "+ artifact writing, not navigation."
        )
        self._set_state("STARTING")
        self.state.started_at = time.monotonic()

        self._telem_task = asyncio.create_task(self._telemetry_loop())
        self._attitude_task = asyncio.create_task(self._attitude_loop())
        self._battery_task = asyncio.create_task(self._battery_loop())
        self._in_air_task = asyncio.create_task(self._in_air_loop())
        self._status_task = asyncio.create_task(self._status_writer_loop())

        try:
            self._set_state("AWAITING_UWB")
            for _ in range(50):
                _, _, ready = self.uwb.get_position()
                if ready:
                    break
                await asyncio.sleep(0.2)
            else:
                logger.warning("UWB not ready after 10s — continuing anyway (no-fly)")

            deadline = time.monotonic() + float(self.args.max_flight_time_s)
            self._set_state("NOFLY_SCAN")
            cycle = 0
            while not self._stop_event.is_set() and not self.state.aborted:
                if time.monotonic() > deadline:
                    logger.info(
                        "no-fly: scan duration reached (%.0fs)",
                        float(self.args.max_flight_time_s),
                    )
                    break
                cycle += 1
                _vinfo("no-fly scan cycle %d", cycle)
                try:
                    await self._scan_at_waypoint()
                except Exception as exc:
                    logger.warning("no-fly scan cycle %d failed: %s", cycle, exc)
                await asyncio.sleep(0.2)
        finally:
            self._set_state("DONE" if not self.state.aborted else "ABORTED")
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

    # ----- top-level mission -----
    async def run_mission(self, waypoints: list[tuple[float, float, float]]) -> None:
        if getattr(self.args, "nofly", False):
            await self._run_nofly(waypoints)
            return
        self._set_state("STARTING")
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
            self._set_state("AWAITING_UWB")
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
            self._set_state("AWAITING_HEALTH")
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
            self._set_state("ARMING")
            await self.drone.action.arm()
            self._set_state("TAKEOFF")
            try:
                await self.drone.action.set_takeoff_altitude(TAKEOFF_HEIGHT)
            except Exception:
                pass
            await self.drone.action.takeoff()
            await asyncio.sleep(3.0)

            # offboard pre-warm
            self._set_state("OFFBOARD_PREWARM")
            await self._offboard_prewarm()
            offboard_started = True

            # mission deadline
            deadline = time.monotonic() + float(self.args.max_flight_time_s)

            self._set_state("MISSION")
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
                self._set_state(f"SCAN_WP_{idx + 1}")
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
            self._set_state("LANDING")
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

            self._set_state("DONE" if not self.state.aborted else "ABORTED")

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


def _resolve_mavsdk_addresses(args: argparse.Namespace) -> list[str]:
    """Build the ordered address list the connector should try.

    --mavsdk-addresses (comma-separated list) wins over --mavsdk-address when
    BOTH are present. When neither is provided, falls back to the single
    --mavsdk-address default (preserving the back-compat single-address
    behaviour for existing scripts and the operator runbook).
    """
    raw = getattr(args, "mavsdk_addresses", None)
    if raw:
        addrs = [a.strip() for a in str(raw).split(",") if a.strip()]
        if addrs:
            return addrs
    return [args.mavsdk_address]


async def _connect_with_fallback(
    drone: Any,
    addresses: list[str],
    per_addr_timeout_s: float,
) -> str:
    """Try each address in order with a per-attempt connect timeout.

    Returns the address that successfully connected. Raises RuntimeError if
    every address failed (either by raising or by failing to report
    is_connected within the timeout).
    """
    last_exc: Exception | None = None
    for addr in addresses:
        logger.info("MAVSDK connect attempt: %s (timeout %.1fs)", addr, per_addr_timeout_s)
        try:
            await asyncio.wait_for(
                drone.connect(system_address=addr), timeout=per_addr_timeout_s
            )
        except asyncio.TimeoutError:
            logger.warning("MAVSDK connect timed out for %s", addr)
            continue
        except Exception as exc:
            logger.warning("MAVSDK connect raised for %s: %s", addr, exc)
            last_exc = exc
            continue

        # connect() returned — now wait (also bounded) for is_connected.
        try:
            async def _await_connected() -> None:
                async for cs in drone.core.connection_state():
                    if cs.is_connected:
                        return
            await asyncio.wait_for(_await_connected(), timeout=per_addr_timeout_s)
        except asyncio.TimeoutError:
            logger.warning("MAVSDK is_connected timed out for %s", addr)
            continue
        except Exception as exc:
            logger.warning("MAVSDK connection_state raised for %s: %s", addr, exc)
            last_exc = exc
            continue

        logger.info("connected via %s", addr)
        return addr

    if last_exc is not None:
        raise RuntimeError(
            f"MAVSDK failed to connect via any of {addresses}: last error {last_exc!r}"
        )
    raise RuntimeError(f"MAVSDK failed to connect via any of {addresses}")


async def _build_drone(args: argparse.Namespace) -> tuple[Any, Any]:
    addresses = _resolve_mavsdk_addresses(args)
    if args.mock_mavsdk or args.mock_all:
        drone = MockMavsdk()
        # In mock mode we still honour the fallback list by walking it once
        # for the log trail, but every mock connect succeeds — so we just
        # connect to the first and log which one "won".
        first = addresses[0]
        await drone.connect(first)
        logger.info("connected via %s", first)
        return drone, _MockVelocityNedYaw
    System, VelocityNedYaw = _load_real_mavsdk()
    drone = System()
    if len(addresses) == 1:
        # Preserve original single-address behaviour exactly: one connect
        # call, then drain connection_state until is_connected (no timeout).
        # This keeps back-compat for scripts that rely on the old
        # --mavsdk-address path and want to block indefinitely on a flaky bus.
        addr = addresses[0]
        logger.info("connecting MAVSDK to %s", addr)
        await drone.connect(system_address=addr)
        async for cs in drone.core.connection_state():
            if cs.is_connected:
                logger.info("MAVSDK connected")
                logger.info("connected via %s", addr)
                break
        return drone, VelocityNedYaw
    # Multi-address path: try each with a bounded timeout.
    await _connect_with_fallback(drone, addresses, MAVSDK_CONNECT_TIMEOUT_S)
    return drone, VelocityNedYaw


def _parse_waypoints_json(data: Any, source_label: str) -> list[tuple[float, float, float]]:
    """Validate a decoded list-of-3-tuples payload from ``source_label``."""
    if not isinstance(data, list):
        raise ValueError(
            f"{source_label}: expected a JSON list, got {type(data).__name__}"
        )
    out: list[tuple[float, float, float]] = []
    for row in data:
        if len(row) != 3:
            raise ValueError(f"{source_label}: waypoint must be [n, e, alt], got {row}")
        out.append((float(row[0]), float(row[1]), float(row[2])))
    if not out:
        raise ValueError(f"{source_label}: waypoints list is empty")
    return out


def _load_waypoints(
    inline_path: str | None,
    from_json_path: str | None = None,
) -> tuple[list[tuple[float, float, float]], str]:
    """Resolve the active waypoint list and report the source.

    Fallback chain:
        --waypoints (inline_path) > --waypoints-from-json (from_json_path)
        > DEFAULT_WAYPOINTS

    Returns ``(waypoints, source_label)`` so the caller can log which source
    actually supplied the list.
    """
    if inline_path:
        data = json.loads(Path(inline_path).read_text())
        label = f"--waypoints {inline_path}"
        return _parse_waypoints_json(data, label), label
    if from_json_path:
        data = json.loads(Path(from_json_path).read_text())
        label = f"--waypoints-from-json {from_json_path}"
        return _parse_waypoints_json(data, label), label
    return list(DEFAULT_WAYPOINTS), "DEFAULT_WAYPOINTS"


def _setup_logging(
    level: str,
    run_dir: Path,
    *,
    verbose: bool = False,
    tailscale: bool = False,
    tailscale_host: str = "100.79.202.101:9999",
    tailscale_tag: str | None = None,
    run_ts: str = "",
) -> tuple[logging.FileHandler, Optional[TailscaleHandler]]:
    """Configure root logger and attach a FileHandler at ``run_dir/log.txt``.

    Returns ``(file_handler, tailscale_handler_or_None)`` so the caller can
    close + remove both in a finally block. Without that, Windows keeps the
    log.txt file open and any later attempt to tear down the run dir (e.g.
    tempfile.TemporaryDirectory cleanup in smoke tests) fails with
    PermissionError [WinError 32].

    When ``verbose`` is True we flip the module-level ``_VERBOSE`` flag so
    ``_vinfo()`` calls promote to INFO. We deliberately do NOT lower the
    root level to DEBUG — that would also pull in third-party DEBUG noise
    (pyrealsense2 / rclpy / asyncio) and bury the signal we actually want.

    When ``tailscale`` is True we also attach a TailscaleHandler that POSTs
    each formatted record to the desktop log_sink. Uses the same on-disk
    format as the file handler so a sink-side log file is byte-identical to
    log.txt (modulo the sink's own timestamp prefix).
    """
    global _VERBOSE
    _VERBOSE = bool(verbose)

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

    th: Optional[TailscaleHandler] = None
    if tailscale:
        tag = tailscale_tag or f"mapping-drone-{run_ts or 'unknown'}"
        th = TailscaleHandler(tailscale_host, tag)
        th.setFormatter(fmt)
        root.addHandler(th)
        logger.info(
            "tailscale broadcast ON: posting log lines to http://%s/%s",
            th._host, th._tag,
        )
    return fh, th


# ============================================================
# Dry-run health probe
# ============================================================
async def _dry_run(args: argparse.Namespace) -> int:
    """Bring up MAVSDK + UWB + Realsense, log per-subsystem health, tear down.

    Honours --mock-* flags so a bench laptop with no hardware can still smoke
    the wiring via ``--dry-run --mock-all``. Never arms, never moves the drone.
    Returns 0 if all three subsystems came up cleanly, 2 if any failed.
    """
    _configure_stream_logging(args.log_level)
    failures: list[str] = []

    # MAVSDK. We don't keep the System() handle — MAVSDK exposes no explicit
    # close on the object we use, so successfully reaching this point is the
    # health signal we care about.
    try:
        await _build_drone(args)
        logger.info("DRY-RUN: MAVSDK OK")
    except Exception as exc:
        logger.error("DRY-RUN: MAVSDK FAILED: %s", exc)
        failures.append("mavsdk")

    # UWB
    uwb: UwbAdapter | None = None
    try:
        uwb = _build_uwb(args)
        uwb.start()
        logger.info("DRY-RUN: UWB OK")
    except Exception as exc:
        logger.error("DRY-RUN: UWB FAILED: %s", exc)
        failures.append("uwb")
        uwb = None

    # Realsense
    realsense: RealsenseAdapter | None = None
    try:
        realsense = _build_realsense(args)
        realsense.start()
        logger.info("DRY-RUN: Realsense OK")
    except Exception as exc:
        logger.error("DRY-RUN: Realsense FAILED: %s", exc)
        failures.append("realsense")
        realsense = None

    # Teardown (best-effort). MAVSDK has no explicit close on the System
    # object we use; UWB + Realsense expose stop().
    if realsense is not None:
        try:
            realsense.stop()
        except Exception:
            logger.debug("DRY-RUN: realsense.stop() raised", exc_info=True)
    if uwb is not None:
        try:
            uwb.stop()
        except Exception:
            logger.debug("DRY-RUN: uwb.stop() raised", exc_info=True)

    if failures:
        logger.error("DRY-RUN: incomplete — failures: %s", ",".join(failures))
        return 2
    logger.info("DRY-RUN: all subsystems OK")
    return 0


def _configure_stream_logging(level: str) -> None:
    """Stream-only logging for the dry-run path (no run_<ts>/log.txt)."""
    lvl = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(lvl)
    # Avoid stacking handlers if dry-run is invoked repeatedly in-process.
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)


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
    log_handler, ts_handler = _setup_logging(
        args.log_level,
        run_dir,
        verbose=getattr(args, "verbose", False),
        tailscale=getattr(args, "tailscale", False),
        tailscale_host=getattr(args, "tailscale_host", "100.79.202.101:9999"),
        tailscale_tag=getattr(args, "tailscale_tag", None),
        run_ts=run_ts,
    )
    # Wrap the entire run body so the FileHandler is always closed +
    # removed, even on early returns or unhandled exceptions. Leaving it
    # open is fine on POSIX but Windows pins the file and any later
    # rmtree() of run_dir (notably tempfile.TemporaryDirectory in the
    # smoke tests) raises PermissionError [WinError 32].
    try:
        logger.info("run dir: %s", run_dir)
        logger.info("args: %s", vars(args))
        _raw_dict = getattr(args, "aruco_dict", "6X6_250")
        try:
            _norm_dict = _normalize_dict_name(_raw_dict)
        except Exception:
            _norm_dict = _raw_dict
        if _norm_dict == _raw_dict:
            logger.info("ArUco dictionary: %s", _norm_dict)
        else:
            logger.info("ArUco dictionary: %s (normalized from %r)", _norm_dict, _raw_dict)
        logger.info("validity rule: %s", describe_rule())

        run_writer = RunWriter(run_dir, run_ts)

        # Load waypoints BEFORE acquiring any hardware. A malformed/empty
        # waypoints JSON raises JSONDecodeError / FileNotFoundError / ValueError;
        # doing this early means we fail fast without leaking the UWB rclpy spin
        # thread, Realsense pipeline, or MAVSDK connection. We catch the failure
        # here (rather than letting it escape to _outer / _best_effort_finalise)
        # so that the just-constructed run_writer always gets a finalise() call
        # — otherwise result_box["writer"] stays None and the run_<ts>/ dir is
        # left as orphan-with-STATUS-seed-only.
        try:
            waypoints, waypoints_source = _load_waypoints(
                args.waypoints, getattr(args, "waypoints_from_json", None)
            )
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            logger.error("waypoints load failed: %s", exc)
            try:
                run_writer.finalise(
                    OccupancyGrid(resolution_m=0.05, size_m=20.0),
                    0.0,
                    aborted=True,
                    abort_reason=f"waypoints load failed: {exc!r}",
                )
            except Exception:
                logger.exception("finalise after waypoints-load failure raised")
            return 2, run_writer, None
        logger.info("waypoints source: %s", waypoints_source)
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
                    # Record a meaningful reason if the mission task raised
                    # before any deeper abort path got a chance to set one.
                    if not controller.state.abort_reason:
                        controller.state.abort_reason = (
                            f"mission task exception: {exc!r}"
                        )
                    if not controller.state.aborted:
                        controller.state.aborted = True
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
                    abort_reason=controller.state.abort_reason or None,
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
    finally:
        # Release the FileHandler so Windows lets go of log.txt. Catch all
        # errors so a logging-teardown failure never masks the real result.
        try:
            log_handler.close()
        except Exception:
            pass
        try:
            logging.getLogger().removeHandler(log_handler)
        except Exception:
            pass
        # Also detach the tailscale handler if we attached one. urllib has
        # no persistent connection to close but we still want the handler
        # off the root logger so a second in-process run (e.g. pytest
        # suite) doesn't double-post.
        if ts_handler is not None:
            try:
                ts_handler.close()
            except Exception:
                pass
            try:
                logging.getLogger().removeHandler(ts_handler)
            except Exception:
                pass


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BrainHack mapping drone controller")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--real", action="store_true", help="use all real hardware (default)")
    mode.add_argument(
        "--mock",
        "--mock-all",
        dest="mock_all",
        action="store_true",
        help="mock UWB, MAVSDK, Realsense (--mock and --mock-all are aliases)",
    )
    p.add_argument("--mock-uwb", action="store_true")
    p.add_argument("--mock-mavsdk", action="store_true")
    p.add_argument("--mock-realsense", action="store_true")
    p.add_argument(
        "--mavsdk-address",
        default="serial:///dev/ttyS6:921600",
        help="MAVSDK system address (single). Used when --mavsdk-addresses "
             "is not supplied. Preserves original blocking-connect semantics.",
    )
    p.add_argument(
        "--mavsdk-addresses",
        default=None,
        help="Comma-separated list of MAVSDK system addresses to try in order "
             "with a %.1fs per-address connect timeout. Wins over "
             "--mavsdk-address when both are present. Logs each attempt and "
             "'connected via <addr>' on success. Example: "
             "'serial:///dev/ttyS6:921600,serial:///dev/ttyACM0:115200,"
             "udp://:14540'. See DAY1_MAVSDK_TRY_ORDER for the canonical "
             "Day-1 list." % MAVSDK_CONNECT_TIMEOUT_S,
    )
    p.add_argument("--waypoints", default=None, help="JSON file: list of [n_m, e_m, alt_m]")
    p.add_argument(
        "--waypoints-from-json",
        default=None,
        help="JSON file: list of [n_m, e_m, alt_m]. Used only when --waypoints "
             "is not supplied; ignored otherwise. Fallback chain: --waypoints "
             "> --waypoints-from-json > DEFAULT_WAYPOINTS.",
    )
    p.add_argument(
        "--gimbal-pitch",
        type=float,
        default=-90.0,
        help="degrees; -90=straight down (canonical for top-down mapping)",
    )
    p.add_argument(
        "--aruco-dict",
        default="7X7_1000",
        help="ArUco dictionary name (org markers are 7X7_1000; e.g. 6X6_250, 4X4_50)",
    )
    p.add_argument(
        "--max-vel-xy",
        type=float,
        default=MAX_VEL_XY_HARD_CAP,
        help="horizontal-speed cap in m/s. Org rule (finals brief slide 5) is "
             "0.3 m/s for the mapping drone — values above %.2f m/s are "
             "hard-clamped at runtime and logged at INFO." % MAX_VEL_XY_HARD_CAP,
    )
    # Org rule (finals brief slide 5): max 8 min (480 s) per Challenge 1
    # attempt. Default sits 60 s under that ceiling so the per-attempt timeout
    # never elbows the org's own clock.
    p.add_argument("--max-flight-time-s", type=int, default=420)
    p.add_argument(
        "--runs-dir",
        default="mapping_drone/runs",
        help="parent directory for run_<ts> output dirs (relative to CWD; "
             "operators running from the repo root can override with --runs-dir)",
    )
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Promote silent-but-useful hot-path lines (per-frame scan result, "
             "per-UWB tick, per-velocity command, per-WP arrival distance, "
             "every state transition) from DEBUG to INFO. Does NOT lower the "
             "root level to DEBUG — keeps third-party noise out of the log.",
    )
    p.add_argument(
        "--tailscale",
        action="store_true",
        help="Also POST every log line to the desktop log_sink over Tailscale "
             "(matches tools/log_broadcaster/wrap.sh). Defaults to host "
             "100.79.202.101:9999 and tag mapping-drone-<run_ts>. Errors are "
             "swallowed (the sink may be unreachable mid-flight); a one-shot "
             "INFO line is emitted on the first POST failure.",
    )
    p.add_argument(
        "--tailscale-host",
        default="100.79.202.101:9999",
        help="<host>[:<port>] override for the log_sink endpoint (default "
             "100.79.202.101:9999, the desktop tailnet IP). Only used when "
             "--tailscale is set.",
    )
    p.add_argument(
        "--tailscale-tag",
        default=None,
        help="Override the log_sink tag (=log file basename). Default is "
             "'mapping-drone-<run_ts>' so each run is its own log file on the "
             "sink. Only used when --tailscale is set.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Bring up MAVSDK, UWB, and Realsense, log per-subsystem health, "
             "then tear down without arming. Respects --mock-* flags. Exit 0 "
             "if all 3 subsystems came up, 2 if any failed.",
    )
    p.add_argument(
        "--nofly",
        action="store_true",
        help="No-flight bench mode for a drone that must stay grounded. Brings "
             "up all subsystems and runs the full scan/detect/map/artifact "
             "pipeline IN PLACE, but NEVER arms, takes off, starts offboard, "
             "sends a velocity/position command, or lands. Use this to verify "
             "ArUco detection, RealSense, UWB, and artifact writing on a "
             "powered-but-grounded drone (point the camera at printed markers). "
             "World coordinates are not physically meaningful at ground level, "
             "but every other stage of the pipeline is exercised. Honours "
             "--max-flight-time-s as the scan duration; Ctrl-C stops cleanly.",
    )
    args = p.parse_args(argv)
    if not (args.real or args.mock_all or args.mock_uwb or args.mock_mavsdk or args.mock_realsense):
        args.real = True
    return args


def main() -> int:
    args = _parse_args()
    # --dry-run short-circuits the normal mission entirely: bring up the three
    # subsystems, log health, tear down, exit. Honours --mock-* so it works on
    # a bench laptop with no hardware. Must run BEFORE the normal asyncio.run
    # below so we don't drag in RunWriter / mission setup we'll never use.
    if getattr(args, "dry_run", False):
        try:
            return asyncio.run(_dry_run(args))
        except KeyboardInterrupt:
            return 130
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
            abort_reason: str | None = "outer exception (no inner reason recorded)"
            grid: Any = None
            if controller is not None:
                if controller.state.started_at > 0:
                    total_s = time.monotonic() - controller.state.started_at
                aborted_flag = bool(
                    controller.state.aborted or controller.state.stop_requested
                )
                # Prefer the controller's recorded reason when it exists;
                # fall back to stop_requested -> user_interrupt so the
                # KeyboardInterrupt-at-top-level path still names itself.
                if controller.state.abort_reason:
                    abort_reason = controller.state.abort_reason
                elif controller.state.stop_requested:
                    abort_reason = "user_interrupt"
                grid = controller.grid
            if grid is None:
                grid = OccupancyGrid(resolution_m=0.05, size_m=20.0)
            writer.finalise(grid, total_s, aborted_flag, abort_reason=abort_reason)
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
