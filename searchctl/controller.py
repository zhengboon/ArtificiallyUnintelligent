"""
RoboVerse search controller — Phases 1 (flight) + 2 (detection) + 6 (fake-GCS) + 7 (mapping + timer).

Single-file asyncio controller that:
  * Connects to PX4 SITL on udp://:14540
  * Sets the SITL battery/supply circuit-breaker params from code
    (no need to type them in the px4> console)
  * Verifies home_position_ok is set (operator still needs to run
    `commander set_ekf_origin ...` in the px4 console — see README)
  * Arms, takes off, follows a hardcoded waypoint script, lands, disarms
  * Runs a setpoint pumper task at 10 Hz so PX4 never loses heartbeat
    while the main loop is doing planner work
  * (Phase 2) Subscribes to the IMX214 RGB camera via gz-transport,
    feeds frames into a YOLO worker thread, logs detections with the
    drone's NED pose at frame-capture time, and saves annotated .jpgs
    to logs/run_<ts>/detections/
  * (Phase 6) Sends a fake-GCS HEARTBEAT on UDP 14550 so PX4's preflight
    "no GCS connection" check passes without QGC running
  * (Phase 7) Subscribes to the depth camera, accumulates obstacle points
    in a global NED top-down map, periodically renders run_dir/map.png
    so judges observe a live map being built (tiebreaker signal per org's
    2026-05-18 clarification), saves map_points.npy on teardown
  * (Phase 7) Tracks per-run wall-clock from takeoff→land and writes a
    run_summary.json with detection list + timing for A's scoring script
  * Logs everything to logs/run_<ts>.log AND stdout
  * On *any* failure path (exception, signal, watchdog trigger),
    runs an emergency_land coroutine that lands + disarms before exit

Detection, fake-GCS, and mapping are each opt-out via --no-detect,
--no-fake-gcs, --no-map. If any dependency (ultralytics, gz.transport13,
matplotlib, pymavlink, the workshop's Detector.py) can't be imported, the
controller logs a warning and proceeds with whatever remains — flight is
never blocked by an optional pipeline failing to start.

The current waypoint script is still a smoke pattern (4-cell square at
2 m altitude). Phase 3 will replace it with a real search strategy.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.offboard import OffboardError, PositionNedYaw, VelocityNedYaw, VelocityBodyYawspeed

# Detection deps are imported lazily inside setup_detection() so the
# controller still runs Phase-1-only without them installed.


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

    # ---- Detection state (Phase 2; populated by detection_callback) ----
    detection_count: int = 0
    detections: list = field(default_factory=list)
    last_detection_at: Optional[float] = None

    # ---- Run-timing state (Phase 7; populated by run()) ----
    # Wall-clock seconds since epoch. takeoff_ts is set just after
    # arm_and_takeoff returns; land_ts is set right before disarm.
    takeoff_ts: Optional[float] = None
    land_ts: Optional[float] = None

    # ---- Mapping state (Phase 7; populated by mapping task) ----
    map_points_count: int = 0       # rolling count of accumulated obstacle points

    # ---- Wall-following / velocity-mode state (K's planner) ----
    # When True, setpoint_pumper sends VelocityBodyYawspeed (forward / right /
    # down / yaw-rate) instead of PositionNedYaw. Set by planner_wall().
    velocity_mode: bool = False
    vel_fwd: float = 0.0       # m/s, body-frame forward
    vel_right: float = 0.0     # m/s, body-frame right (positive = strafe right)
    vel_down: float = 0.0      # m/s, body-frame down (positive = descend)
    yaw_rate_deg: float = 0.0  # deg/s


@dataclass
class DetectionRecord:
    """One record per fired detection. Kept light — full annotated frame
    lives on disk, this just keeps the gist."""
    seq: int
    ts: float
    class_name: str
    confidence: float
    bbox_xyxy: tuple        # (x1, y1, x2, y2) in image pixels
    pose_at_detect: tuple   # (north, east, down, yaw_deg) at frame capture time
    saved_path: Optional[str]


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

        # PX4 TAKEOFF mode handles the climb. Sleep 8 s — same pattern the
        # workshop's drone_control_new.py uses. The pumper takes over after
        # offboard.start(); no point in polling telemetry just to time out
        # exactly when the drone is mid-climb.
        await asyncio.sleep(8.0)
        log.info("takeoff complete (assumed; pumper will hold altitude)")

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

    Branches on state.velocity_mode:
      False (default): sends PositionNedYaw — used by 'square' / 'scan' planners
      True:            sends VelocityBodyYawspeed — used by K's wall-follow
                       planner (forward / right / down / yawspeed_deg)
    """
    period = 1.0 / hz
    sent = 0
    while not state.abort_requested:
        try:
            if state.velocity_mode:
                await drone.drone.offboard.set_velocity_body(
                    VelocityBodyYawspeed(
                        state.vel_fwd,
                        state.vel_right,
                        state.vel_down,
                        state.yaw_rate_deg,
                    )
                )
            else:
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


async def flight_clock_logger(state: SharedState, interval_s: float = 5.0) -> None:
    """Periodic visible status line so judges + screen-watcher see live
    progress: elapsed flight time, detection counts by class, map points,
    current pose. Runs alongside whichever planner is active."""
    while not state.abort_requested:
        await asyncio.sleep(interval_s)
        if state.takeoff_ts is None:
            continue  # not airborne yet
        elapsed = time.time() - state.takeoff_ts
        # Count detections by class for the visible summary
        yellow_n = sum(1 for d in state.detections if "yellow" in d.class_name.lower())
        red_n = sum(1 for d in state.detections if "red" in d.class_name.lower() and "toxic" not in d.class_name.lower())
        log.info(
            "flight: T+%5.1fs  detections: %dY/%dR (total %d)  map=%d  pos=(N=%.1f E=%.1f D=%.1f yaw=%.0f)",
            elapsed, yellow_n, red_n, state.detection_count,
            state.map_points_count,
            state.north_m, state.east_m, state.down_m, state.yaw_deg,
        )


async def divergence_watchdog(state: SharedState) -> None:
    """Emergency-abort if measured position drifts far from the active target.

    EKF vision odometry can lose tracking during fast yaw or visually
    featureless flight, causing the position estimate to diverge by tens
    of meters. We refuse to let the drone fly into the void: if the
    distance from current measured pose to the active setpoint exceeds
    DIVERGENCE_LIMIT_M continuously for DIVERGENCE_TIME_S, set abort.
    """
    divergent_since: Optional[float] = None
    while not state.abort_requested:
        # In velocity mode (e.g. K's wall-follow) the position setpoints
        # state.target_north / target_east stay at takeoff origin while the
        # drone actually translates around the arena. Comparing against them
        # would trip the watchdog spuriously — disable the check while
        # velocity mode is active.
        if state.velocity_mode:
            divergent_since = None
            await asyncio.sleep(0.2)
            continue
        err = math.hypot(
            state.north_m - state.target_north,
            state.east_m - state.target_east,
        )
        now = time.monotonic()
        if err > DIVERGENCE_LIMIT_M:
            if divergent_since is None:
                divergent_since = now
                log.warning(
                    "divergence watchdog armed: pos err=%.2f m > %.1f m",
                    err, DIVERGENCE_LIMIT_M,
                )
            elif now - divergent_since > DIVERGENCE_TIME_S:
                log.error(
                    "DIVERGENCE WATCHDOG TRIPPED — pos err=%.2f m sustained "
                    "for %.1f s; requesting abort",
                    err, now - divergent_since,
                )
                state.abort_requested = True
                return
        else:
            divergent_since = None  # back in range
        await asyncio.sleep(0.2)


