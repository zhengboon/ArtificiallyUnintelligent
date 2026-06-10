"""PX4-ROS2 mapping mission for the finals drone (MAVSDK-free).

This is the drop-in replacement for ``controller.py`` on the actual finals
drone, whose flight controller speaks PX4 over micro-XRCE-DDS (ROS2), NOT
MAVLink. It reuses the proven, platform-independent vision stack
(``mapping`` / ``realsense`` / ``run_writer`` / ``validity``) and swaps the
flight + pose layer.

POSE SOURCES (``--pose``)
-------------------------
- ``px4``  (default): pose from ``/fmu/out/vehicle_local_position`` via
  ``px4_ros.Px4Ros2Flight``. REQUIRES the ``px4_msgs`` package to match the
  PX4 firmware version, or messages fail to deserialize ("Fast CDR exception")
  and pose stays invalid.
- ``uwb``: pose from the UWB ``/uwb_tag`` ``geometry_msgs/PoseStamped`` topic
  (standard message — immune to the px4_msgs version problem). Altitude is not
  in that topic, so ``--assumed-alt`` supplies it. Good for grounded /
  hand-carried mapping and as the fallback when PX4 pose won't decode. Cannot
  drive autonomous flight (``--fly`` requires ``--pose px4``).

RUN PREREQUISITES (on the drone)
--------------------------------
    source ~/ros2_ws/install/setup.bash
    pkill -f MicroXRCEAgent; bash ~/start_micro.sh &   # ONE XRCE agent
    bash ~/start_uwb.sh                                # for --pose uwb
    # do NOT run start_rs.sh — this process opens the RealSense directly.

MODES (test in order)
---------------------
    --check    Connect, print live pose (+ arm/offboard status for px4), ~10 s,
               never arms.
    --nofly    Real pose + RealSense + ArUco + occupancy + artifacts in place;
               never arms/moves. (Default.)
    --fly      Autonomous offboard survey (requires --pose px4). Lands+disarms
               on exit/Ctrl-C.

Examples
--------
    python3 -m mapping_drone.px4_mission --check --pose uwb
    python3 -m mapping_drone.px4_mission --nofly --pose uwb --aruco-dict 7X7_1000
    python3 -m mapping_drone.px4_mission --fly --aruco-dict 7X7_1000 \
        --waypoints-from-json configs/waypoints_10jun.json --takeoff-alt 4.0
"""

from __future__ import annotations

import argparse
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

logger = logging.getLogger("mapping_drone.px4_mission")

TAKEOFF_ALT_DEFAULT = 4.0
REACH_XY_M = 0.30
REACH_Z_M = 0.30
FLY_TO_TIMEOUT_S = 40.0
FRAMES_PER_WAYPOINT = 8
DEDUPE_RADIUS_M = 0.5
POSE_WAIT_S = 15.0
ARM_OFFBOARD_WAIT_S = 8.0
DEFAULT_WAYPOINTS = [(0.0, 0.0, 4.0), (2.0, 0.0, 4.0), (2.0, 2.0, 4.0), (0.0, 2.0, 4.0)]


def _world_distance(a, b) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class UwbPoseSource:
    """Pose from the UWB /uwb_tag topic (standard PoseStamped, no px4_msgs).

    Exposes the same ``get_pose() -> (n, e, down, yaw_deg, valid)`` shape as
    ``px4_ros.Px4Ros2Flight`` so the mission code is source-agnostic. The UWB
    topic carries no altitude or heading, so ``down`` is fixed from
    ``assumed_alt`` and yaw is 0 (north). World XY of detections is accurate to
    the UWB fix; world Z scales with ``assumed_alt`` — set it close to the real
    camera height for accurate marker world coords.
    """

    def __init__(self, assumed_alt_m: float) -> None:
        self._uwb = UwbNode()
        self._alt = float(assumed_alt_m)

    def start(self) -> None:
        self._uwb.start()

    def stop(self) -> None:
        self._uwb.stop()

    def get_pose(self):
        n, e, ready = self._uwb.get_position()
        alt = self._uwb.get_altitude()        # real ENU z-up from /uwb_tag if present
        down = -alt if alt is not None else -self._alt
        return n, e, down, 0.0, ready


