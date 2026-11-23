"""Supply RF2O pose covariance for the lab's relative planar EKF."""

import math

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data


class Rf2oEkfInput(Node):
    def __init__(self):
        super().__init__("lab03_rf2o_ekf_input")
        self.output = self.create_publisher(Odometry, "/lab03/rf2o_for_ekf", 10)
        self.create_subscription(Odometry, "/odom_rf2o", self.forward, qos_profile_sensor_data)

    def forward(self, msg):
        if msg.header.frame_id != "lidar_odom" or msg.child_frame_id != "base_footprint":
            self.get_logger().warning("Unexpected RF2O frames", throttle_duration_sec=5.0)
            return

        pose = msg.pose.pose
        q = pose.orientation
        if not all(map(math.isfinite, (pose.position.x, pose.position.y, q.x, q.y, q.z, q.w))):
            return
        if not math.isclose(math.hypot(q.x, q.y, q.z, q.w), 1.0, abs_tol=1e-3):
            return

        # The filter uses this private input in relative mode, applying the
        # inverse of the first RF2O pose before fusion in its own odom frame.
        msg.header.frame_id = "ekf_odom"
        covariance = [0.0] * 36
        # Stock RF2O reports zero covariance. Start with 5 cm and 5 degree std dev.
        covariance[0] = covariance[7] = 0.05 ** 2
        covariance[35] = math.radians(5) ** 2
        msg.pose.covariance = covariance
        self.output.publish(msg)


def main():
    rclpy.init()
    node = Rf2oEkfInput()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
