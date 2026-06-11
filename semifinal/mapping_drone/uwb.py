"""UWB position adapters for the mapping drone.

Provides a real ROS2 subscriber (UwbNode) and a programmable mock
(MockUwbNode) behind a common Protocol so the controller can be tested
on a laptop without rclpy installed.

Coordinate convention: the ROS2 'uwb_tag' topic publishes PoseStamped in
ENU (x=east, y=north, z=up). MAVSDK/controller callers in this repo work
in NED-style (north, east), so we swap axes here: n = pose.position.y,
e = pose.position.x. See mapping_drone/README.md "Coordinate-frame
callout" section for the full PX4 NED vs world ENU rationale.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol

logger = logging.getLogger(__name__)

UWB_TOPIC = "uwb_tag"

try:
    import rclpy
    from rclpy.node import Node as _RclpyNode
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from geometry_msgs.msg import PoseStamped
    _ROS2_AVAILABLE = True
    _ROS2_IMPORT_ERROR: Exception | None = None
except Exception as _exc:
    rclpy = None  # type: ignore[assignment]
    _RclpyNode = object  # type: ignore[assignment,misc]
    QoSProfile = None  # type: ignore[assignment]
    ReliabilityPolicy = None  # type: ignore[assignment]
    HistoryPolicy = None  # type: ignore[assignment]
    PoseStamped = None  # type: ignore[assignment]
    _ROS2_AVAILABLE = False
    _ROS2_IMPORT_ERROR = _exc


class UwbAdapter(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def get_position(self) -> tuple[float, float, bool]:
        """Returns (n_m, e_m, ready). ready=False means no fix yet."""
        ...

    @property
    def last_update_ts(self) -> float:
        """Monotonic timestamp of last UWB packet. 0.0 if never."""
        ...


class UwbNode:
    """Real ROS2 subscriber to the 'uwb_tag' PoseStamped topic.

    Spins rclpy in a daemon thread so the controller's asyncio loop is
    free. Topic publishes ENU; we expose NED-style (north, east).
    """

    def __init__(self, topic: str = UWB_TOPIC) -> None:
        self._topic = topic
        self._lock = threading.Lock()
        self._n: float = 0.0
        self._e: float = 0.0
        self._z: float = 0.0
        self._have_z: bool = False
        self._ready: bool = False
        self._last_update_ts: float = 0.0
        self._node: object | None = None
        self._executor_thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._owns_rclpy_init: bool = False
        self._started: bool = False

    def start(self) -> None:
        if self._started:
            return
        if not _ROS2_AVAILABLE:
            raise RuntimeError(
                "ROS2 (rclpy / geometry_msgs) is not importable on this "
                "machine; cannot start real UwbNode. Use MockUwbNode for "
                f"laptop testing. Underlying import error: {_ROS2_IMPORT_ERROR!r}"
            )

        if not rclpy.ok():
            rclpy.init()
            self._owns_rclpy_init = True

        try:
            node = _RclpyNode("mapping_drone_uwb_subscriber")
            qos = QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
                depth=10,
            )
            node.create_subscription(PoseStamped, self._topic, self._on_pose, qos)
        except Exception:
            # Don't leak the rclpy context we just initialised on a failed start.
            if self._owns_rclpy_init and rclpy.ok():
                try:
                    rclpy.shutdown()
                except Exception:
                    pass
                self._owns_rclpy_init = False
            raise
        self._node = node

        def _spin() -> None:
            try:
                while not self._stop_flag.is_set() and rclpy.ok():
                    rclpy.spin_once(node, timeout_sec=0.1)
            except Exception:
                logger.exception("UWB ROS2 spin thread crashed")

        self._executor_thread = threading.Thread(
            target=_spin, name="uwb-rclpy-spin", daemon=True
        )
        self._executor_thread.start()
        self._started = True
        logger.info("UwbNode started, subscribed to '%s'", self._topic)

    def _on_pose(self, msg: object) -> None:
        # ENU (ROS2) -> NED-style axis swap: n = pose.position.y, e = pose.position.x
        try:
            pose = msg.pose  # type: ignore[attr-defined]
            n = float(pose.position.y)
            e = float(pose.position.x)
            z_up = float(pose.position.z)  # nlink /uwb_tag carries altitude as ENU z-up
        except Exception:
            logger.exception("Malformed PoseStamped on '%s'", self._topic)
            return

        with self._lock:
            self._n = n
            self._e = e
            self._z = z_up
            # Per-packet, NOT latched: a single early spurious z must not
            # permanently poison get_altitude(). (UWB is really N-E only.)
            self._have_z = abs(z_up) > 1e-6
            self._ready = True
            self._last_update_ts = time.monotonic()

    def stop(self) -> None:
        if not self._started:
            return
        self._stop_flag.set()
        if self._executor_thread is not None:
            self._executor_thread.join(timeout=2.0)
            self._executor_thread = None
        if self._node is not None:
            try:
                self._node.destroy_node()  # type: ignore[attr-defined]
            except Exception:
                logger.exception("Error destroying UWB ROS2 node")
            self._node = None
        if self._owns_rclpy_init and rclpy is not None and rclpy.ok():
            try:
                rclpy.shutdown()
            except Exception:
                logger.exception("Error shutting down rclpy")
            self._owns_rclpy_init = False
        self._started = False
        logger.info("UwbNode stopped")

    def get_position(self) -> tuple[float, float, bool]:
        with self._lock:
            return self._n, self._e, self._ready

    def get_altitude(self) -> float | None:
        """ENU z-up altitude from /uwb_tag if present AND fresh, else None.
        NOTE: the UWB tag is N-E only (org slides) — prefer FC altitude; this
        is a best-effort fallback only."""
        with self._lock:
            if not self._have_z or self._last_update_ts == 0.0:
                return None
            if time.monotonic() - self._last_update_ts > 1.0:
                return None
            return self._z

    @property
    def last_update_ts(self) -> float:
        with self._lock:
            return self._last_update_ts


class MockUwbNode:
    """Programmable in-process UWB source for laptop/CI testing.

    Default position is (0.0, 0.0) with ready=False; ready flips to True
    only after the first set_position() call. start()/stop() merely toggle
    an internal _started lifecycle flag for parity with the real UwbNode
    and do not affect readiness.
    """

    def __init__(self, initial_n: float = 0.0, initial_e: float = 0.0) -> None:
        self._lock = threading.Lock()
        self._n: float = float(initial_n)
        self._e: float = float(initial_e)
        self._ready: bool = False
        self._last_update_ts: float = 0.0
        self._started: bool = False

    def start(self) -> None:
        self._started = True
        logger.info(
            "MockUwbNode started at n=%.3f e=%.3f (ready=%s)",
            self._n, self._e, self._ready,
        )

    def stop(self) -> None:
        self._started = False
        logger.info("MockUwbNode stopped")

    def set_position(self, n: float, e: float) -> None:
        with self._lock:
            self._n = float(n)
            self._e = float(e)
            self._ready = True
            self._last_update_ts = time.monotonic()

    def get_position(self) -> tuple[float, float, bool]:
        with self._lock:
            return self._n, self._e, self._ready

    @property
    def last_update_ts(self) -> float:
        with self._lock:
            return self._last_update_ts
