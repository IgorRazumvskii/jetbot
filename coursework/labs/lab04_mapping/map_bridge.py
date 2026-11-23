"""Read occupancy, keyframes, and the robot pose from JetBot's ROS domain."""

import base64
import json
import math
import sys
import threading

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray


def yaw(quaternion):
    x, y, z, w = quaternion.x, quaternion.y, quaternion.z, quaternion.w
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


class MapBridge(Node):
    def __init__(self):
        super().__init__("lab04_laptop_map")
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.map_key = None
        self.map_revision = 0
        self.pending_map = None
        self.pending_graph = None
        self.create_subscription(
            OccupancyGrid, "/map", self.grid,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                       durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.create_subscription(MarkerArray, "/slam_toolbox/graph_visualization", self.graph, 1)
        self.create_timer(0.25, self.send)

    def grid(self, msg):
        info = msg.info
        if msg.header.frame_id != "map" or not info.width or not info.height:
            return
        cells = bytes(msg.data)
        origin = (info.origin.position.x, info.origin.position.y, yaw(info.origin.orientation))
        if len(cells) != info.width * info.height or not info.resolution > 0.0:
            return
        key = (info.width, info.height, info.resolution, origin, cells)
        if self.map_key == key:
            return
        self.map_key = key
        self.map_revision += 1
        self.pending_map = {
            "revision": self.map_revision,
            "width": info.width,
            "height": info.height,
            "resolution": info.resolution,
            "origin": origin,
            "cells": base64.b64encode(cells).decode("ascii"),
        }

    def graph(self, msg):
        nodes = []
        edges = []
        for marker in msg.markers:
            if marker.header.frame_id != "map" or marker.action != Marker.ADD:
                continue
            if marker.ns == "slam_toolbox_edges" and marker.type == Marker.LINE_LIST:
                edges.extend((round(p.x, 3), round(p.y, 3)) for p in marker.points)
            elif marker.ns == "slam_toolbox":
                position = marker.pose.position
                nodes.append((round(position.x, 3), round(position.y, 3)))
        self.pending_graph = {"nodes": nodes, "edges": edges}

    def pose(self):
        try:
            transform = self.buffer.lookup_transform("map", "base_footprint", Time())
        except TransformException:
            return None
        stamp = Time.from_msg(transform.header.stamp)
        if (self.get_clock().now() - stamp).nanoseconds > 1_500_000_000:
            return None
        position = transform.transform.translation
        return (position.x, position.y, yaw(transform.transform.rotation))

    def send(self):
        packet = {"pose": self.pose() if self.map_key is not None else None}
        if self.pending_map is not None:
            packet["map"] = self.pending_map
            self.pending_map = None
        if self.pending_graph is not None:
            packet["graph"] = self.pending_graph
            self.pending_graph = None
        print(json.dumps(packet, allow_nan=False, separators=(",", ":")), flush=True)


def main():
    rclpy.init()
    node = MapBridge()
    closed = threading.Event()

    def wait_for_close():
        sys.stdin.buffer.read(1)
        closed.set()

    threading.Thread(target=wait_for_close, daemon=True).start()
    try:
        while rclpy.ok() and not closed.is_set():
            rclpy.spin_once(node, timeout_sec=0.2)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
