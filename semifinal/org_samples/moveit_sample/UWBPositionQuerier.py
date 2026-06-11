import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import PoseStamped
import threading
from typing import Optional
from copy import deepcopy


class UWBPositionQuerier:
    """
    Standalone class to query UWB tag positions from a ROS2 topic.
    Does not inherit from rclpy.Node. Manages an internal node and executor
    to handle ROS2 subscriptions in a background thread.
    """

    def __init__(self, topic_name: str = 'uwb_tag', qos: Optional[QoSProfile] = None):
        # Initialize rclpy if not already done by the host application
        if not rclpy.ok():
            rclpy.init()

        self._node = rclpy.create_node('uwb_position_querier_internal')
        
        # Default QoS tuned for typical UWB streams (best-effort, volatile)
        self._qos = qos or QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE
        )

        self._subscription = self._node.create_subscription(
            PoseStamped,
            topic_name,
            self._uwb_callback,
            self._qos
        )

        self._latest_pose: Optional[PoseStamped] = None
        self._lock = threading.Lock()
        
        # Run ROS2 callbacks in a dedicated background thread
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

    def _uwb_callback(self, msg: PoseStamped) -> None:
        """Thread-safe callback that stores the latest UWB pose."""
        with self._lock:
            # Deepcopy ensures thread safety if the caller modifies the returned object
            self._latest_pose = deepcopy(msg)

    def get_latest_pose(self) -> Optional[PoseStamped]:
        """
        Returns the most recently received UWB pose.
        Returns None if no message has been received yet.
        """
        with self._lock:
            return self._latest_pose

    def shutdown(self) -> None:
        """Gracefully stops the internal executor and destroys the internal node."""
        if self._executor:
            self._executor.shutdown()
        if self._spin_thread.is_alive():
            self._spin_thread.join(timeout=2.0)
        if self._node:
            self._node.destroy_node()
        # Note: rclpy.shutdown() is intentionally NOT called here to avoid 
        # interfering with other ROS2 nodes in the same process.

    def __enter__(self) -> 'UWBPositionQuerier':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.shutdown()
        return False

    def __del__(self) -> None:
        self.shutdown()


# Example standalone usage
if __name__ == '__main__':
    try:
        # Using context manager for automatic cleanup
        with UWBPositionQuerier(topic_name='uwb_tag') as querier:
            import time
            
            # Poll for position
            while True:
                pose = querier.get_latest_pose()
                if pose:
                    x = pose.pose.position.x
                    y = pose.pose.position.y
                    z = pose.pose.position.z
                    print(f"UWB Position -> x: {x:.3f}, y: {y:.3f}, z: {z:.3f}")
                else:
                    print("Waiting for UWB data...")
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        # IMPORTANT: Call rclpy.shutdown() once at the very end of your application
        if rclpy.ok():
            rclpy.shutdown()