# ---------------------------------------------------------------------------
# Detection pipeline (Phase 2)
# ---------------------------------------------------------------------------
# Architecture:
#   gz-transport delivers frames to our callback (on its own thread)
#   → callback stamps frame with current NED pose + submits to Detector
#   → Detector runs YOLO in its own worker thread(s)
#   → Detector calls our on_detection() callback when something fires
#   → on_detection logs + appends to SharedState.detections
#
# Nothing in this pipeline touches the asyncio loop — the setpoint pumper
# is unaffected by YOLO inference time. That's the whole point.

IMAGE_TOPIC_DEFAULT = (
    "/world/roboverse/model/x500_vision_0/link/camera_link"
    "/sensor/IMX214/image"
)

WORKSHOP_CODES_DIR = os.path.expanduser("~/ArtificiallyUnintelligent/codes/Codes")
YOLO_WEIGHTS_DEFAULT = os.path.expanduser("~/ArtificiallyUnintelligent/models/best.pt")
# 0.35 (was 0.5). Org confirmed 21/5/2026 no penalty for incorrect detections,
# so we err on the side of firing more often. Verylousymodel fired at 0.50-0.52
# in our 20/5 test, right at the old threshold's edge.
DETECT_CONFIDENCE_DEFAULT = 0.35

# WORKSHOP_CODES_DIR = os.path.expanduser("~/Desktop/codes")
# YOLO_WEIGHTS_DEFAULT = os.path.join(WORKSHOP_CODES_DIR, "yolov10n.pt")
# DETECT_CONFIDENCE_DEFAULT = 0.4


def _import_detection_deps():
    """Lazy import so the controller still runs without ultralytics/gz installed."""
    # The workshop's Detector lives in ~/Desktop/codes; make it importable.
    if WORKSHOP_CODES_DIR not in sys.path:
        sys.path.insert(0, WORKSHOP_CODES_DIR)
    # gz.msgs10 needs this env var or its import explodes.
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    import cv2                                    # noqa: F401
    import numpy as np
    from gz.transport13 import Node
    from gz.msgs10.image_pb2 import Image
    from Detector import Detector                 # workshop's class
    return cv2, np, Node, Image, Detector


def setup_detection(
    state: SharedState,
    run_dir: Path,
    weights_path: str = YOLO_WEIGHTS_DEFAULT,
    confidence: float = DETECT_CONFIDENCE_DEFAULT,
    image_topic: str = IMAGE_TOPIC_DEFAULT,
) -> Optional[dict]:
    """Stand up the camera → YOLO pipeline.

    Returns a handle dict with the live objects so teardown_detection
    can shut them down, or None if init failed (in which case we run
    Phase-1-only with a logged warning — flight should not be blocked
    by a missing camera).
    """
    try:
        cv2, np, Node, Image, Detector = _import_detection_deps()
    except Exception:
        log.exception("could not import detection deps; running without detection")
        return None

    det_dir = run_dir / "detections"
    det_dir.mkdir(parents=True, exist_ok=True)
    log.info("detection: saving annotated frames into %s", det_dir)

    seq_counter = {"n": 0}

    def on_detection(detections, annotated_image, context):
        """Runs in Detector's worker thread. Don't touch asyncio from here."""
        if not detections:
            return
        seq_counter["n"] += 1
        for d in detections:
            cls = d.get("class_name", "?")
            conf = float(d.get("confidence", 0.0))
            bbox = tuple(d.get("bbox", (0, 0, 0, 0)))
            pose = context.get("pose", (0.0, 0.0, 0.0, 0.0))
            saved = context.get("saved_path")
            record = DetectionRecord(
                seq=seq_counter["n"],
                ts=context.get("timestamp", time.time()),
                class_name=cls,
                confidence=conf,
                bbox_xyxy=bbox,
                pose_at_detect=pose,
                saved_path=str(saved) if saved else None,
            )
            state.detections.append(record)
            state.detection_count += 1
            state.last_detection_at = time.monotonic()
            log.info(
                "detection: class=%s conf=%.2f pose=(N=%.2f E=%.2f D=%.2f yaw=%.0f)  -> %s",
                cls, conf, pose[0], pose[1], pose[2], pose[3],
                Path(saved).name if saved else "(no file)",
            )

    try:
        detector = Detector(
            model_path=weights_path,
            confidence_threshold=confidence,
            callback=on_detection,
            num_workers=2,
            device="cpu",
            save_dir=str(det_dir),
            enable_display=False,
        )
    except Exception:
        log.exception("Detector failed to init; running without detection")
        return None

    # K's best.pt names classes with spaces ("yellow barrel" / "red barrel" /
    # "toxic barrel"). Org's example image (the qualifier reference) and
    # org's verylousymodel.pt both use underscores ("yellow_barrel" /
    # "red_barrel"). Remap so saved bbox JPGs + log lines + run_summary.json
    # all match the format judges will be looking for.
    # Patch class names so saved bbox JPGs read "yellow_barrel" (org example
    # format) instead of K's training-time "yellow barrel" (with a space).
    # Modern ultralytics makes `YOLO.names` a read-only property — the real
    # backing dict lives on the inner DetectionModel (detector.model.model).
    # Write to whichever paths accept the assignment; each is its own
    # try/except so one failure doesn't skip the others.
    remap = {0: "yellow_barrel", 1: "red_barrel", 2: "toxic_barrel"}
    original = None
    try:
        original = dict(getattr(detector.model, "names", {}))
    except Exception:
        pass
    patched_paths = []
    # Path 1: inner DetectionModel.names (this is the one result.plot() reads
    # from in current ultralytics).
    try:
        if hasattr(detector.model, "model") and hasattr(detector.model.model, "names"):
            detector.model.model.names = remap
            patched_paths.append("model.model.names")
    except Exception as e:
        log.debug("remap path model.model.names failed: %s: %s", type(e).__name__, e)
    # Path 2: top-level YOLO.names (older ultralytics).
    try:
        detector.model.names = remap
        patched_paths.append("model.names")
    except Exception as e:
        log.debug("remap path model.names failed: %s: %s", type(e).__name__, e)
    # Path 3: predictor's model.names (if predictor is initialised).
    try:
        if hasattr(detector.model, "predictor") and detector.model.predictor is not None:
            pm = detector.model.predictor.model
            if hasattr(pm, "names"):
                pm.names = remap
                patched_paths.append("model.predictor.model.names")
    except Exception as e:
        log.debug("remap path predictor.model.names failed: %s: %s", type(e).__name__, e)
    if patched_paths:
        log.info("detection: class names remapped (%s) %s -> %s",
                 ",".join(patched_paths), original, remap)
    else:
        log.warning("detection: could NOT remap class names on any path; "
                    "JPG bbox labels will use model defaults (%s)", original)

    # Shutdown flag: teardown_detection flips this, image_callback then
    # short-circuits, queue stops growing, Detector workers can drain + exit.
    # Without this gate, Detector.stop()'s t.join() blocks forever because
    # gz keeps feeding the queue.
    shutting_down = {"v": False}

    def image_callback(msg):
        """Runs in gz-transport's own thread. Push frame -> Detector queue.
        Detector internally has its own worker thread, so this returns fast."""
        if shutting_down["v"]:
            return
        try:
            frame = np.frombuffer(msg.data, dtype=np.uint8)
            frame = frame.reshape((msg.height, msg.width, 3))
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            # Snapshot pose at capture time — GIL makes these reads safe.
            pose = (state.north_m, state.east_m, state.down_m, state.yaw_deg)
            detector.submit_image(
                frame_bgr,
                context={"timestamp": time.time(), "pose": pose},
            )
        except Exception:
            log.exception("image_callback failed (will keep listening)")

    node = Node()
    if not node.subscribe(Image, image_topic, image_callback):
        log.error("could not subscribe to image topic %s; running without detection", image_topic)
        try:
            detector.stop()
        except Exception:
            pass
        return None
    log.info("detection: subscribed to %s", image_topic)

    return {"detector": detector, "node": node, "shutting_down": shutting_down}