class Px4Mission:
    def __init__(self, args, pose_source, flight, realsense, run_writer) -> None:
        self.args = args
        self.pose = pose_source          # has get_pose() -> 5-tuple
        self.flight = flight             # Px4Ros2Flight or None (no autonomy)
        self.realsense = realsense
        self.run_writer = run_writer
        self.detector = ArucoDetector(dict_name=getattr(args, "aruco_dict", "6X6_250"))
        self.grid = OccupancyGrid(resolution_m=0.05, size_m=20.0)
        self.sightings: list[ArucoSighting] = []
        self._seq = 0
        self._validity_cache: dict[int, Optional[bool]] = {}
        self._stop = False
        self.state = "INIT"
        self.started_at = 0.0

    # ---- helpers ---------------------------------------------------
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
        return [
            {"aruco_id": aid, "world_xyz_m": s.world_xyz_m, "valid": self._validity_for(aid)}
            for aid, s in seen.items()
        ]

    def _write_status(self) -> None:
        n, e, down, yaw, _ = self.pose.get_pose()
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
                n, e, down, yaw, _ = self.pose.get_pose()
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
            n, e, down, yaw, _ = self.pose.get_pose()
            try:
                self.grid.integrate(frame, (n, e, down, yaw), self.args.gimbal_pitch)
            except Exception as exc:
                logger.debug("grid integrate failed: %s", exc)
            for aruco_id, pc, bbox in self.detector.detect_in_frame(frame):
                self._register_sighting(frame, aruco_id, pc, bbox)
            time.sleep(0.05)

    def _await_pose(self, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline and not self._stop:
            if self.pose.get_pose()[4]:
                return True
            time.sleep(0.2)
        return False

    # ---- modes -----------------------------------------------------
    def run_check(self) -> int:
        logger.info("CHECK MODE: printing pose%s for ~10 s, never arms",
                    " + arm/offboard status" if self.flight else "")
        got_fix = False
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not self._stop:
            n, e, down, yaw, valid = self.pose.get_pose()
            got_fix = got_fix or valid
            extra = ""
            if self.flight is not None:
                extra = f" | armed={self.flight.armed} offboard={self.flight.in_offboard}"
            logger.info("pose n=%.3f e=%.3f down=%.3f yaw=%.1f valid=%s%s",
                        n, e, down, yaw, valid, extra)
            time.sleep(1.0)
        if not got_fix:
            logger.error("CHECK: never got a valid pose. For --pose px4 this is usually a "
                         "px4_msgs<->firmware version mismatch (Fast CDR exception). For "
                         "--pose uwb, run start_uwb.sh and confirm `ros2 topic echo /uwb_tag`.")
            return 2
        return 0

    def run_nofly(self) -> int:
        logger.info("NO-FLY MODE: real pose + scan/detect/map/artifacts, never arms/moves")
        self.state = "NOFLY_SCAN"
        self.started_at = time.monotonic()
        if not self._await_pose(POSE_WAIT_S):
            logger.warning("no pose fix yet — continuing; world coords may be invalid")
        deadline = time.monotonic() + float(self.args.max_flight_time_s)
        while time.monotonic() < deadline and not self._stop:
            self._scan_once()
            self._write_status()
            time.sleep(0.2)
        self.state = "DONE"
        return 0

    def run_fly(self, waypoints) -> int:
        if self.flight is None:
            logger.error("--fly requires --pose px4 (PX4 offboard control). Aborting.")
            return 2
        logger.info("FLY MODE: autonomous offboard survey of %d waypoints", len(waypoints))
        self.started_at = time.monotonic()
        self.state = "AWAIT_POSE"
        if not self._await_pose(POSE_WAIT_S):
            logger.error("no valid PX4 position estimate — refusing to fly")
            return 2
        n0, e0, down0, yaw0, _ = self.pose.get_pose()
        self.flight.set_target(n0, e0, self.args.takeoff_alt, yaw0)
        self.flight.begin_streaming()
        self.state = "OFFBOARD_PREWARM"
        time.sleep(1.0)
        self.state = "ARMING"
        self.flight.engage_offboard()
        self.flight.arm()
        t = time.monotonic() + ARM_OFFBOARD_WAIT_S
        while time.monotonic() < t:
            if self.flight.armed and self.flight.in_offboard:
                break
            time.sleep(0.2)
        if not (self.flight.armed and self.flight.in_offboard):
            logger.error("did not reach armed+offboard (armed=%s offboard=%s) — landing",
                         self.flight.armed, self.flight.in_offboard)
            return self._land_and_disarm(aborted=True)
        self.state = "TAKEOFF"
        if not self._fly_to(n0, e0, self.args.takeoff_alt, yaw0):
            return self._land_and_disarm(aborted=True)
        deadline = self.started_at + float(self.args.max_flight_time_s)
        for idx, (wn, we, walt) in enumerate(waypoints):
            if self._stop or time.monotonic() > deadline:
                logger.warning("stop/time-limit before waypoint %d", idx + 1)
                break
            self.state = f"FLY_WP_{idx + 1}"
            logger.info("WAYPOINT %d/%d -> (%.2f, %.2f, %.2f)", idx + 1, len(waypoints), wn, we, walt)
            if not self._fly_to(wn, we, walt, yaw0):
                logger.warning("waypoint %d not reached (timeout) — scanning anyway", idx + 1)
            self.state = f"SCAN_WP_{idx + 1}"
            self._scan_once()
            self._write_status()
        return self._land_and_disarm(aborted=self._stop)

    def _fly_to(self, n, e, alt, yaw_deg) -> bool:
        self.flight.set_target(n, e, alt, yaw_deg)
        deadline = time.monotonic() + FLY_TO_TIMEOUT_S
        while time.monotonic() < deadline and not self._stop:
            cn, ce, cdown, _, _ = self.pose.get_pose()
            if (abs(n - cn) < REACH_XY_M and abs(e - ce) < REACH_XY_M
                    and abs(alt - (-cdown)) < REACH_Z_M):
                time.sleep(0.5)
                return True
            self._write_status()
            time.sleep(0.2)
        return False

    def _land_and_disarm(self, *, aborted: bool) -> int:
        self.state = "LANDING"
        logger.info("landing + disarming")
        try:
            self.flight.land()
        except Exception as exc:
            logger.error("land failed: %s", exc)
        for _ in range(40):
            if not self.flight.armed:
                break
            time.sleep(0.5)
        try:
            self.flight.disarm()
        except Exception:
            pass
        self.state = "ABORTED" if aborted else "DONE"
        return 1 if aborted else 0

    def request_stop(self) -> None:
        self._stop = True


def _load_waypoints(args) -> list[tuple[float, float, float]]:
    path = args.waypoints or args.waypoints_from_json
    if not path:
        return list(DEFAULT_WAYPOINTS)
    data = json.loads(Path(path).read_text())
    out = [(float(r[0]), float(r[1]), float(r[2])) for r in data]
    if not out:
        raise ValueError(f"{path}: waypoints list is empty")
    return out


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PX4-ROS2 mapping mission (MAVSDK-free)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="connect + print pose/status, no arm")
    mode.add_argument("--nofly", action="store_true", help="pose+scan+artifacts, no arm (default)")
    mode.add_argument("--fly", action="store_true", help="autonomous offboard survey (needs --pose px4)")
    p.add_argument("--pose", choices=["px4", "uwb"], default="px4",
                   help="pose source: px4 (/fmu local position) or uwb (/uwb_tag). "
                        "Use uwb if px4 messages won't decode (px4_msgs version mismatch).")
    p.add_argument("--assumed-alt", type=float, default=1.0,
                   help="fallback camera height (m) for --pose uwb, used ONLY if /uwb_tag "
                        "carries no z (nlink normally publishes ENU z-up altitude, which is used)")
    p.add_argument("--aruco-dict", default="6X6_250")
    p.add_argument("--waypoints", default=None)
    p.add_argument("--waypoints-from-json", default=None)
    p.add_argument("--gimbal-pitch", type=float, default=-90.0)
    p.add_argument("--takeoff-alt", type=float, default=TAKEOFF_ALT_DEFAULT)
    p.add_argument("--max-flight-time-s", type=int, default=420)
    p.add_argument("--runs-dir", default="mapping_drone/runs")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args(argv)
    if not (args.check or args.nofly or args.fly):
        args.nofly = True
    if args.fly:
        args.pose = "px4"  # autonomous flight must use the FC's own position estimate
    return args


