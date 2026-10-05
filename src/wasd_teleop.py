import select
import sys
import termios
import time
import tty

import rclpy
from geometry_msgs.msg import Twist

rclpy.init()
node = rclpy.create_node('wasd_teleop')
pub = node.create_publisher(Twist, '/cmd_vel', 10)
settings = termios.tcgetattr(sys.stdin)
linear = angular = 0.0
last_key = 0.0

print('W/S — вперёд/назад, A/D — поворот, пробел — стоп, Q — выход.')
print('Удерживайте клавишу для движения. Раскладка — английская.', flush=True)

try:
    tty.setraw(sys.stdin.fileno())
    while rclpy.ok():
        if select.select([sys.stdin], [], [], 0.05)[0]:
            key = sys.stdin.read(1).lower()
            if key in ('q', '\x03'):
                break
            linear, angular = {
                'w': (0.5, 0.0),
                's': (-0.5, 0.0),
                'a': (0.0, 3.0),
                'd': (0.0, -3.0),
            }.get(key, (0.0, 0.0))
            last_key = time.monotonic()

        if time.monotonic() - last_key > 0.3:
            linear = angular = 0.0

        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        pub.publish(msg)
finally:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    for _ in range(3):
        pub.publish(Twist())
        time.sleep(0.05)
    node.destroy_node()
    rclpy.shutdown()
    print('\nУправление завершено.')