def teardown_detection(handle: Optional[dict], state: SharedState) -> None:
    if handle is None:
        return
    log.info("detection: total fired = %d", state.detection_count)
    # First: stop accepting new frames so the Detector queue can drain.
    handle["shutting_down"]["v"] = True
    # Drain any in-flight frames quickly with a hard cap so we exit.
    try:
        det = handle["detector"]
        det.stop_event.set()
        # Manually join workers with a per-worker timeout instead of
        # Detector.stop()'s unbounded join (which can block if queue is huge).
        for t in det.workers:
            t.join(timeout=5.0)
            if t.is_alive():
                log.warning("detection: worker thread still alive after 5s; abandoning")
    except Exception:
        log.exception("Detector teardown failed")
    # gz-transport Node has no clean unsubscribe API; it'll exit with the
    # process. Drop our reference so it can be garbage-collected.
    handle["node"] = None


# ---------------------------------------------------------------------------
# Top-down mapping pipeline (Phase 7)
# ---------------------------------------------------------------------------
# Judges observe "is some sort of mapping being done as the drone flies"
# (org clarification 2026-05-18). They use this as a tiebreaker signal.
#
# Architecture mirrors detection: a gz-transport callback on the depth
# topic stashes the latest frame, a background asyncio task drains it
# every N seconds and accumulates obstacle points in the global NED frame
# using pose snapshots from SharedState. Every render tick we save a PNG
# of the live map to run_dir/map.png AND a snapshot map_<seq>.png to
# run_dir/map_frames/ so the judge sees a fresh image on screen.
#
# At teardown we save final map.png + map_points.npy + run_summary.json.
#
# All work happens off the asyncio loop (gz callback thread + the asyncio
# task only does the cheap aggregation step). The render is offloaded to
# a thread so matplotlib's PNG save can't stall the planner.

DEPTH_TOPIC_DEFAULT = "/depth_camera"
# Same intrinsics the workshop uses (OAK-D Lite at 640x480 after the
# org's 11/5/2026 model.sdf update). If the camera resolution differs
# at runtime the depth_to_xy_map call still works — only fx/fy/cx/cy
# scaling would be slightly off, which is acceptable for a visual map.
DEPTH_K = (
    (433.0,   0.0, 320.0),
    (  0.0, 433.0, 240.0),
    (  0.0,   0.0,   1.0),
)
MAP_RENDER_INTERVAL_S = 1.0   # how often we re-render the PNG
MAP_MAX_POINTS = 200_000      # cap memory; oldest points dropped past this


def _import_mapping_deps():
    """Lazy import — same opt-out pattern as detection deps."""
    if WORKSHOP_CODES_DIR not in sys.path:
        sys.path.insert(0, WORKSHOP_CODES_DIR)
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")             # headless — no display server needed
    import matplotlib.pyplot as plt
    from gz.transport13 import Node
    from gz.msgs10.image_pb2 import Image
    from top_down import depth_to_xy_map    # workshop helper
    return np, plt, Node, Image, depth_to_xy_map


def setup_mapping(
    state: SharedState,
    run_dir: Path,
    depth_topic: str = DEPTH_TOPIC_DEFAULT,
) -> Optional[dict]:
    """Stand up the depth-camera → top-down map pipeline.

    Returns a handle dict (or None on init failure → mapping disabled,
    flight proceeds without it).
    """
    try:
        np, plt, Node, Image, depth_to_xy_map = _import_mapping_deps()
    except Exception:
        log.exception("could not import mapping deps; running without map")
        return None

    map_dir = run_dir / "map_frames"
    map_dir.mkdir(parents=True, exist_ok=True)
    final_png = run_dir / "map.png"
    final_npy = run_dir / "map_points.npy"

    # Latest depth frame stashed by the gz callback; the asyncio task
    # consumes it. We don't queue every frame — only the most recent
    # one matters for an accumulating obstacle map.
    latest = {"depth": None, "pose": None, "ts": 0.0}
    latest_lock = threading.Lock()

    # Accumulator (kept as a numpy array, two columns: north, east)
    points = np.empty((0, 2), dtype=np.float32)

    K = np.array(DEPTH_K, dtype=np.float32)

    # Shutdown flag — same pattern as detection. Lets the mapping task drain
    # its current depth frame and exit without the callback re-arming work.
    shutting_down = {"v": False}

    def depth_callback(msg):
        """Runs in gz-transport's own thread."""
        if shutting_down["v"]:
            return
        try:
            depth = np.frombuffer(msg.data, dtype=np.float32)
            depth = depth.reshape((msg.height, msg.width))
            pose = (state.north_m, state.east_m, state.down_m, state.yaw_deg)
            with latest_lock:
                latest["depth"] = depth
                latest["pose"] = pose
                latest["ts"] = time.monotonic()
        except Exception:
            log.exception("depth_callback failed (will keep listening)")

    node = Node()
    if not node.subscribe(Image, depth_topic, depth_callback):
        log.error(
            "could not subscribe to depth topic %s; running without map",
            depth_topic,
        )
        return None
    log.info("mapping: subscribed to %s", depth_topic)

    def _render_png(pts, drone_pose, out_path: Path) -> None:
        """Save a top-down obstacle map to PNG. Runs in a worker thread."""
        try:
            fig, ax = plt.subplots(figsize=(8, 8))
            if pts.shape[0] > 0:
                dists = np.linalg.norm(pts, axis=1)
                ax.scatter(
                    pts[:, 1],  # east on X axis
                    pts[:, 0],  # north on Y axis
                    c=dists, s=2, cmap="viridis", edgecolors="none",
                )
            if drone_pose is not None:
                ax.plot(drone_pose[1], drone_pose[0], "r*", markersize=14, label="drone")
                ax.legend(loc="upper right")
            ax.set_xlabel("East [m]")
            ax.set_ylabel("North [m]")
            ax.set_aspect("equal")
            ax.grid(alpha=0.3)
            ax.set_title(
                f"top-down map  |  points={pts.shape[0]}  |  "
                f"detections={state.detection_count}"
            )
            fig.savefig(out_path, dpi=90, bbox_inches="tight")
            plt.close(fig)
        except Exception:
            log.exception("map render failed")

    handle = {
        "node": node,
        "latest": latest,
        "latest_lock": latest_lock,
        "points": points,
        "K": K,
        "depth_to_xy_map": depth_to_xy_map,
        "np": np,
        "map_dir": map_dir,
        "final_png": final_png,
        "final_npy": final_npy,
        "render": _render_png,
        "last_render": 0.0,
        "seq": 0,
        "stop": threading.Event(),
        "shutting_down": shutting_down,
    }
    return handle


