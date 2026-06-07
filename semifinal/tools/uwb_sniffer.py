"""Day-1 morning sanity-check sniffer for the 'uwb_tag' ROS2 topic.

Run on the companion/ground machine BEFORE arming the drone to confirm
the UWB ground anchors are publishing PoseStamped at a sane rate and
that the ENU -> NED axis swap (n=pose.y, e=pose.x, alt=-pose.z) lines
up with the physical layout we expect. Standalone — no controller, no
MAVSDK, no realsense. Prints one line per message; Ctrl-C to stop.

Usage:
    python tools/uwb_sniffer.py
    python tools/uwb_sniffer.py --topic /custom_uwb_topic
"""
from __future__ import annotations
import argparse, time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topic", default="uwb_tag", help="ROS2 topic (default: uwb_tag)")
    args = ap.parse_args()
    rclpy.init()
    node = Node("uwb_sniffer")

    def _cb(msg: PoseStamped) -> None:
        p = msg.pose.position
        print(f"[{time.monotonic():.3f}] raw x={p.x:+.3f} y={p.y:+.3f} z={p.z:+.3f}"
              f" -> NED n={p.y:+.3f} e={p.x:+.3f} alt={-p.z:+.3f}")

    node.create_subscription(PoseStamped, args.topic, _cb, 10)
    node.get_logger().info(f"sniffing '{args.topic}' — Ctrl-C to stop")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
