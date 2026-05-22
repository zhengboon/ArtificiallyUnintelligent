"""
RoboVerse search controller — Phases 1 (flight) + 2 (detection) + 6 (fake-GCS) + 7 (mapping + timer).

Single-file asyncio controller that:
  * Connects to PX4 SITL on udp://:14540
  * Sets the SITL battery/supply circuit-breaker params from code
    (no need to type them in the px4> console)
  * Verifies home_position_ok is set (operator still needs to run
    `commander set_ekf_origin ...` in the px4 console — see README)
  * Arms, takes off, wall-follows using depth camera, lands, disarms
  * Runs a setpoint pumper task at 20 Hz so PX4 never loses heartbeat
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
  * (Phase 7) Tracks per-run wall-clock from takeoff->land and writes a
    run_summary.json with detection list + timing for A's scoring script
  * Logs everything to logs/run_<ts>.log AND stdout
  * On *any* failure path (exception, signal, watchdog trigger),
    runs an emergency_land coroutine that lands + disarms before exit

Detection, fake-GCS, and mapping are each opt-out via --no-detect,
--no-fake-gcs, --no-map. If any dependency (ultralytics, gz.transport13,
matplotlib, pymavlink, the workshop's Detector.py) can't be imported, the
controller logs a warning and proceeds with whatever remains — flight is
never blocked by an optional pipeline failing to start.
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
from mavsdk.offboard import OffboardError, VelocityNedYaw

# Make codes/Codes/ importable from searchctl/
CODES_DIR = os.path.join(os.path.dirname(__file__), '..', 'codes', 'Codes')
sys.path.insert(0, CODES_DIR)
# gz.msgs10 needs the pure-Python protobuf parser; without this env var the
# import explodes with "Descriptors cannot be created directly" on the VM's
# protobuf version. Set BEFORE depth_receiver / depthcloud imports so the
# transitive gz.msgs10 imports see it.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
# wall_following.py is in the same directory as controller.py
from wall_following import get_wall_distances, WallFollower, VelocitySmoother, body_to_ned
from depth_receiver import DepthReceiver
from depthcloud import PointCloud

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

    target_vel_north: float = 0.0   # m/s
    target_vel_east:  float = 0.0   # m/s
    target_vel_down:  float = 0.0   # m/s (0 = hold altitude)
    target_yaw:       float = 0.0   # degrees absolute

    # Wall follower state
    current_yaw_cmd:  float = 0.0   # integrated yaw heading (degrees)

    # Heartbeat / liveness
    last_planner_progress: float = field(default_factory=time.monotonic)
    abort_requested: bool = False

    # ---- Detection state (Phase 2; populated by detection_callback) ----
    detection_count: int = 0
    detections: list = field(default_factory=list)
    last_detection_at: Optional[float] = None

    # ---- Run-timing state (Phase 7; populated by run()) ----
    takeoff_ts: Optional[float] = None
    land_ts: Optional[float] = None

    # ---- Mapping state (Phase 7; populated by mapping task) ----
    map_points_count: int = 0


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
        """Wait for PX4 to declare ready-to-arm.

        For x500_vision (no GPS) `is_armable` may stay False forever because
        it includes a global-position check that vision-only drones can't
        satisfy. We accept the equivalent vision-drone armable condition:
        home_position_ok AND local_position_ok. PX4 will reject the actual
        arm() call if anything else is still wrong, so this is safe.
        """
        log.info("waiting for armable (is_armable OR (home_ok AND local_ok))...")
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
            if home_ok and local_ok:
                log.info("home_ok=True AND local_ok=True (vision-drone armable); OK to arm")
                return
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"not armable after {timeout_s}s "
                    f"(armable={armable}, home_ok={home_ok}, local_ok={local_ok}). "
                    "Did you run `commander set_ekf_origin 47.397742 8.545594 488.0` "
                    "in the px4> console?"
                )
            await asyncio.sleep(0.5)

    async def arm_and_takeoff(self, altitude_m: float = 2.0, state: SharedState = None) -> None:
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

        # Wait until actually at altitude
        deadline = time.monotonic() + 50.0
        while time.monotonic() < deadline:
            target_down = -altitude_m * 0.8  # 80% of target altitude is close enough
            if state.down_m < target_down:
                log.info("altitude reached: down_m=%.2f", state.down_m)
                await asyncio.sleep(1.0)
                break
            await asyncio.sleep(0.2)
        else:
            raise RuntimeError("takeoff timed out — drone never reached altitude")

        log.info("takeoff complete (assumed; pumper will hold altitude)")

    async def begin_offboard(self, initial: VelocityNedYaw) -> None:
        await self.drone.offboard.set_velocity_ned(initial)
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
    """Continuously push the current target setpoint to PX4."""
    period = 1.0 / hz
    sent = 0
    while not state.abort_requested:
        try:
            await drone.drone.offboard.set_velocity_ned(
                VelocityNedYaw(
                    state.target_vel_north,
                    state.target_vel_east,
                    state.target_vel_down,
                    state.target_yaw,
                )
            )
            sent += 1
            if sent % (int(hz) * 5) == 0:  # every ~5 seconds
                log.debug(
                    "pumper @ %d  vel=(%.2f, %.2f, %.2f) yaw=%.0f",
                    sent, state.target_vel_north, state.target_vel_east,
                    state.target_vel_down, state.target_yaw,
                )
        except OffboardError as e:
            log.debug("pumper offboard error (will retry): %s", e)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("unexpected error in setpoint_pumper")
        await asyncio.sleep(period)


async def telemetry_monitor(drone: Drone, state: SharedState) -> None:
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
# Detection pipeline (Phase 2)
# ---------------------------------------------------------------------------
IMAGE_TOPIC_DEFAULT = (
    "/world/roboverse/model/x500_vision_0/link/camera_link"
    "/sensor/IMX214/image"
)

WORKSHOP_CODES_DIR = os.path.expanduser("~/ArtificiallyUnintelligent/codes/Codes")
YOLO_WEIGHTS_DEFAULT = os.path.expanduser("~/ArtificiallyUnintelligent/models/best.pt")
DETECT_CONFIDENCE_DEFAULT = 0.7


# def _import_detection_deps():
#     if WORKSHOP_CODES_DIR not in sys.path:
#         sys.path.insert(0, WORKSHOP_CODES_DIR)
#     os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
#     import cv2
#     import numpy as np
#     from gz.transport13 import Node
#     from gz.msgs10.image_pb2 import Image
#     from Detector import Detector
#     return cv2, np, Node, Image, Detector


def setup_detection(state, run_dir, weights_path=YOLO_WEIGHTS_DEFAULT, confidence=DETECT_CONFIDENCE_DEFAULT, image_topic=IMAGE_TOPIC_DEFAULT):
    try:
        import cv2
        import numpy as np
        from gz.transport13 import Node
        from gz.msgs10.image_pb2 import Image
        from ultralytics import YOLO
        import threading
    except Exception:
        log.exception("could not import detection deps; running without detection")
        return None

    det_dir = run_dir / "detections"
    det_dir.mkdir(parents=True, exist_ok=True)

    if not os.path.exists(weights_path):
        log.warning("model file not found at %s; detection disabled", weights_path)
        return None

    log.info("loading YOLO model from %s", weights_path)
    model = YOLO(weights_path)
    log.info("YOLO model loaded")

    seq_counter = {"n": 0}

    processing = {"busy": False}
    def image_callback(msg):
        if processing["busy"]:
            return
        processing["busy"] = True
        # snapshot the frame data immediately and return
        try:
            frame = np.frombuffer(msg.data, dtype=np.uint8).copy()
            frame = frame.reshape((msg.height, msg.width, 3))
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            pose = (state.north_m, state.east_m, state.down_m, state.yaw_deg)
        except Exception:
            processing["busy"] = False
            return

        # run YOLO in a background thread so this callback returns instantly
        def run_inference():
            try:
                results = model(frame_bgr, conf=confidence, verbose=False)[0]
                boxes = [b for b in results.boxes if int(b.cls) != 2]
                if len(boxes) > 0 and state.in_air:
                    seq_counter["n"] += 1
                    annotated = results.plot()
                    filename = str(det_dir / f"detected_{seq_counter['n']:04d}.jpg")
                    cv2.imwrite(filename, annotated)
                    state.detection_count += 1
                    state.last_detection_at = time.monotonic()
                    log.info(
                        "detection: count=%d pose=(N=%.2f E=%.2f D=%.2f yaw=%.0f) -> %s",
                        state.detection_count, pose[0], pose[1], pose[2], pose[3],
                        os.path.basename(filename),
                    )
            except Exception:
                log.exception("inference failed")
            finally:
                processing["busy"] = False

        threading.Thread(target=run_inference, daemon=True).start()

    node = Node()
    if not node.subscribe(Image, image_topic, image_callback):
        log.error("could not subscribe to image topic %s", image_topic)
        return None
    log.info("detection: subscribed to %s", image_topic)

    return {"node": node, "model": model}


def teardown_detection(handle: Optional[dict], state: SharedState) -> None:
    if handle is None:
        return
    log.info("detection: total fired = %d", state.detection_count)
    handle["node"] = None


# ---------------------------------------------------------------------------
# Top-down mapping pipeline (Phase 7)
# ---------------------------------------------------------------------------
DEPTH_TOPIC_DEFAULT = "/depth_camera"
DEPTH_K = (
    (433.0,   0.0, 320.0),
    (  0.0, 433.0, 240.0),
    (  0.0,   0.0,   1.0),
)
MAP_RENDER_INTERVAL_S = 1.0
MAP_MAX_POINTS = 200_000


def _import_mapping_deps():
    if WORKSHOP_CODES_DIR not in sys.path:
        sys.path.insert(0, WORKSHOP_CODES_DIR)
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from gz.transport13 import Node
    from gz.msgs10.image_pb2 import Image
    from top_down import depth_to_xy_map
    return np, plt, Node, Image, depth_to_xy_map


def setup_mapping(
    state: SharedState,
    run_dir: Path,
    depth_topic: str = DEPTH_TOPIC_DEFAULT,
) -> Optional[dict]:
    try:
        np, plt, Node, Image, depth_to_xy_map = _import_mapping_deps()
    except Exception:
        log.exception("could not import mapping deps; running without map")
        return None

    map_dir = run_dir / "map_frames"
    map_dir.mkdir(parents=True, exist_ok=True)
    final_png = run_dir / "map.png"
    final_npy = run_dir / "map_points.npy"

    latest = {"depth": None, "pose": None, "ts": 0.0}
    latest_lock = threading.Lock()

    points = __import__('numpy').empty((0, 2), dtype=__import__('numpy').float32)

    K = __import__('numpy').array(DEPTH_K, dtype=__import__('numpy').float32)

    def depth_callback(msg):
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
        try:
            fig, ax = plt.subplots(figsize=(8, 8))
            if pts.shape[0] > 0:
                dists = np.linalg.norm(pts, axis=1)
                ax.scatter(
                    pts[:, 1],
                    pts[:, 0],
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
    }
    return handle


def _local_to_ned_global(local_xy, north, east, yaw_rad, np_mod):
    Xc = local_xy[:, 0]
    Zc = local_xy[:, 1]
    c = np_mod.cos(yaw_rad)
    s = np_mod.sin(yaw_rad)
    north_g = north + Zc * c - Xc * s
    east_g = east + Zc * s + Xc * c
    return np_mod.column_stack([north_g, east_g])


async def mapping_task(handle: Optional[dict], state: SharedState) -> None:
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
        points = np.vstack([points, global_pts.astype(np.float32)])
        if points.shape[0] > MAP_MAX_POINTS:
            points = points[-MAP_MAX_POINTS:]
        handle["points"] = points
        state.map_points_count = int(points.shape[0])

        now = time.monotonic()
        if now - handle["last_render"] >= MAP_RENDER_INTERVAL_S:
            handle["last_render"] = now
            handle["seq"] += 1
            seq_path = map_dir / f"map_{handle['seq']:04d}.png"
            await asyncio.to_thread(render, points.copy(), pose, final_png)
            await asyncio.to_thread(render, points.copy(), pose, seq_path)


def teardown_mapping(handle: Optional[dict], state: SharedState) -> None:
    if handle is None:
        return
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
    try:
        last_pose = handle["latest"]["pose"]
        handle["render"](pts, last_pose, handle["final_png"])
        log.info("mapping: final map saved to %s", handle["final_png"].name)
    except Exception:
        log.exception("final map render failed")
    handle["node"] = None
    handle["stop"].set()


# ---------------------------------------------------------------------------
# Run summary (Phase 7) + detection dedup (Phase 4) + live STATUS.txt
# ---------------------------------------------------------------------------
# Per qualifier PDF (info_2026-05-21/RoboVerse_2026_Qualifier.pdf):
#   Eligibility (uni): >=1 red + >=1 yellow.  Score = 50 pts per unique yellow
#   + 100 pts per unique red.  Bonus: +20 pts per 30s under 5min for finding
#   ALL of a colour.
#
# K's model fires repeatedly on the same barrel as the drone moves past it,
# so we cluster detections within 1.5 m (drone pose at detect time, NED) as
# "same physical barrel". Crude but useful — the per-frame list still ships
# in the JSON for full audit.
DETECTION_CLUSTER_RADIUS_M = 1.5


def compute_unique_detections(detections: list, radius_m: float = DETECTION_CLUSTER_RADIUS_M) -> dict:
    """Cluster detection records into unique physical barrels.
    Returns: {"yellow_barrel": int, "red_barrel": int, "toxic_barrel": int, "total": int}."""
    counts = {"yellow_barrel": 0, "red_barrel": 0, "toxic_barrel": 0, "total": 0}
    if not detections:
        return counts
    by_class: dict[str, list[tuple[float, float]]] = {}
    for d in detections:
        cls = (d.class_name or "").lower().replace(" ", "_")
        try:
            n, e, *_ = d.pose_at_detect
        except Exception:
            continue
        clusters = by_class.setdefault(cls, [])
        merged = False
        for cn, ce in clusters:
            if math.hypot(n - cn, e - ce) <= radius_m:
                merged = True
                break
        if not merged:
            clusters.append((float(n), float(e)))
    total = 0
    for cls, pts in by_class.items():
        counts[cls] = len(pts)
        total += len(pts)
    counts["total"] = total
    return counts


def _build_summary_dict(state: SharedState) -> dict:
    unique = compute_unique_detections(state.detections)
    return {
        "run_ts": RUN_TS,
        "takeoff_ts": state.takeoff_ts,
        "land_ts": state.land_ts,
        "flight_seconds": (
            (state.land_ts - state.takeoff_ts)
            if (state.takeoff_ts and state.land_ts) else None
        ),
        "detection_count": state.detection_count,
        "unique_detections": unique,
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


def write_run_summary(state: SharedState, run_dir: Path) -> None:
    import json
    summary = _build_summary_dict(state)
    out_path = run_dir / "run_summary.json"
    try:
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        log.info("run summary written to %s (unique: %s)",
                 out_path.name, summary["unique_detections"])
    except Exception:
        log.exception("could not write run_summary.json")


def _format_status_text(state: SharedState, summary: dict) -> str:
    """Plain-text snapshot of flight state for run_<ts>/STATUS.txt.
    Written every 5 s; judges can cat it without a terminal viewer."""
    elapsed = None
    if state.takeoff_ts is not None:
        end = state.land_ts if state.land_ts is not None else time.time()
        elapsed = end - state.takeoff_ts
    unique = summary["unique_detections"]
    y_uniq = unique.get("yellow_barrel", 0)
    r_uniq = unique.get("red_barrel", 0)
    eligible = y_uniq >= 1 and r_uniq >= 1
    base_score = 50 * y_uniq + 100 * r_uniq if eligible else 0
    bonus_remaining = max(0.0, 300.0 - elapsed) if elapsed is not None else None
    bonus_window_status = (
        "EXPIRED" if (bonus_remaining is not None and bonus_remaining <= 0)
        else (f"{bonus_remaining:5.1f}s remaining" if bonus_remaining is not None else "—")
    )
    if state.land_ts is not None:
        run_state = "LANDED"
    elif state.abort_requested:
        run_state = "ABORTED"
    else:
        run_state = "RUNNING"
    if run_state == "LANDED":
        next_hint = "RUN COMPLETE — copy run dir to USB, show judge."
    elif state.abort_requested:
        next_hint = "ABORT IN PROGRESS — wait for land + disarm."
    elif not eligible:
        if y_uniq == 0 and r_uniq == 0:
            next_hint = "no detections yet — keep flying, scan more angles"
        elif y_uniq == 0:
            next_hint = "need a YELLOW for eligibility — keep searching"
        else:
            next_hint = "need a RED for eligibility — keep searching"
    else:
        if bonus_remaining and bonus_remaining > 30:
            next_hint = "ELIGIBLE — bonus window open, look for more barrels"
        elif bonus_remaining and bonus_remaining > 0:
            next_hint = "ELIGIBLE — bonus closing, consider early-land"
        else:
            next_hint = "ELIGIBLE — bonus window closed, just maximise count"
    lines = [
        f"BrainHack 2026 RoboVerse — run {RUN_TS}",
        f"  status: {run_state}",
        f"  flight time: {('%.1f s' % elapsed) if elapsed is not None else '—'}",
        f"  bonus window (<5:00): {bonus_window_status}",
        f"  armed: {state.armed}  in_air: {state.in_air}  mode: {state.flight_mode}",
        f"  pose: N={state.north_m:+.2f}m  E={state.east_m:+.2f}m  D={state.down_m:+.2f}m  yaw={state.yaw_deg:.0f}°",
        "",
        f"  ELIGIBLE FOR SCORING: {'YES' if eligible else 'NO (need >=1 yellow AND >=1 red)'}",
        f"  unique barrels found:  yellow={y_uniq}  red={r_uniq}  toxic={unique.get('toxic_barrel', 0)}",
        f"  base score estimate:   {base_score} pts ({y_uniq}*50 + {r_uniq}*100, only counts if eligible)",
        f"  raw detection frames:  {state.detection_count}",
        f"  map points accumulated: {state.map_points_count}",
        "",
        f"  NEXT: {next_hint}",
        "",
    ]
    last = state.detections[-3:]
    if last:
        lines.append("  recent detections:")
        for d in last:
            n, e, _, _ = (list(d.pose_at_detect) + [0, 0, 0, 0])[:4]
            lines.append(f"    #{d.seq:03d} {d.class_name:<14s} conf={d.confidence:.2f} at N={n:+.1f} E={e:+.1f}")
    return "\n".join(lines) + "\n"


async def incremental_status_writer(state: SharedState, run_dir: Path, interval_s: float = 5.0) -> None:
    """Write run_summary.json + STATUS.txt every interval_s seconds during
    flight. Crash-robust: if the controller dies mid-run we still have a
    ~5s-stale snapshot of detections + timings on disk."""
    import json
    json_path = run_dir / "run_summary.json"
    status_path = run_dir / "STATUS.txt"
    while not state.abort_requested:
        try:
            summary = _build_summary_dict(state)
            await asyncio.to_thread(
                json_path.write_text,
                json.dumps(summary, indent=2),
                encoding="utf-8",
            )
            await asyncio.to_thread(
                status_path.write_text,
                _format_status_text(state, summary),
                encoding="utf-8",
            )
        except Exception:
            log.exception("incremental_status_writer tick failed (continuing)")
        await asyncio.sleep(interval_s)


# ---------------------------------------------------------------------------
# Fake-GCS heartbeat (Phase 6)
# ---------------------------------------------------------------------------
FAKE_GCS_PORT = 14550


def _fake_gcs_pump(stop_event: "object", port: int = FAKE_GCS_PORT) -> None:
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
# Main + signal handling
# ---------------------------------------------------------------------------
async def emergency_land(drone: Drone, state: SharedState) -> None:
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


# --- Bonus-mode tuning (per qualifier PDF: 20 pts / 30 s under 5 min for
# finding ALL of a colour) ---
BONUS_HARD_LAND_S        = 260.0  # ~4:20; leaves ~40 s for the land sequence
                                  # to finish inside the 5-min bonus window
BONUS_DUAL_COLOUR_HOLD_S = 25.0   # once both colours seen, hold this long
                                  # before landing (lets YOLO find more)
PLATEAU_S_DEFAULT        = 60.0   # non-bonus: land if no new unique cluster
                                  # for this long AND both colours present


async def run(
    detect_enabled: bool = True,
    fake_gcs_enabled: bool = True,
    map_enabled: bool = True,
    bonus_mode: bool = False,
    altitude_m: float = 3.0,
    confidence: float = DETECT_CONFIDENCE_DEFAULT,
) -> int:
    state = SharedState()
    drone = Drone()
    detect_handle: Optional[dict] = None
    fake_gcs_handle: Optional[dict] = None
    map_handle: Optional[dict] = None
    map_task: Optional[asyncio.Task] = None
    run_dir = LOG_DIR.parent / f"run_{RUN_TS}"
    run_dir.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: setattr(state, "abort_requested", True))
        except NotImplementedError:
            pass

    fake_gcs_handle = start_fake_gcs(enabled=fake_gcs_enabled)
    if fake_gcs_handle is not None:
        await asyncio.sleep(1.5)

    try:
        await drone.connect()
        await drone.set_sitl_workarounds()
        await asyncio.sleep(1.0)
        await drone.wait_until_armable(timeout_s=45.0)

        telem_task = asyncio.create_task(telemetry_monitor(drone, state), name="telemetry")
        await asyncio.sleep(0.5)

        if map_enabled:
            map_handle = setup_mapping(state, run_dir)
            if map_handle is None:
                log.warning("mapping unavailable — flight will proceed without map")
        else:
            log.info("mapping disabled by flag (--no-map)")

        await drone.arm_and_takeoff(altitude_m=altitude_m, state=state)
        state.takeoff_ts = time.time()
        log.info("run clock started: takeoff at t=0")

        # Start detection AFTER takeoff so it doesn't interfere with climb
        if detect_enabled:
            detect_handle = await asyncio.to_thread(
                setup_detection, state, run_dir, YOLO_WEIGHTS_DEFAULT, confidence,
            )
            if detect_handle is None:
                log.warning("detection unavailable")
        else:
            log.info("detection disabled by flag (--no-detect)")

        # Prime offboard with a zero velocity setpoint, then start
        await drone.begin_offboard(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))

        # Prime offboard with a zero velocity setpoint, then start
        await drone.begin_offboard(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
        pumper_task = asyncio.create_task(setpoint_pumper(drone, state), name="pumper")
        # wd_task     = asyncio.create_task(watchdog(state), name="watchdog")
        wd_task = asyncio.create_task(watchdog(state, timeout_s=60.0), name="watchdog")
        status_task = asyncio.create_task(
            incremental_status_writer(state, run_dir), name="status_writer",
        )
        if map_handle is not None:
            map_task = asyncio.create_task(mapping_task(map_handle, state), name="mapping")

        # Wall-following loop
        wall_follower = WallFollower()
        wf_smoother   = VelocitySmoother()
        depth_cam     = DepthReceiver("/depth_camera")
        pc            = PointCloud(320, 320, 320, 240)
        LOOP_DT       = 0.05

        await asyncio.sleep(0.1)              # brief wait for telemetry
        state.target_yaw = state.yaw_deg     # prevent pumper from yawing to 0
        state.current_yaw_cmd = state.yaw_deg
        await asyncio.sleep(2.0)             # let drone stabilize at altitude
        state.current_yaw_cmd = state.yaw_deg  # re-snapshot after stabilize

        # Bonus-mode bookkeeping. We watch detection unique-counts on every
        # tick and trigger early-exit on one of three signals:
        #   * hard time cap (bonus mode only) — land before the 5-min bonus
        #     deadline so we can bank a non-zero bonus,
        #   * dual-colour hold expired (bonus mode) — both colours seen + a
        #     short hold to let YOLO find more, then land,
        #   * detection plateau (both modes) — both colours seen + no new
        #     unique cluster for a while.
        # Logic shared with the planner_wall path in our pre-merge zb branch.
        loop_start_ts = time.monotonic()
        bonus_deadline = loop_start_ts + BONUS_HARD_LAND_S
        plateau_window = 30.0 if bonus_mode else PLATEAU_S_DEFAULT
        last_unique_total = 0
        last_unique_change_at = loop_start_ts
        dual_colour_first_seen_at: Optional[float] = None
        early_exit_reason: Optional[str] = None
        if bonus_mode:
            log.info(
                "BONUS MODE: hard-land deadline at T+%.0fs, dual-colour hold %.0fs, plateau %.0fs",
                BONUS_HARD_LAND_S, BONUS_DUAL_COLOUR_HOLD_S, plateau_window,
            )

        try:
            while not state.abort_requested:
                # --- Early-exit checks (cheap; run every tick) ---
                now = time.monotonic()
                if bonus_mode and now >= bonus_deadline:
                    early_exit_reason = (
                        f"bonus mode: hard land at T+{now-loop_start_ts:.1f}s "
                        f"(deadline {BONUS_HARD_LAND_S:.0f}s)"
                    )
                    break
                unique = compute_unique_detections(state.detections)
                total = unique["total"]
                if total != last_unique_total:
                    last_unique_total = total
                    last_unique_change_at = now
                have_both = unique.get("yellow_barrel", 0) >= 1 and unique.get("red_barrel", 0) >= 1
                if have_both and dual_colour_first_seen_at is None:
                    dual_colour_first_seen_at = now
                    log.info(
                        "EARLY-EXIT armed: BOTH COLOURS detected (yellow=%d, red=%d) "
                        "at T+%.1fs",
                        unique["yellow_barrel"], unique["red_barrel"],
                        now - loop_start_ts,
                    )
                if bonus_mode and dual_colour_first_seen_at is not None \
                        and (now - dual_colour_first_seen_at) >= BONUS_DUAL_COLOUR_HOLD_S:
                    early_exit_reason = (
                        f"bonus mode: dual-colour hold complete "
                        f"({BONUS_DUAL_COLOUR_HOLD_S:.0f}s after first dual-colour)"
                    )
                    break
                if have_both and (now - last_unique_change_at) >= plateau_window:
                    early_exit_reason = (
                        f"plateau: no new unique for {now-last_unique_change_at:.1f}s "
                        f"({unique['yellow_barrel']}Y/{unique['red_barrel']}R)"
                    )
                    break

                depth = depth_cam.get_frame()
                if depth is None:
                    await asyncio.sleep(LOOP_DT)
                    continue

                points = pc.convert(depth)
                regions = get_wall_distances(points)

                log.info(
                    "front=%.2f  front_right=%.2f  right=%.2f  wf_state=%s",
                    regions['front'], regions['front_right'],
                    regions['right'], wall_follower.state,
                )

                vx, vy, vz, yaw_rate = wall_follower.compute(regions)

                # Overlay obstacle avoidance
                if regions['front'] < 2.0:
                    vx -= 0.7 * (2.0 - regions['front'])
                # if regions['left'] < 1.0:
                #     vy += 0.3 * (1.0 - regions['left'])

                vx, vy, vz, yaw_rate = wf_smoother.smooth((vx, vy, vz, yaw_rate))

                # Update yaw command by integrating yaw_rate
                state.current_yaw_cmd += math.degrees(yaw_rate) * LOOP_DT
                state.current_yaw_cmd = (state.current_yaw_cmd + 180) % 360 - 180

                # Rotate body-frame velocity -> NED using current yaw
                north, east = body_to_ned(vx, vy, state.current_yaw_cmd)
                state.target_vel_north = north
                state.target_vel_east  = east
                state.target_vel_down  = vz
                state.target_yaw       = state.current_yaw_cmd
                state.last_planner_progress = time.monotonic()

                await asyncio.sleep(LOOP_DT)

        finally:
            if early_exit_reason is not None:
                log.info("wall-follow EARLY EXIT (T+%.1fs): %s",
                         time.monotonic() - loop_start_ts, early_exit_reason)
            state.abort_requested = True
            bg_tasks = [pumper_task, wd_task, status_task, telem_task]
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
        help="Disable Phase 7 top-down mapping.",
    )
    ap.add_argument(
        "--bonus",
        action="store_true",
        help="Tune for the qualifier 5-min bonus window. Hard-lands at ~4:20 "
             "(BONUS_HARD_LAND_S) and early-exits as soon as both yellow + "
             "red are detected (plus a short hold). Use this for the FIRST "
             "qualifier attempt to bank bonus points.",
    )
    ap.add_argument(
        "--altitude",
        type=float,
        default=3.0,
        help="Takeoff altitude in metres (positive). Default 3.0 (K's tuning). "
             "Bump to 4.0 if reds in lockers look high at venue; drop to 2.0 "
             "for safer hover.",
    )
    ap.add_argument(
        "--conf",
        type=float,
        default=DETECT_CONFIDENCE_DEFAULT,
        help=f"YOLO confidence threshold. Default {DETECT_CONFIDENCE_DEFAULT} "
             "(K's tuning). Drop to 0.25-0.35 at venue if K's model isn't "
             "firing on the actual barrels — org confirmed no penalty for "
             "incorrect detections (21/5).",
    )
    args = ap.parse_args()
    logging.getLogger().setLevel(args.log_level)

    log.info("==== searchctl controller v0.5 (K wall-follow + zb bonus/status/dedup) ====")
    log.info("logs at %s", LOG_FILE)
    log.info("detection:  %s", "OFF (--no-detect)" if args.no_detect else "ON")
    log.info("fake-GCS:   %s", "OFF (--no-fake-gcs)" if args.no_fake_gcs else "ON")
    log.info("mapping:    %s", "OFF (--no-map)" if args.no_map else "ON")
    log.info("bonus:      %s", "ON (hard-land ~4:20)" if args.bonus else "OFF")
    log.info("altitude:   %.1f m   conf threshold: %.2f", args.altitude, args.conf)
    try:
        return asyncio.run(run(
            detect_enabled=not args.no_detect,
            fake_gcs_enabled=not args.no_fake_gcs,
            map_enabled=not args.no_map,
            bonus_mode=args.bonus,
            altitude_m=args.altitude,
            confidence=args.conf,
        ))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())