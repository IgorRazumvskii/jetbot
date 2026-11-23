#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped

class OdometryToTF(Node):
    def __init__(self):
        super().__init__('odometry_to_tf')
        
        # Create transform broadcaster
        self.tf_broadcaster = TransformBroadcaster(self)
        
        # Subscribe to odometry topic
        self.odom_sub = self.create_subscription(
            Odometry,
            '/model/jetbot/odometry',
            self.odom_callback,
            10)
        
        self.get_logger().info('Odometry to TF node started')

    def odom_callback(self, msg):
        transform = TransformStamped()
        
        # Copy header information
        transform.header.stamp = msg.header.stamp
        transform.header.frame_id = msg.header.frame_id  # Usually 'odom'
        transform.child_frame_id = msg.child_frame_id    # Usually 'base_link'
        
        # Copy position
        transform.transform.translation.x = msg.pose.pose.position.x
        transform.transform.translation.y = msg.pose.pose.position.y
        transform.transform.translation.z = msg.pose.pose.position.z
        
        # Copy orientation
        transform.transform.rotation = msg.pose.pose.orientation
        
        # Broadcast the transform
        self.tf_broadcaster.sendTransform(transform)

def main():
    rclpy.init()
    node = OdometryToTF()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()