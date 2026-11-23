"""Restore the wheel TF and expose SLAM's corrected keyframes as a ROS Path."""

import rclpy
from geometry_msgs.msg import PoseStamped, TransformStamped
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from tf2_ros import TransformBroadcaster
from visualization_msgs.msg import Marker, MarkerArray


class ReplayBridge(Node):
    def __init__(self):
        super().__init__("scout_replay_bridge")
        self.tf = TransformBroadcaster(self)
        self.path_pub = self.create_publisher(
            Path, "/slam_path", QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        )
        self.create_subscription(Odometry, "/odom", self.broadcast_odom, qos_profile_sensor_data)
        self.create_subscription(
            MarkerArray, "/slam_toolbox/graph_visualization", self.publish_path, 1
        )

    def broadcast_odom(self, msg):
        if (msg.header.frame_id, msg.child_frame_id) != ("odom", "base_footprint"):
            self.get_logger().warning("Expected odom → base_footprint", once=True)
            return
        transform = TransformStamped(header=msg.header, child_frame_id=msg.child_frame_id)
        position = msg.pose.pose.position
        transform.transform.translation.x = position.x
        transform.transform.translation.y = position.y
        transform.transform.translation.z = position.z
        transform.transform.rotation = msg.pose.pose.orientation
        self.tf.sendTransform(transform)

    def publish_path(self, msg):
        markers = sorted(
            (m for m in msg.markers
             if m.action == Marker.ADD and m.ns == "slam_toolbox" and m.header.frame_id == "map"),
            key=lambda marker: marker.id,
        )
        if markers:
            path = Path(header=markers[-1].header)
            # The graph contains corrected positions. Its marker rotations have no heading.
            for marker in markers:
                point = PoseStamped(header=marker.header)
                point.pose.position = marker.pose.position
                point.pose.orientation.w = 1.0
                path.poses.append(point)
            self.path_pub.publish(path)


def main():
    rclpy.init()
    node = ReplayBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
