"""Bridge telemetry and bounded velocity commands through an SSH stream."""

import fcntl
import json
import math
import sys
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


MAX_LINEAR = 0.20
MAX_ANGULAR = 1.0
TIMEOUT = 0.25
COMMAND_TOPIC = "/cmd_vel_robot_steering"
CONTROLLER_TOPIC = "/diffbot_base_controller/cmd_vel_unstamped"


def read_commands(command, lock, closed):
    for line in sys.stdin:
        try:
            gate, linear, angular = map(float, line.split())
        except ValueError:
            gate, linear, angular = 0.0, 0.0, 0.0
        now = time.monotonic()
        if not (0 <= now - gate <= 0.55 and abs(linear) <= MAX_LINEAR and abs(angular) <= MAX_ANGULAR):
            linear = angular = 0.0
        with lock:
            command[:] = (now, linear, angular)
    closed.set()


def scan_payload(msg):
    if not math.isfinite(msg.angle_min) or not math.isfinite(msg.angle_increment):
        return None
    ranges = [
        round(distance, 3) if math.isfinite(distance) and msg.range_min <= distance <= msg.range_max
        else None
        for distance in msg.ranges
    ]
    return {
        "frame": msg.header.frame_id,
        "angle_min": msg.angle_min,
        "angle_increment": msg.angle_increment,
        "ranges": ranges,
    }


def run():
    rclpy.init()
    node = rclpy.create_node("lab03_laptop_teleop")
    publisher = node.create_publisher(Twist, COMMAND_TOPIC, 1)
    latest_odom = {}
    latest_scan = None
    drive_ready = False
    moving = False
    command = [0.0, 0.0, 0.0]
    lock = threading.Lock()
    closed = threading.Event()

    def odometry(source, msg):
        position = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y ** 2 + q.z ** 2))
        twist = msg.twist.twist
        pose = (position.x, position.y, yaw, twist.linear.x, twist.angular.z)
        latest_odom[source] = (time.monotonic(), pose if all(map(math.isfinite, pose)) else None)

    def scan(msg):
        nonlocal latest_scan
        latest_scan = time.monotonic(), scan_payload(msg)

    def publish(linear, angular):
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        publisher.publish(msg)

    def control():
        nonlocal moving
        with lock:
            stamp, linear, angular = command
        if not drive_ready or closed.is_set() or time.monotonic() - stamp > TIMEOUT:
            linear = angular = 0.0
        active = bool(linear or angular)
        if active or moving:
            publish(linear, angular)
        moving = active

    def telemetry():
        nonlocal drive_ready
        now = time.monotonic()
        poses = {
            source: pose for source, (stamp, pose) in latest_odom.items() if now - stamp < 0.75
        }
        pose = poses.get("wheel")
        cloud = latest_scan[1] if latest_scan and now - latest_scan[0] < 0.75 else None
        drive_ready = bool(pose and publisher.get_subscription_count() and any(
            endpoint.node_name == "diffbot_base_controller"
            for endpoint in node.get_subscriptions_info_by_topic(CONTROLLER_TOPIC)
        ))
        print(json.dumps({
            "gate": now,
            "ready": drive_ready,
            "odom": pose,
            "lidar_odom": poses.get("lidar"),
            "ekf_odom": poses.get("fusion"),
            "scan": cloud,
        }, allow_nan=False, separators=(",", ":")), flush=True)

    node.create_subscription(
        Odometry, "/diffbot_base_controller/odom", lambda msg: odometry("wheel", msg),
        qos_profile_sensor_data,
    )
    node.create_subscription(
        Odometry, "/odom_rf2o", lambda msg: odometry("lidar", msg), qos_profile_sensor_data,
    )
    node.create_subscription(
        Odometry, "/odometry/filtered", lambda msg: odometry("fusion", msg), qos_profile_sensor_data,
    )
    node.create_subscription(LaserScan, "/scan", scan, qos_profile_sensor_data)
    node.create_timer(0.05, control)
    node.create_timer(0.20, telemetry)
    threading.Thread(target=read_commands, args=(command, lock, closed), daemon=True).start()
    try:
        while rclpy.ok() and not closed.is_set():
            rclpy.spin_once(node, timeout_sec=0.10)
    finally:
        if moving and rclpy.ok():
            publish(0.0, 0.0)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    # Share the legacy WASD lock within the same container.
    with open("/tmp/jetbot-wasd.lock", "a", encoding="utf-8") as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another teleop session is already running.")
        run()
