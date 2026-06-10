"""PX4-ROS2 (micro-XRCE-DDS) flight + pose adapter for the mapping drone.

WHY THIS EXISTS
---------------
The finals mapping drone's flight controller speaks PX4 over micro-XRCE-DDS
(ROS2 ``px4_msgs`` topics on ``/fmu/in/*`` and ``/fmu/out/*``), **not MAVLink**.
MAVSDK therefore cannot connect to it (verified on the drone 2026-06-10: the
XRCE agent on ``/dev/ttyS1`` brings up the full ``/fmu/*`` topic set, while
MAVSDK finds no heartbeat on any serial port). This module is the MAVSDK
replacement: pose telemetry from ``/fmu/out/vehicle_local_position`` and
offboard position control via ``/fmu/in/{offboard_control_mode,
trajectory_setpoint,vehicle_command}``.

PREREQUISITES (on the drone)
----------------------------
- ``MicroXRCEAgent serial -D /dev/ttyS1 -b 921600`` running (``start_micro.sh``).
- ROS2 Humble + the ``px4_msgs`` package built and sourced (``ros2_ws``).
- Verify the message fields match this PX4 build once with, e.g.::

      ros2 interface show px4_msgs/msg/TrajectorySetpoint
      ros2 interface show px4_msgs/msg/VehicleLocalPosition

COORDINATE FRAME
----------------
PX4 ``VehicleLocalPosition`` and ``TrajectorySetpoint`` are NED: x=North,
y=East, z=Down (z negative when airborne). We expose pose as (n, e, down, yaw)
to match ``mapping.camera_to_world`` (which wants alt-up = -down) and the
existing waypoint format ``(n, e, alt_m)``.

SAFETY
------
- PX4 drops OFFBOARD if setpoints stop arriving — a 20 Hz timer streams the
  current setpoint continuously while ``_stream`` is set.
- We never arm until OFFBOARD is engaged AND setpoints have been streaming.
- ``land()`` + ``disarm()`` are exposed for the caller's finally/Ctrl-C path.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import (
        QoSProfile,
        ReliabilityPolicy,
        HistoryPolicy,
        DurabilityPolicy,
    )
    from px4_msgs.msg import (
        OffboardControlMode,
        TrajectorySetpoint,
        VehicleCommand,
        VehicleLocalPosition,
        VehicleStatus,
    )

    _PX4_AVAILABLE = True
    _IMPORT_ERROR: Optional[Exception] = None
except Exception as _exc:  # rclpy or px4_msgs missing (e.g. laptop dev)
    rclpy = None  # type: ignore[assignment]
    Node = object  # type: ignore[assignment,misc]
    _PX4_AVAILABLE = False
    _IMPORT_ERROR = _exc


# PX4 VehicleCommand command IDs (stable across recent PX4 / px4_msgs).
VEHICLE_CMD_DO_SET_MODE = 176
VEHICLE_CMD_COMPONENT_ARM_DISARM = 400
VEHICLE_CMD_NAV_LAND = 21

# PX4 main-mode index for OFFBOARD (param2 of DO_SET_MODE with param1=1).
PX4_CUSTOM_MAIN_MODE_OFFBOARD = 6
# VehicleStatus.arming_state value for "armed" and nav_state for "offboard".
ARMING_STATE_ARMED = 2
NAVIGATION_STATE_OFFBOARD = 14


def px4_available() -> bool:
    return _PX4_AVAILABLE


def _px4_sub_qos() -> "QoSProfile":
    # PX4 publishes /fmu/out/* BEST_EFFORT. Match it; VOLATILE + small history.
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=5,
    )


def _px4_pub_qos() -> "QoSProfile":
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
    )


class Px4Ros2Flight:
    """Pose + offboard-control adapter over PX4 micro-XRCE-DDS topics.

    Spins rclpy in a daemon thread (like ``uwb.UwbNode``) so a synchronous
    mission loop can call ``set_target`` / ``arm`` / ``land`` and poll
    ``get_pose``.
    """

    def __init__(
        self,
        *,
        node_name: str = "mapping_drone_px4",
        stream_hz: float = 20.0,
        target_system: int = 1,
    ) -> None:
        if not _PX4_AVAILABLE:
            raise RuntimeError(
                "px4_msgs / rclpy not importable — cannot use PX4-ROS2 flight. "
                f"Underlying import error: {_IMPORT_ERROR!r}. On the drone, "
                "`source ~/ros2_ws/install/setup.bash` first."
            )
        self._node_name = node_name
        self._stream_dt = 1.0 / float(stream_hz)
        self._target_system = int(target_system)

        self._lock = threading.Lock()
        # pose (NED): north, east, down (m), yaw (deg). valid flags.
        self._n = 0.0
        self._e = 0.0
        self._down = 0.0
        self._yaw_deg = 0.0
        self._pos_valid = False
        self._last_pos_ts = 0.0
        # status
        self._armed = False
        self._nav_state = -1
        # setpoint the timer streams: (n, e, alt_up_m, yaw_deg) or None=hold
        self._setpoint: Optional[tuple[float, float, float, float]] = None
        self._stream = False

        self._node: Optional[Node] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._timer = None
        self._stop = threading.Event()
        self._owns_rclpy = False
        self._started = False

    # ---- lifecycle -------------------------------------------------
    def start(self) -> None:
        if self._started:
            return
        if not rclpy.ok():
            rclpy.init()
            self._owns_rclpy = True
        node = rclpy.create_node(self._node_name)
        self._node = node

        pub_qos = _px4_pub_qos()
        sub_qos = _px4_sub_qos()
        self._pub_offboard = node.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", pub_qos
        )
        self._pub_setpoint = node.create_publisher(
            TrajectorySetpoint, "/fmu/in/trajectory_setpoint", pub_qos
        )
        self._pub_command = node.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", pub_qos
        )
        node.create_subscription(
            VehicleLocalPosition,
            "/fmu/out/vehicle_local_position",
            self._on_local_position,
            sub_qos,
        )
        node.create_subscription(
            VehicleStatus, "/fmu/out/vehicle_status", self._on_status, sub_qos
        )
        # Streamer timer runs inside the executor thread.
        self._timer = node.create_timer(self._stream_dt, self._stream_cb)

        def _spin() -> None:
            try:
                while not self._stop.is_set() and rclpy.ok():
                    rclpy.spin_once(node, timeout_sec=0.1)
            except Exception:
                logger.exception("PX4 ROS2 spin thread crashed")

        self._spin_thread = threading.Thread(
            target=_spin, name="px4-rclpy-spin", daemon=True
        )
        self._spin_thread.start()
        self._started = True
        logger.info("Px4Ros2Flight started (px4_msgs over micro-XRCE-DDS)")

    def stop(self) -> None:
        if not self._started:
            return
        self._stop.set()
        if self._spin_thread is not None:
            self._spin_thread.join(timeout=2.0)
            self._spin_thread = None
        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception:
                logger.exception("destroy_node failed")
            self._node = None
        if self._owns_rclpy and rclpy is not None and rclpy.ok():
            try:
                rclpy.shutdown()
            except Exception:
                logger.exception("rclpy.shutdown failed")
            self._owns_rclpy = False
        self._started = False
        logger.info("Px4Ros2Flight stopped")

    # ---- subscriptions ---------------------------------------------
    def _on_local_position(self, msg) -> None:
        try:
            n = float(msg.x)
            e = float(msg.y)
            down = float(msg.z)
            heading = float(getattr(msg, "heading", 0.0))
            xy_valid = bool(getattr(msg, "xy_valid", True))
            z_valid = bool(getattr(msg, "z_valid", True))
        except Exception:
            logger.exception("malformed VehicleLocalPosition")
            return
        with self._lock:
            self._n, self._e, self._down = n, e, down
            self._yaw_deg = math.degrees(heading)
            self._pos_valid = xy_valid and z_valid
            self._last_pos_ts = time.monotonic()

    def _on_status(self, msg) -> None:
        with self._lock:
            self._armed = int(getattr(msg, "arming_state", -1)) == ARMING_STATE_ARMED
            self._nav_state = int(getattr(msg, "nav_state", -1))

    # ---- streamer (executor thread) --------------------------------
    def _now_us(self) -> int:
        return int(self._node.get_clock().now().nanoseconds / 1000)

    def _stream_cb(self) -> None:
        if not self._stream:
            return
        # OffboardControlMode: position control only.
        ocm = OffboardControlMode()
        ocm.timestamp = self._now_us()
        ocm.position = True
        ocm.velocity = False
        ocm.acceleration = False
        ocm.attitude = False
        ocm.body_rate = False
        self._pub_offboard.publish(ocm)

        with self._lock:
            sp = self._setpoint
            cur = (self._n, self._e, self._down, self._yaw_deg)
        ts = TrajectorySetpoint()
        ts.timestamp = self._now_us()
        if sp is None:
            # hold current pose
            ts.position = [cur[0], cur[1], cur[2]]
            ts.yaw = math.radians(cur[3])
        else:
            n, e, alt_up, yaw_deg = sp
            ts.position = [float(n), float(e), float(-alt_up)]  # alt-up -> NED down
            ts.yaw = math.radians(float(yaw_deg))
        self._pub_setpoint.publish(ts)

    # ---- commands (callable from any thread) -----------------------
    def _send_command(self, command: int, **params) -> None:
        cmd = VehicleCommand()
        cmd.timestamp = self._now_us()
        cmd.command = int(command)
        cmd.param1 = float(params.get("param1", 0.0))
        cmd.param2 = float(params.get("param2", 0.0))
        cmd.param3 = float(params.get("param3", 0.0))
        cmd.param4 = float(params.get("param4", 0.0))
        cmd.param5 = float(params.get("param5", 0.0))
        cmd.param6 = float(params.get("param6", 0.0))
        cmd.param7 = float(params.get("param7", 0.0))
        cmd.target_system = self._target_system
        cmd.target_component = 1
        cmd.source_system = 1
        cmd.source_component = 1
        cmd.from_external = True
        self._pub_command.publish(cmd)

    def begin_streaming(self) -> None:
        """Start streaming setpoints (call BEFORE engage_offboard/arm)."""
        self._stream = True

    def set_target(self, n: float, e: float, alt_up_m: float, yaw_deg: float) -> None:
        with self._lock:
            self._setpoint = (float(n), float(e), float(alt_up_m), float(yaw_deg))

    def hold_here(self) -> None:
        with self._lock:
            self._setpoint = None  # timer streams current pose

    def engage_offboard(self) -> None:
        self._send_command(
            VEHICLE_CMD_DO_SET_MODE, param1=1.0, param2=float(PX4_CUSTOM_MAIN_MODE_OFFBOARD)
        )
        logger.info("PX4: requested OFFBOARD mode")

    def arm(self) -> None:
        self._send_command(VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=1.0)
        logger.info("PX4: arm command sent")

    def disarm(self) -> None:
        self._send_command(VEHICLE_CMD_COMPONENT_ARM_DISARM, param1=0.0)
        logger.info("PX4: disarm command sent")

    def land(self) -> None:
        self._send_command(VEHICLE_CMD_NAV_LAND)
        logger.info("PX4: LAND command sent")

    # ---- reads -----------------------------------------------------
    def get_pose(self) -> tuple[float, float, float, float, bool]:
        """Return (north_m, east_m, down_m, yaw_deg, valid)."""
        with self._lock:
            return self._n, self._e, self._down, self._yaw_deg, self._pos_valid

    @property
    def last_pos_ts(self) -> float:
        with self._lock:
            return self._last_pos_ts

    @property
    def armed(self) -> bool:
        with self._lock:
            return self._armed

    @property
    def in_offboard(self) -> bool:
        with self._lock:
            return self._nav_state == NAVIGATION_STATE_OFFBOARD