def _local_to_ned_global(local_xy, north, east, yaw_rad, np_mod):
    """Same transform as workshop's GlobalMapper_new.py.

    local_xy[:, 0] = camera-right (X_cam), local_xy[:, 1] = camera-forward (Z_cam).
    Returns Nx2 array [north, east] in global NED.
    """
    Xc = local_xy[:, 0]
    Zc = local_xy[:, 1]
    c = np_mod.cos(yaw_rad)
    s = np_mod.sin(yaw_rad)
    north_g = north + Zc * c - Xc * s
    east_g = east + Zc * s + Xc * c
    return np_mod.column_stack([north_g, east_g])


def _depth_to_points_3d(depth, K, np_mod, stride=2):
    """Convert HxW depth image -> Nx3 point cloud in camera optical frame.

    Output columns: [x_right, y_down, z_forward] in metres. Same convention
    as the workshop's depthcloud.PointCloud.convert (which K's
    wall_following.get_wall_distances expects).

    'stride' downsamples by every-other-pixel for speed (matches workshop).
    """
    d = depth[::stride, ::stride]
    h, w = d.shape
    fx = float(K[0, 0])
    fy = float(K[1, 1])
    cx = float(K[0, 2]) / stride
    cy = float(K[1, 2]) / stride
    i, j = np_mod.meshgrid(np_mod.arange(w), np_mod.arange(h))
    z = d.astype(np_mod.float32)
    x = (i - cx) * z / fx
    y = (j - cy) * z / fy
    # Drop invalid (zero / NaN / very-far) returns to keep the cloud sane.
    mask = (z > 0.05) & (z < 15.0) & np_mod.isfinite(z)
    return np_mod.stack((x[mask], y[mask], z[mask]), axis=-1)


async def mapping_task(handle: Optional[dict], state: SharedState) -> None:
    """Drain the latest depth frame, accumulate points, periodically render.

    Cancels cleanly when state.abort_requested flips. Yields back to the
    loop on every tick so the setpoint pumper is never starved.
    """
    if handle is None:
        return
    np = handle["np"]
    depth_to_xy_map = handle["depth_to_xy_map"]
    K = handle["K"]
    latest = handle["latest"]
    latest_lock = handle["latest_lock"]
    points = handle["points"]
    render = handle["render"]
    map_dir = handle["map_dir"]
    final_png = handle["final_png"]

    last_consumed_ts = 0.0
    while not state.abort_requested:
        await asyncio.sleep(0.2)
        with latest_lock:
            ts = latest["ts"]
            if ts == last_consumed_ts:
                continue
            depth = latest["depth"]
            pose = latest["pose"]
            last_consumed_ts = ts

        if depth is None or pose is None:
            continue
        try:
            xy_local = depth_to_xy_map(
                depth, K,
                cam_height=1.0, obs_h_min=0.1, obs_h_max=1.5,
                z_min=0.3, z_max=8.0,
            )
        except Exception:
            log.exception("depth_to_xy_map failed (skipping frame)")
            continue
        if xy_local is None or xy_local.shape[0] == 0:
            continue

        north, east, _down, yaw_deg = pose
        yaw_rad = math.radians(float(yaw_deg))
        global_pts = _local_to_ned_global(xy_local, north, east, yaw_rad, np)
        # Append + cap (drop oldest if past MAX).
        points = np.vstack([points, global_pts.astype(np.float32)])
        if points.shape[0] > MAP_MAX_POINTS:
            points = points[-MAP_MAX_POINTS:]
        handle["points"] = points
        state.map_points_count = int(points.shape[0])

        # Throttled render so we don't burn CPU saving PNGs.
        now = time.monotonic()
        if now - handle["last_render"] >= MAP_RENDER_INTERVAL_S:
            handle["last_render"] = now
            handle["seq"] += 1
            seq_path = map_dir / f"map_{handle['seq']:04d}.png"
            # Offload to a thread — matplotlib PNG save is ~50 ms.
            await asyncio.to_thread(render, points.copy(), pose, final_png)
            # Also drop a numbered snapshot for the after-run viewer.
            await asyncio.to_thread(render, points.copy(), pose, seq_path)


def teardown_mapping(handle: Optional[dict], state: SharedState) -> None:
    if handle is None:
        return
    # Stop accepting new depth frames first.
    handle["shutting_down"]["v"] = True
    pts = handle["points"]
    state.map_points_count = int(pts.shape[0])
    try:
        handle["np"].save(handle["final_npy"], pts)
        log.info(
            "mapping: saved %d points to %s",
            state.map_points_count, handle["final_npy"].name,
        )
    except Exception:
        log.exception("could not save final map_points.npy")
    # One last render so map.png is current at teardown.
    try:
        last_pose = handle["latest"]["pose"]
        handle["render"](pts, last_pose, handle["final_png"])
        log.info("mapping: final map saved to %s", handle["final_png"].name)
    except Exception:
        log.exception("final map render failed")
    handle["node"] = None
    handle["stop"].set()


# ---------------------------------------------------------------------------
# Run summary (Phase 7)
# ---------------------------------------------------------------------------
def write_run_summary(state: SharedState, run_dir: Path) -> None:
    """Dump a small JSON with timing + detection stats. Used by A's
    scoring script and by judges who want to see a single artifact per run."""
    import json
    summary = {
        "run_ts": RUN_TS,
        "takeoff_ts": state.takeoff_ts,
        "land_ts": state.land_ts,
        "flight_seconds": (
            (state.land_ts - state.takeoff_ts)
            if (state.takeoff_ts and state.land_ts) else None
        ),
        "detection_count": state.detection_count,
        "detections": [
            {
                "seq": d.seq,
                "ts": d.ts,
                "class_name": d.class_name,
                "confidence": d.confidence,
                "bbox_xyxy": list(d.bbox_xyxy),
                "pose_at_detect": list(d.pose_at_detect),
                "saved_path": d.saved_path,
            }
            for d in state.detections
        ],
        "map_points_count": state.map_points_count,
        "aborted": state.abort_requested,
    }
    out_path = run_dir / "run_summary.json"
    try:
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        log.info("run summary written to %s", out_path.name)
    except Exception:
        log.exception("could not write run_summary.json")


