"""
RoboVerse search controller — Phase 1.

Single-file asyncio controller that:
  * Connects to PX4 SITL on udp://:14540
  * Sets the SITL battery/supply circuit-breaker params from code
    (no need to type them in the px4> console)
  * Verifies home_position_ok is set (operator still needs to run
    `commander set_ekf_origin ...` in the px4 console — see README)
  * Arms, takes off, follows a hardcoded waypoint script, lands, disarms
  * Runs a setpoint pumper task at 10 Hz so PX4 never loses heartbeat
    while the main loop is doing planner work
  * Logs everything to searchctl/logs/run_<ts>.log AND stdout
  * On *any* failure path (exception, signal, watchdog trigger),
    runs an emergency_land coroutine that lands + disarms before exit

Phase 1 has no detection, no depth, no real search strategy. The waypoint
script is just a smoke pattern — fly a square at 2 m altitude, then land.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.offboard import OffboardError, PositionNedYaw, VelocityNedYaw


# ---------------------------------------------------------------------------
# Logging — file + stdout
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
RUN_TS = time.strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"run_{RUN_TS}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("ctl")


# ---------------------------------------------------------------------------
# Shared state — read by tasks, written by the main planner
# ---------------------------------------------------------------------------
@dataclass
class SharedState:
    # Current measured pose (from telemetry task)
    north_m: float = 0.0
    east_m: float = 0.0
    down_m: float = 0.0
    yaw_deg: float = 0.0
    armed: bool = False
    in_air: bool = False
    flight_mode: str = "UNKNOWN"

    # Current setpoint the pumper should send (written by main loop)
    target_north: float = 0.0
    target_east: float = 0.0
    target_down: float = -2.0   # negative = up; -2.0 m = 2 m altitude
    target_yaw: float = 0.0

    # Heartbeat / liveness
    last_planner_progress: float = field(default_factory=time.monotonic)
    abort_requested: bool = False


# ---------------------------------------------------------------------------
# Drone wrapper — preflight params + connection
# ---------------------------------------------------------------------------
class Drone:
    """Thin MAVSDK wrapper. Owns the System instance and preflight setup."""

    SYSTEM_ADDR = "udpin://0.0.0.0:14540"

    def __init__(self) -> None:
        self.drone = System()

    async def connect(self) -> None:
        log.info("connecting to PX4 at %s", self.SYSTEM_ADDR)
        await self.drone.connect(system_address=self.SYSTEM_ADDR)
        async for s in self.drone.core.connection_state():
            if s.is_connected:
                log.info("PX4 connected")
                return
        raise RuntimeError("PX4 connection state never became connected")

    async def set_sitl_workarounds(self) -> None:
        """Apply the 'battery unhealthy' workarounds via MAVSDK param plugin.

        These match what `param set CBRK_SUPPLY_CHK 894281` and
        `param set SIM_BAT_MIN_PCT 100` would do in the px4> console.
        Idempotent — safe to call every run.
        """
        try:
            await self.drone.param.set_param_int("CBRK_SUPPLY_CHK", 894281)
            log.info("CBRK_SUPPLY_CHK set to 894281 (supply check bypassed)")
        except Exception as e:
            log.warning("could not set CBRK_SUPPLY_CHK: %s", e)
        try:
            await self.drone.param.set_param_float("SIM_BAT_MIN_PCT", 100.0)
            log.info("SIM_BAT_MIN_PCT set to 100.0 (battery pinned full)")
        except Exception as e:
            log.warning("could not set SIM_BAT_MIN_PCT: %s", e)

    async def wait_until_armable(self, timeout_s: float = 30.0) -> None:
        """Block until PX4 says the drone can be armed."""
        log.info("waiting for is_armable...")
        deadline = time.monotonic() + timeout_s
        async for h in self.drone.telemetry.health():
            armable = bool(getattr(h, "is_armable", False))
            home_ok = bool(h.is_home_position_ok)
            local_ok = bool(h.is_local_position_ok)
            log.debug(
                "health: armable=%s home_ok=%s local_ok=%s",
                armable, home_ok, local_ok,
            )
            if armable:
                log.info("is_armable=True; OK to arm")
                return
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"is_armable still False after {timeout_s}s "
                    f"(home_ok={home_ok}, local_ok={local_ok}). "
                    "Did you run `commander set_ekf_origin 47.397742 8.545594 488.0` "
                    "in the px4> console?"
                )
            await asyncio.sleep(0.5)

    async def arm_and_takeoff(self, altitude_m: float = 2.0) -> None:
        log.info("arming")
        try:
            await self.drone.action.arm()
        except ActionError as e:
            raise RuntimeError(f"arm failed: {e}") from e

        try:
            await self.drone.action.set_takeoff_altitude(altitude_m)
        except Exception as e:
            log.warning("set_takeoff_altitude failed (continuing): %s", e)

        log.info("takeoff to %.1f m", altitude_m)
        try:
            await self.drone.action.takeoff()
        except ActionError as e:
            raise RuntimeError(f"takeoff failed: {e}") from e

        # Wait for the drone to reach roughly the target altitude.
        await self._wait_until_altitude(altitude_m, tolerance=0.5, timeout_s=20.0)
        log.info("takeoff complete")

    async def _wait_until_altitude(
        self, target_alt: float, tolerance: float, timeout_s: float
    ) -> None:
        deadline = time.monotonic() + timeout_s
        async for p in self.drone.telemetry.position_velocity_ned():
            alt = -p.position.down_m
            if abs(alt - target_alt) <= tolerance:
                return
            if time.monotonic() > deadline:
                log.warning(
                    "altitude wait timed out (current=%.2f target=%.2f)",
                    alt, target_alt,
                )
                return
            await asyncio.sleep(0.3)

    async def begin_offboard(self, initial: PositionNedYaw) -> None:
        """Prime offboard with one setpoint, then start the mode."""
        await self.drone.offboard.set_position_ned(initial)
        try:
            await self.drone.offboard.start()
            log.info("offboard mode started")
        except OffboardError as e:
            raise RuntimeError(f"offboard.start() failed: {e}") from e

    async def end_offboard(self) -> None:
        try:
            await self.drone.offboard.stop()
            log.info("offboard mode stopped")
        except OffboardError as e:
            log.warning("offboard.stop() failed (continuing to land): %s", e)

    async def land_and_disarm(self) -> None:
        log.info("landing")
        try:
            await self.drone.action.land()
        except ActionError as e:
            log.warning("land() failed: %s", e)
        # Wait until on ground or timeout.
        deadline = time.monotonic() + 30.0
        async for in_air in self.drone.telemetry.in_air():
            if not in_air:
                break
            if time.monotonic() > deadline:
                log.warning("landing wait timed out")
                break
            await asyncio.sleep(0.5)
        log.info("on ground; disarming")
        try:
            await self.drone.action.disarm()
        except ActionError as e:
            log.warning("disarm() failed: %s", e)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------
async def setpoint_pumper(drone: Drone, state: SharedState, hz: float = 10.0) -> None:
    """Continuously push the current target setpoint to PX4.

    This is the lifeline — PX4 must see a setpoint at least every 0.5 s or
    it'll failsafe-land. We send at 10 Hz with plenty of margin.
    """
    period = 1.0 / hz
    sent = 0
    while not state.abort_requested:
        try:
            await drone.drone.offboard.set_position_ned(
                PositionNedYaw(
                    state.target_north,
                    state.target_east,
                    state.target_down,
                    state.target_yaw,
                )
            )
            sent += 1
            if sent % (int(hz) * 5) == 0:  # every ~5 seconds
                log.debug(
                    "pumper @ %d  target=(%.1f, %.1f, %.1f) yaw=%.0f",
                    sent, state.target_north, state.target_east,
                    state.target_down, state.target_yaw,
                )
        except OffboardError as e:
            # If offboard isn't started yet, we'll get an error — that's fine,
            # just keep trying. The main flow primes offboard before launching
            # the planner, so this should only matter during the brief startup.
            log.debug("pumper offboard error (will retry): %s", e)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("unexpected error in setpoint_pumper")
        await asyncio.sleep(period)


async def telemetry_monitor(drone: Drone, state: SharedState) -> None:
    """Two streams — position+velocity and attitude — fanned into SharedState."""
    async def stream_pose():
        async for p in drone.drone.telemetry.position_velocity_ned():
            state.north_m = p.position.north_m
            state.east_m = p.position.east_m
            state.down_m = p.position.down_m
            if state.abort_requested:
                return

    async def stream_yaw():
        async for att in drone.drone.telemetry.attitude_euler():
            state.yaw_deg = att.yaw_deg
            if state.abort_requested:
                return

    async def stream_armed():
        async for a in drone.drone.telemetry.armed():
            state.armed = bool(a)
            if state.abort_requested:
                return

    async def stream_in_air():
        async for ia in drone.drone.telemetry.in_air():
            state.in_air = bool(ia)
            if state.abort_requested:
                return

    await asyncio.gather(stream_pose(), stream_yaw(), stream_armed(), stream_in_air())


async def watchdog(state: SharedState, timeout_s: float = 30.0) -> None:
    """If the planner hasn't called state.touch() within timeout, abort."""
    while not state.abort_requested:
        idle = time.monotonic() - state.last_planner_progress
        if idle > timeout_s:
            log.error(
                "WATCHDOG TRIPPED — no planner progress for %.1f s; "
                "requesting abort",
                idle,
            )
            state.abort_requested = True
            return
        await asyncio.sleep(1.0)