def main() -> int:
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(args.runs_dir).resolve() / f"run_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("run dir: %s", run_dir)
    logger.info("pose=%s | ArUco dict: %s | validity: %s", args.pose, args.aruco_dict, describe_rule())

    # Build flight (PX4 control) only when needed: --fly always, or --pose px4.
    flight = None
    if args.fly or args.pose == "px4":
        from .px4_ros import Px4Ros2Flight, px4_available
        if not px4_available():
            logger.error("px4_msgs/rclpy not importable. source ~/ros2_ws/install/setup.bash")
            return 2
        flight = Px4Ros2Flight()

    if args.pose == "px4":
        pose_source = flight
    else:
        pose_source = UwbPoseSource(args.assumed_alt)

    realsense = RealsenseNode()
    run_writer = RunWriter(run_dir, run_ts)

    mission: Optional[Px4Mission] = None
    aborted = False
    try:
        if flight is not None:
            flight.start()
        if pose_source is not flight:
            pose_source.start()
        realsense.start()
        mission = Px4Mission(args, pose_source, flight, realsense, run_writer)

        def _on_sig(*_a):
            logger.warning("signal received — stopping")
            if mission is not None:
                mission.request_stop()
        for s in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(s, _on_sig)
            except Exception:
                pass

        if args.check:
            return mission.run_check()
        if args.fly:
            code = mission.run_fly(_load_waypoints(args))
            aborted = code != 0
            return code
        code = mission.run_nofly()
        aborted = code != 0
        return code
    except Exception:
        logger.exception("mission crashed")
        aborted = True
        if args.fly and mission is not None and mission.flight is not None:
            try:
                mission._land_and_disarm(aborted=True)
            except Exception:
                pass
        return 1
    finally:
        total_s = (time.monotonic() - mission.started_at) if (mission and mission.started_at) else 0.0
        try:
            run_writer.finalise(mission.grid if mission else OccupancyGrid(resolution_m=0.05, size_m=20.0),
                                total_s, aborted, abort_reason="px4_mission" if aborted else None)
        except Exception as exc:
            logger.error("finalise failed: %s", exc)
        for closer in (realsense.stop, (pose_source.stop if pose_source is not flight else (lambda: None)),
                       (flight.stop if flight is not None else (lambda: None))):
            try:
                closer()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