# ---------------------------------------------------------------------------
# Fake-GCS heartbeat (Phase 6)
# ---------------------------------------------------------------------------
# PX4's preflight has a "GCS connection" check that fires when QGroundControl
# (or any peer identifying as MAV_TYPE_GCS) is connected. On 2026-05-13 we
# hit a QGC crash and PX4 refused to arm with "No connection to the GCS"
# even though our MAVSDK controller was happily talking on udp 14540.
# Reason: PX4 tags the 14540 link as "Onboard", not "GCS".
#
# Workaround: spawn a tiny pymavlink loop on udp 14550 that sends HEARTBEAT
# at 1 Hz claiming to be a GCS. PX4 sees a GCS connected, preflight passes.
# Now the controller is fully self-sufficient — QGC is no longer required.
#
# If QGC IS running, port 14550 is already bound and pymavlink fails to
# open it — we detect that and skip cleanly (QGC is already doing the job).
# If pymavlink isn't installed in the VM, we log a warning and skip.

FAKE_GCS_PORT = 14550


def _fake_gcs_pump(stop_event: "object", port: int = FAKE_GCS_PORT) -> None:
    """Send MAV_TYPE_GCS heartbeats on UDP <port> at 1 Hz until stop_event is set.

    Runs in a daemon thread (not the asyncio loop) so blocking socket
    operations don't interfere with the setpoint pumper.
    """
    try:
        from pymavlink import mavutil
    except ImportError:
        log.warning(
            "fake-GCS: pymavlink not installed; QGC must be running for "
            "preflight to pass. Install with: pip install --user pymavlink"
        )
        return

    try:
        conn = mavutil.mavlink_connection(f"udpin:0.0.0.0:{port}")
    except OSError as e:
        log.info(
            "fake-GCS: could not bind UDP %d (%s) — QGC is probably already "
            "running and serving as GCS. Skipping fake heartbeat.",
            port, e,
        )
        return
    except Exception:
        log.exception("fake-GCS: pymavlink connection failed; continuing without")
        return

    log.info("fake-GCS heartbeat: bound UDP %d, will pulse @ 1 Hz", port)
    sent = 0
    while not stop_event.is_set():
        try:
            conn.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0,
                0,
                mavutil.mavlink.MAV_STATE_ACTIVE,
            )
            sent += 1
            if sent == 1:
                log.info("fake-GCS: first heartbeat sent")
            elif sent % 60 == 0:
                log.debug("fake-GCS: %d heartbeats sent", sent)
        except Exception:
            log.exception("fake-GCS: heartbeat_send failed (will keep trying)")
        stop_event.wait(timeout=1.0)

    try:
        conn.close()
    except Exception:
        pass
    log.info("fake-GCS: stopped (sent %d heartbeats)", sent)


def start_fake_gcs(enabled: bool = True) -> Optional[dict]:
    """Spawn the heartbeat thread. Returns a handle for stop_fake_gcs."""
    if not enabled:
        log.info("fake-GCS disabled (--no-fake-gcs)")
        return None
    import threading
    stop_event = threading.Event()
    t = threading.Thread(
        target=_fake_gcs_pump,
        args=(stop_event,),
        daemon=True,
        name="fake-gcs",
    )
    t.start()
    return {"thread": t, "stop_event": stop_event}


def stop_fake_gcs(handle: Optional[dict]) -> None:
    if handle is None:
        return
    handle["stop_event"].set()
    handle["thread"].join(timeout=3.0)


# ---------------------------------------------------------------------------
# Phase 1 planner — fly a small scripted square at fixed altitude
# ---------------------------------------------------------------------------
WAYPOINTS = [
    # (north, east, down, yaw_deg, hold_s, label)
    # Phase 1 v2: yaw locked to 0° throughout (no rotation), 2 m moves.
    # Rationale: combining a position translation with a yaw change in NED
    # frame caused EKF vision odometry to drift ~100 m on v1's WP3. Without
    # rotation the drone flies laterally with stable visual tracking.
    ( 0.0,  0.0, -2.0, 0.0,  3.0, "hover above start"),
    ( 2.0,  0.0, -2.0, 0.0,  3.0, "forward 2 m"),
    ( 2.0,  2.0, -2.0, 0.0,  3.0, "right 2 m (lateral, yaw still 0)"),
    ( 0.0,  2.0, -2.0, 0.0,  3.0, "back 2 m"),
    ( 0.0,  0.0, -2.0, 0.0,  3.0, "left 2 m, back to start"),
]

# Scan pattern: hold position at spawn, spin 360° in 4× 90° steps with long
# holds so the camera + detector can settle on each cardinal view. Pure yaw
# at fixed XY should not trip the EKF the way yaw+translation did on v1.
SCAN_WAYPOINTS = [
    # (north, east, down, yaw_deg, hold_s, label)
    ( 0.0,  0.0, -2.0,   0.0, 4.0, "hover, face N"),
    ( 0.0,  0.0, -2.0,  90.0, 6.0, "yaw to E (face barrels on right wall)"),
    ( 0.0,  0.0, -2.0, 180.0, 6.0, "yaw to S"),
    ( 0.0,  0.0, -2.0, 270.0, 6.0, "yaw to W (face barrels on left wall)"),
    ( 0.0,  0.0, -2.0, 359.9, 4.0, "yaw back to ~N (avoid wrap from 270 to 0)"),
]

# Which list to fly (set by main() from --pattern flag)
ACTIVE_WAYPOINTS = WAYPOINTS

ARRIVE_TOL_XY = 0.4   # m
ARRIVE_TOL_YAW = 8.0  # deg

# Divergence watchdog: emergency-land if measured position is this far from
# target for this long. Catches EKF blow-up before drone flies far away.
DIVERGENCE_LIMIT_M = 5.0
DIVERGENCE_TIME_S = 3.0


def _dist_xy(state: SharedState, n: float, e: float) -> float:
    return math.hypot(state.north_m - n, state.east_m - e)


def _yaw_err(state: SharedState, target_yaw: float) -> float:
    err = (target_yaw - state.yaw_deg + 540.0) % 360.0 - 180.0
    return abs(err)


