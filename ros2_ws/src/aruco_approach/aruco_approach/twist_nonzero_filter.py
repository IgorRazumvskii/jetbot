"""Пропускает дальше только ненулевые команды скорости.

teleop_twist_keyboard публикует нулевой Twist (клавиша k и любые другие),
а twist_mux отдаёт приоритет входу при любом свежем сообщении — даже нулевом.
По заданию teleop главнее только при ненулевой команде, поэтому нули
отсекаются здесь, и при молчащем/нулевом teleop работает движение к цели.
"""
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node


class TwistNonzeroFilter(Node):

    def __init__(self):
        super().__init__('twist_nonzero_filter')
        self.epsilon = self.declare_parameter('epsilon', 1e-3).value
        self.pub = self.create_publisher(Twist, 'cmd_vel_out', 10)
        self.create_subscription(Twist, 'cmd_vel_in', self._on_twist, 10)

    def _on_twist(self, msg: Twist):
        values = (msg.linear.x, msg.linear.y, msg.linear.z,
                  msg.angular.x, msg.angular.y, msg.angular.z)
        if any(abs(v) > self.epsilon for v in values):
            self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TwistNonzeroFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
