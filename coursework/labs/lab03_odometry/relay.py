"""Relay JetBot transforms and wheel odometry over an SSH stream."""

import argparse
import base64
import sys
from functools import partial

import rclpy
from nav_msgs.msg import Odometry
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.serialization import deserialize_message, serialize_message
from tf2_msgs.msg import TFMessage


TOPICS = {
    "/tf": TFMessage,
    "/tf_static": TFMessage,
    "/diffbot_base_controller/odom": Odometry,
}


def topic_qos(topic, *, sender):
    if topic == "/tf_static":
        return QoSProfile(depth=100, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    reliability = ReliabilityPolicy.BEST_EFFORT if sender else ReliabilityPolicy.RELIABLE
    return QoSProfile(depth=25, reliability=reliability)


def write_message(topic, message):
    payload = base64.b64encode(serialize_message(message))
    sys.stdout.buffer.write(b"lab03\t" + topic.encode() + b"\t" + payload + b"\n")
    sys.stdout.buffer.flush()


def send(node):
    for topic, kind in TOPICS.items():
        node.create_subscription(
            kind, topic, partial(write_message, topic), topic_qos(topic, sender=True)
        )
    rclpy.spin(node)


def receive(node):
    publishers = {
        topic: node.create_publisher(kind, topic, topic_qos(topic, sender=False))
        for topic, kind in TOPICS.items()
    }
    for line in sys.stdin.buffer:
        if not line.startswith(b"lab03\t"):
            continue
        _, key, payload = line.rstrip(b"\n").split(b"\t", maxsplit=2)
        topic = key.decode()
        message = deserialize_message(base64.b64decode(payload, validate=True), TOPICS[topic])
        publishers[topic].publish(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("send", "receive"))
    mode = parser.parse_args().mode
    rclpy.init(args=[])
    node = rclpy.create_node(f"lab03_relay_{mode}")
    try:
        if mode == "send":
            send(node)
        else:
            receive(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