async def planner(state: SharedState) -> None:
    """Step through the scripted waypoint list, writing targets for the pumper."""
    log.info("planner started; %d waypoints", len(ACTIVE_WAYPOINTS))
    for i, (n, e, d, yaw, hold, label) in enumerate(ACTIVE_WAYPOINTS):
        if state.abort_requested:
            log.info("planner aborting before waypoint %d", i)
            return
        log.info("WP %d/%d — %s   target=(N=%.1f E=%.1f D=%.1f yaw=%.0f)",
                 i + 1, len(ACTIVE_WAYPOINTS), label, n, e, d, yaw)
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
# Wall-following planner — K's algorithm (searchctl/wall_following.py)
# ---------------------------------------------------------------------------
#
# Flow:
#   1. Pull the latest depth frame from the mapping pipeline's `latest` dict
#      (mapping must be ON — otherwise we have no depth source)
#   2. Project depth -> Nx3 point cloud (camera optical frame)
#   3. K's get_wall_distances() -> {front, front_right, right} in metres
#   4. K's WallFollower.compute() -> (vx, vy, vz, yaw_rate)  [body frame]
#   5. Smooth via K's VelocitySmoother
#   6. Write into state (with yaw_rate converted rad/s -> deg/s)
#   7. Flip state.velocity_mode = True so the setpoint pumper sends
#      VelocityBodyYawspeed instead of PositionNedYaw
#   8. Loop at ~10 Hz until time budget hits or abort flag flips
#
# Time-cap defaults to 8 min so the controller ALWAYS gets to landing within
# the 10-min qualifier run. Land + teardown takes another ~15 s.

WALL_FOLLOW_BUDGET_S      = 480.0   # 8 minutes, leaves headroom inside the 10-min run cap
WALL_FOLLOW_HZ            = 10.0    # match K's tick rate assumptions in WallFollower
WALL_SCAN_EVERY_S         = 30.0    # do a periodic 360° scan every N seconds
WALL_SCAN_YAW_RATE_DEG    = 60.0    # deg/s during scan (full 360 takes 6 s)
WALL_SCAN_DURATION_S      = 7.0     # slightly longer than 360/rate so we overshoot a bit
# Stuck detector (escape K's "corner stuck" / depth-filter oscillation):
WALL_STUCK_WINDOW_S       = 10.0    # if drone hasn't moved much for this long, escape
WALL_STUCK_DISTANCE_M     = 0.5     # threshold for "hasn't moved"
WALL_ESCAPE_BACK_S        = 2.0     # back up for this long
WALL_ESCAPE_BACK_SPEED    = 0.5     # m/s reverse
WALL_ESCAPE_YAW_S         = 3.0     # then yaw for this long
WALL_ESCAPE_YAW_RATE_DEG  = 80.0    # deg/s during escape yaw (~240° in 3s — breaks out of the loop)
WALL_ESCAPE_FWD_S         = 2.0     # then forward push to leave the stuck spot
WALL_ESCAPE_FWD_SPEED     = 0.6     # m/s forward