# ---------------------------------------------------------------------------
# Phase 1 planner — fly a small scripted square at fixed altitude
# ---------------------------------------------------------------------------
WAYPOINTS = [
    # (north, east, down, yaw_deg, hold_s, label)
    ( 0.0,  0.0, -2.0,   0.0,  3.0, "hover above start"),
    ( 4.0,  0.0, -2.0,   0.0,  4.0, "forward 4 m, facing N"),
    ( 4.0,  4.0, -2.0,  90.0,  4.0, "right 4 m, facing E"),
    ( 0.0,  4.0, -2.0, 180.0,  4.0, "back 4 m, facing S"),
    ( 0.0,  0.0, -2.0, -90.0,  4.0, "left 4 m, facing W"),
    ( 0.0,  0.0, -2.0,   0.0,  3.0, "return home, hover"),
]

ARRIVE_TOL_XY = 0.4   # m
ARRIVE_TOL_YAW = 8.0  # deg


def _dist_xy(state: SharedState, n: float, e: float) -> float:
    return math.hypot(state.north_m - n, state.east_m - e)


def _yaw_err(state: SharedState, target_yaw: float) -> float:
    err = (target_yaw - state.yaw_deg + 540.0) % 360.0 - 180.0
    return abs(err)


async def planner(state: SharedState) -> None:
    """Step through the scripted waypoint list, writing targets for the pumper."""
    log.info("planner started; %d waypoints", len(WAYPOINTS))
    for i, (n, e, d, yaw, hold, label) in enumerate(WAYPOINTS):
        if state.abort_requested:
            log.info("planner aborting before waypoint %d", i)
            return
        log.info("WP %d/%d — %s   target=(N=%.1f E=%.1f D=%.1f yaw=%.0f)",
                 i + 1, len(WAYPOINTS), label, n, e, d, yaw)
        state.target_north = n
        state.target_east = e
        state.target_down = d
        state.target_yaw = yaw
        state.last_planner_progress = time.monotonic()

        # Wait until arrived (with a per-WP timeout that also touches the watchdog).
        wp_deadline = time.monotonic() + 25.0
        while True:
            if state.abort_requested:
                return
            if (
                _dist_xy(state, n, e) < ARRIVE_TOL_XY
                and abs(state.down_m - d) < 0.5
                and _yaw_err(state, yaw) < ARRIVE_TOL_YAW
            ):
                log.info("  arrived (pos err=%.2f m, yaw err=%.1f deg)",
                         _dist_xy(state, n, e), _yaw_err(state, yaw))
                break
            if time.monotonic() > wp_deadline:
                log.warning("  WP %d timeout; pos err=%.2f m yaw err=%.1f deg — moving on",
                            i + 1, _dist_xy(state, n, e), _yaw_err(state, yaw))
                break
            # Keep the watchdog quiet — we're making progress (or at least trying).
            state.last_planner_progress = time.monotonic()
            await asyncio.sleep(0.25)

        log.info("  holding %.1f s", hold)
        for _ in range(int(hold * 4)):
            if state.abort_requested:
                return
            state.last_planner_progress = time.monotonic()
            await asyncio.sleep(0.25)

    log.info("planner complete; all waypoints visited")