async def planner_wall(state: SharedState, map_handle: Optional[dict]) -> None:
    """K's wall-following loop. Requires the mapping pipeline to be active
    (we reuse its depth subscription instead of opening a second one)."""
    if map_handle is None:
        log.error(
            "planner_wall requires the Phase 7 mapping pipeline "
            "(don't pass --no-map). Aborting wall planner."
        )
        state.abort_requested = True
        return

    try:
        # Live import so the controller still parses + runs --pattern square
        # even if wall_following.py is missing for some reason.
        from wall_following import WallFollower, get_wall_distances, VelocitySmoother
    except Exception:
        log.exception(
            "could not import searchctl/wall_following.py; aborting wall planner"
        )
        state.abort_requested = True
        return

    follower = WallFollower()
    smoother = VelocitySmoother()
    np = map_handle["np"]
    K = map_handle["K"]
    latest = map_handle["latest"]
    latest_lock = map_handle["latest_lock"]

    state.velocity_mode = True
    state.vel_fwd = state.vel_right = state.vel_down = state.yaw_rate_deg = 0.0
    log.info(
        "planner_wall: started (budget=%.0fs, hz=%.0f, scan every %.0fs)",
        WALL_FOLLOW_BUDGET_S, WALL_FOLLOW_HZ, WALL_SCAN_EVERY_S,
    )
    period = 1.0 / WALL_FOLLOW_HZ
    start_ts = time.monotonic()
    deadline = start_ts + WALL_FOLLOW_BUDGET_S
    next_scan_at = start_ts + WALL_SCAN_EVERY_S
    ticks = 0
    last_log = 0.0

    async def _do_360_scan() -> None:
        """Stop wall-follow, yaw in place ~360° so the camera sees all
        directions, then return so wall-follow can resume. K's planned
        'wall + periodic scan' strategy. Detection callback fires from
        a separate thread so YOLO keeps running through this."""
        log.info("wall: pausing for 360° scan (%.1fs at %.0f deg/s)",
                 WALL_SCAN_DURATION_S, WALL_SCAN_YAW_RATE_DEG)
        scan_end = time.monotonic() + WALL_SCAN_DURATION_S
        while time.monotonic() < scan_end and not state.abort_requested:
            state.vel_fwd = 0.0
            state.vel_right = 0.0
            state.vel_down = 0.0
            state.yaw_rate_deg = WALL_SCAN_YAW_RATE_DEG
            state.last_planner_progress = time.monotonic()
            await asyncio.sleep(period)
        # Stop yawing, brief settle before wall-follow resumes.
        state.yaw_rate_deg = 0.0
        await asyncio.sleep(0.5)
        # Reset K's FSM so it re-acquires the wall cleanly post-rotation.
        try:
            follower.state = "find_wall"
            follower._corner_ticks = 0
            follower._avoid_cooldown = 0
        except Exception:
            pass
        log.info("wall: scan complete; resuming wall-follow")

    async def _do_escape() -> None:
        """Stuck-recovery: K's WallFollower can deadlock when the depth
        filter (z > 1.5) puts every visible wall right at the filter
        boundary — drone oscillates avoid_front <-> find_wall and barely
        moves. We detect 'no XY progress for N seconds' upstream and
        kick into this escape: back up, yaw ~240°, then go forward. Most
        of the time this breaks the geometric trap and the FSM sees a
        new region of the world to react to."""
        log.warning("wall: STUCK detected — running escape (back %.1fs + yaw %.1fs + fwd %.1fs)",
                    WALL_ESCAPE_BACK_S, WALL_ESCAPE_YAW_S, WALL_ESCAPE_FWD_S)
        # Phase 1: reverse straight back
        end = time.monotonic() + WALL_ESCAPE_BACK_S
        while time.monotonic() < end and not state.abort_requested:
            state.vel_fwd = -WALL_ESCAPE_BACK_SPEED
            state.vel_right = 0.0
            state.vel_down = 0.0
            state.yaw_rate_deg = 0.0
            state.last_planner_progress = time.monotonic()
            await asyncio.sleep(period)
        # Phase 2: yaw in place
        end = time.monotonic() + WALL_ESCAPE_YAW_S
        while time.monotonic() < end and not state.abort_requested:
            state.vel_fwd = 0.0
            state.vel_right = 0.0
            state.vel_down = 0.0
            state.yaw_rate_deg = WALL_ESCAPE_YAW_RATE_DEG
            state.last_planner_progress = time.monotonic()
            await asyncio.sleep(period)
        # Phase 3: drive forward to leave the stuck pocket
        end = time.monotonic() + WALL_ESCAPE_FWD_S
        while time.monotonic() < end and not state.abort_requested:
            state.vel_fwd = WALL_ESCAPE_FWD_SPEED
            state.vel_right = 0.0
            state.vel_down = 0.0
            state.yaw_rate_deg = 0.0
            state.last_planner_progress = time.monotonic()
            await asyncio.sleep(period)
        # Brief settle, then reset K's FSM so it re-acquires fresh.
        state.vel_fwd = state.vel_right = state.vel_down = state.yaw_rate_deg = 0.0
        await asyncio.sleep(0.5)
        try:
            follower.state = "find_wall"
            follower._corner_ticks = 0
            follower._avoid_cooldown = 0
        except Exception:
            pass
        # Reset smoother (avoid leftover velocity from before escape)
        try:
            smoother.prev = np.zeros(4)
        except Exception:
            pass
        log.warning("wall: escape complete; resuming wall-follow")

    # Stuck-detector buffer: list of (timestamp, north, east) sampled @ ~1 Hz.
    pos_history = []  # rolling, trimmed in the loop
    last_escape_at = 0.0   # cooldown so we don't escape back-to-back
    ESCAPE_COOLDOWN = 15.0  # at least this long between escapes

    while time.monotonic() < deadline and not state.abort_requested:
        # Periodic 360 — K's hybrid plan (wall-follow + scan stations)
        if time.monotonic() >= next_scan_at:
            await _do_360_scan()
            next_scan_at = time.monotonic() + WALL_SCAN_EVERY_S
            # After a scan we'll have moved (yawed), reset stuck buffer.
            pos_history.clear()
            continue  # back to top of loop, re-check abort/deadline

        # Stuck detection: are we still where we were 10 sec ago?
        now = time.monotonic()
        pos_history.append((now, state.north_m, state.east_m))
        # Trim to the WALL_STUCK_WINDOW_S window
        cutoff = now - WALL_STUCK_WINDOW_S
        pos_history = [p for p in pos_history if p[0] >= cutoff]
        if len(pos_history) >= 5 and (now - last_escape_at) > ESCAPE_COOLDOWN:
            # Max XY drift in the window
            n_min = min(p[1] for p in pos_history)
            n_max = max(p[1] for p in pos_history)
            e_min = min(p[2] for p in pos_history)
            e_max = max(p[2] for p in pos_history)
            drift = math.hypot(n_max - n_min, e_max - e_min)
            window = pos_history[-1][0] - pos_history[0][0]
            if window >= WALL_STUCK_WINDOW_S * 0.9 and drift < WALL_STUCK_DISTANCE_M:
                log.warning(
                    "wall: stuck check tripped — drift=%.2fm over %.1fs (threshold %.2fm/%.1fs)",
                    drift, window, WALL_STUCK_DISTANCE_M, WALL_STUCK_WINDOW_S,
                )
                await _do_escape()
                last_escape_at = time.monotonic()
                pos_history.clear()
                continue

        with latest_lock:
            depth = latest["depth"]
        if depth is None:
            await asyncio.sleep(0.1)
            continue

        try:
            pts = _depth_to_points_3d(depth, K, np)
            regions = get_wall_distances(pts)
            vx_body, vy_body, vz_body, yaw_rate_rad = follower.compute(regions)
            smoothed = smoother.smooth((vx_body, vy_body, vz_body, yaw_rate_rad))
            state.vel_fwd       = float(smoothed[0])
            state.vel_right     = float(smoothed[1])
            state.vel_down      = float(smoothed[2])
            state.yaw_rate_deg  = float(smoothed[3]) * 180.0 / math.pi
            state.last_planner_progress = time.monotonic()
            ticks += 1
            now = time.monotonic()
            if now - last_log > 5.0:
                log.info(
                    "wall: state=%s front=%.2f right=%.2f "
                    "vel=(fwd=%.2f, right=%.2f, yawrate=%.0f deg/s) ticks=%d "
                    "next_scan_in=%.1fs",
                    follower.state, regions["front"], regions["right"],
                    state.vel_fwd, state.vel_right, state.yaw_rate_deg,
                    ticks, max(0.0, next_scan_at - now),
                )
                last_log = now
        except Exception:
            log.exception("planner_wall tick failed (continuing)")

        await asyncio.sleep(period)

    # Zero out the velocity setpoint cleanly before handing back to land path.
    state.vel_fwd = state.vel_right = state.vel_down = state.yaw_rate_deg = 0.0
    # Hold position for half a second by sending zero velocity, then flip
    # back to position mode targeting current pose (so the land step has a
    # stable position setpoint to fall back on if needed).
    await asyncio.sleep(0.5)
    state.target_north = state.north_m
    state.target_east = state.east_m
    state.target_down = state.down_m
    state.target_yaw = state.yaw_deg
    state.velocity_mode = False
    log.info(
        "planner_wall: exiting (ticks=%d, elapsed=%.1fs, hold pos N=%.2f E=%.2f)",
        ticks, WALL_FOLLOW_BUDGET_S - (deadline - time.monotonic()),
        state.target_north, state.target_east,
    )


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


async def run(
    detect_enabled: bool = True,
    fake_gcs_enabled: bool = True,
    map_enabled: bool = True,
    pattern: str = "square",
) -> int:
    state = SharedState()
    drone = Drone()
    detect_handle: Optional[dict] = None
    fake_gcs_handle: Optional[dict] = None
    map_handle: Optional[dict] = None
    map_task: Optional[asyncio.Task] = None
    # This run's working dir for outputs (annotated detection frames, etc.)
    run_dir = LOG_DIR.parent / f"run_{RUN_TS}"
    run_dir.mkdir(parents=True, exist_ok=True)

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

    # Spawn fake-GCS heartbeat BEFORE we connect to PX4 — gives PX4 time to
    # register a "GCS connected" before our preflight check runs.
    fake_gcs_handle = start_fake_gcs(enabled=fake_gcs_enabled)
    if fake_gcs_handle is not None:
        await asyncio.sleep(1.5)  # let a couple heartbeats land

    try:
        await drone.connect()
        await drone.set_sitl_workarounds()
        await asyncio.sleep(1.0)  # give params time to apply
        await drone.wait_until_armable(timeout_s=45.0)

        # Stand up the heavy setup BEFORE starting telemetry. setup_detection
        # loads a ~30 MB YOLO model which takes 5-10 seconds. If we did this
        # synchronously while a telemetry task was running, mavsdk_server's
        # outbound callback queue would back up (we observed queue size 16),
        # heartbeats would time out, and the gRPC channel to mavsdk_server
        # would reset — causing begin_offboard to fail with
        # "Connection reset by peer". Offloading to a worker thread keeps the
        # asyncio loop responsive (it still services fake-GCS heartbeats and
        # whatever other coroutines are waiting).
        if detect_enabled:
            detect_handle = await asyncio.to_thread(setup_detection, state, run_dir)
            if detect_handle is None:
                log.warning("detection unavailable — Phase 1-only flight")
        else:
            log.info("detection disabled by flag (--no-detect)")

        if map_enabled:
            map_handle = await asyncio.to_thread(setup_mapping, state, run_dir)
            if map_handle is None:
                log.warning("mapping unavailable — flight will proceed without map")
        else:
            log.info("mapping disabled by flag (--no-map)")

        # NOW start telemetry — after heavy setup is done, before arm.
        # The pumper, watchdogs and planner all need fresh pose data; they're
        # started further down right before begin_offboard.
        telem_task = asyncio.create_task(telemetry_monitor(drone, state), name="telemetry")
        await asyncio.sleep(0.5)

        await drone.arm_and_takeoff(altitude_m=abs(state.target_down))
        state.takeoff_ts = time.time()
        log.info("run clock started: takeoff at t=0")

        # Prime offboard with the current target, then start it + the pumper.
        await drone.begin_offboard(
            PositionNedYaw(state.target_north, state.target_east, state.target_down, state.target_yaw)
        )
        pumper_task = asyncio.create_task(setpoint_pumper(drone, state), name="pumper")
        wd_task = asyncio.create_task(watchdog(state), name="watchdog")
        div_task = asyncio.create_task(divergence_watchdog(state), name="divergence")
        clock_task = asyncio.create_task(flight_clock_logger(state), name="flight_clock")
        if map_handle is not None:
            map_task = asyncio.create_task(mapping_task(map_handle, state), name="mapping")

        # Run the chosen planner. Wraps in try so we always land afterward.
        try:
            if pattern == "wall":
                await planner_wall(state, map_handle)
            else:
                # 'square' and 'scan' both walk ACTIVE_WAYPOINTS
                await planner(state)
        finally:
            state.abort_requested = True
            bg_tasks = [pumper_task, wd_task, div_task, clock_task, telem_task]
            if map_task is not None:
                bg_tasks.append(map_task)
            for t in bg_tasks:
                t.cancel()
            for t in bg_tasks:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

        await drone.end_offboard()
        await drone.land_and_disarm()
        state.land_ts = time.time()
        if state.takeoff_ts is not None:
            log.info("run clock stopped: total flight time = %.1f s",
                     state.land_ts - state.takeoff_ts)
        teardown_detection(detect_handle, state)
        teardown_mapping(map_handle, state)
        stop_fake_gcs(fake_gcs_handle)
        write_run_summary(state, run_dir)
        log.info("run finished cleanly")
        return 0

    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt received")
        await emergency_land(drone, state)
        state.land_ts = time.time()
        teardown_detection(detect_handle, state)
        teardown_mapping(map_handle, state)
        stop_fake_gcs(fake_gcs_handle)
        write_run_summary(state, run_dir)
        return 130
    except Exception:
        log.exception("fatal error in run()")
        await emergency_land(drone, state)
        state.land_ts = time.time()
        teardown_detection(detect_handle, state)
        teardown_mapping(map_handle, state)
        stop_fake_gcs(fake_gcs_handle)
        write_run_summary(state, run_dir)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    ap.add_argument(
        "--no-detect",
        action="store_true",
        help="Disable Phase 2 detection pipeline; run Phase 1 (flight only).",
    )
    ap.add_argument(
        "--no-fake-gcs",
        action="store_true",
        help="Disable the pymavlink fake-GCS heartbeat. Use this if QGC is "
             "already running (port 14550 conflict) — though the script "
             "auto-detects that and skips cleanly anyway.",
    )
    ap.add_argument(
        "--no-map",
        action="store_true",
        help="Disable Phase 7 top-down mapping. Use this if matplotlib or "
             "the gz depth topic is unavailable; flight proceeds without "
             "the map (judges then observe 'no map' for tiebreakers).",
    )
    ap.add_argument(
        "--pattern",
        default="square",
        choices=("square", "scan", "wall"),
        help="Flight pattern. "
             "'square' = 2m smoke-test square (Phase 1 default, position mode). "
             "'scan' = hover at spawn, yaw 360° in 4×90° steps so the camera "
             "sees all cardinal directions (position mode, detection probe). "
             "'wall' = K's wall-following algorithm "
             "(searchctl/wall_following.py). Velocity mode, reads depth "
             "frames from the Phase 7 mapping pipeline, so requires --no-map "
             "to NOT be set.",
    )
    args = ap.parse_args()
    logging.getLogger().setLevel(args.log_level)

    global ACTIVE_WAYPOINTS
    ACTIVE_WAYPOINTS = SCAN_WAYPOINTS if args.pattern == "scan" else WAYPOINTS

    log.info("==== searchctl controller v0.5 (Phase 1 + 2 + 6 + 7 + wall + scan + escape) ====")
    log.info("logs at %s", LOG_FILE)
    log.info("detection:  %s", "OFF (--no-detect)" if args.no_detect else "ON")
    log.info("fake-GCS:   %s", "OFF (--no-fake-gcs)" if args.no_fake_gcs else "ON")
    log.info("mapping:    %s", "OFF (--no-map)" if args.no_map else "ON")
    if args.pattern == "wall":
        log.info("pattern:    wall (K's wall-following; velocity mode)")
        if args.no_map:
            log.error("--pattern wall requires the mapping pipeline (it reads "
                      "depth frames from there). Don't pass --no-map.")
            return 1
    else:
        log.info("pattern:    %s (%d WPs)", args.pattern, len(ACTIVE_WAYPOINTS))

    # Pre-load YOLO weights into the OS page cache BEFORE we touch PX4. The
    # cold-cache YOLO load takes ~5-10 s and dominates the timing-sensitive
    # setup window — if it runs after we've connected to mavsdk_server, the
    # asyncio loop is starved long enough that mavsdk's telemetry callback
    # queue backs up, heartbeats time out, and the gRPC channel resets
    # (causing arm/begin_offboard to fail with "Connection reset by peer").
    # Loading here moves the heavy disk I/O outside that window. Subsequent
    # setup_detection() YOLO load reads from RAM, ~0.5 s.
    if not args.no_detect:
        try:
            log.info("pre-loading YOLO weights to warm OS page cache...")
            t0 = time.monotonic()
            import sys as _sys, os as _os
            if WORKSHOP_CODES_DIR not in _sys.path:
                _sys.path.insert(0, WORKSHOP_CODES_DIR)
            _os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
            from ultralytics import YOLO as _PreYOLO
            _ = _PreYOLO(YOLO_WEIGHTS_DEFAULT)
            del _
            log.info("YOLO weights cached (%.1fs)", time.monotonic() - t0)
        except Exception:
            log.exception("YOLO pre-load failed (continuing — setup_detection will retry)")

    try:
        return asyncio.run(run(
            detect_enabled=not args.no_detect,
            fake_gcs_enabled=not args.no_fake_gcs,
            map_enabled=not args.no_map,
            pattern=args.pattern,
        ))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