# ---------------------------------------------------------------------------
# Main + signal handling
# ---------------------------------------------------------------------------
async def emergency_land(drone: Drone, state: SharedState) -> None:
    """Best-effort: stop offboard, land, disarm. Never raises."""
    log.warning("emergency_land triggered")
    state.abort_requested = True
    try:
        await asyncio.wait_for(drone.end_offboard(), timeout=3.0)
    except Exception:
        log.exception("end_offboard failed during emergency_land")
    try:
        await asyncio.wait_for(drone.land_and_disarm(), timeout=40.0)
    except Exception:
        log.exception("land_and_disarm failed during emergency_land")
    log.warning("emergency_land complete")


async def run() -> int:
    state = SharedState()
    drone = Drone()

    # Hook SIGINT / SIGTERM into the abort flag.
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: setattr(state, "abort_requested", True))
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for SIGTERM, but the
            # VM is Linux so this works there. KeyboardInterrupt catch-all
            # below picks up SIGINT on Windows.
            pass

    try:
        await drone.connect()
        await drone.set_sitl_workarounds()
        await asyncio.sleep(1.0)  # give params time to apply
        await drone.wait_until_armable(timeout_s=45.0)

        # Telemetry must be live BEFORE we arm so the pumper has fresh pose data.
        telem_task = asyncio.create_task(telemetry_monitor(drone, state), name="telemetry")
        await asyncio.sleep(0.5)

        await drone.arm_and_takeoff(altitude_m=abs(state.target_down))

        # Prime offboard with the current target, then start it + the pumper.
        await drone.begin_offboard(
            PositionNedYaw(state.target_north, state.target_east, state.target_down, state.target_yaw)
        )
        pumper_task = asyncio.create_task(setpoint_pumper(drone, state), name="pumper")
        wd_task = asyncio.create_task(watchdog(state), name="watchdog")

        # Run the scripted planner. Wraps in try so we always land afterward.
        try:
            await planner(state)
        finally:
            state.abort_requested = True
            for t in (pumper_task, wd_task, telem_task):
                t.cancel()
            for t in (pumper_task, wd_task, telem_task):
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

        await drone.end_offboard()
        await drone.land_and_disarm()
        log.info("run finished cleanly")
        return 0

    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt received")
        await emergency_land(drone, state)
        return 130
    except Exception:
        log.exception("fatal error in run()")
        await emergency_land(drone, state)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    args = ap.parse_args()
    logging.getLogger().setLevel(args.log_level)

    log.info("==== searchctl controller v0.1 (Phase 1: scripted square) ====")
    log.info("logs at %s", LOG_FILE)
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
