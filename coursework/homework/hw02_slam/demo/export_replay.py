"""Build a seekable camera, lidar, and SLAM replay for one SQLite bag."""

import argparse
import base64
import gzip
import json
import math
from pathlib import Path
import signal
import sqlite3
import subprocess
import tempfile
import time

from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid, Path as RosPath
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rclpy.serialization import deserialize_message
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CompressedImage, PointCloud2
from sensor_msgs_py.point_cloud2 import read_points_numpy
import yaml

CAMERA = "/camera/color/image_raw/compressed"
LIDAR = "/rslidar_points"


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class Capture(Node):
    def __init__(self, start_ns):
        super().__init__("scout_replay_export")
        self.start_ns = start_ns
        self.elapsed = 0.0
        self.maps = []
        self.last_grid = None
        self.path = []
        self.pose = None
        self.timeline = []
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(Clock, "/clock", self.on_clock, qos_profile_sensor_data)
        self.create_subscription(OccupancyGrid, "/map", self.on_map, latched)
        self.create_subscription(RosPath, "/slam_path", self.on_path, latched)
        self.create_subscription(PoseWithCovarianceStamped, "/pose", self.on_pose, 1)
        self.create_timer(0.1, self.sample)

    def on_clock(self, msg):
        stamp = msg.clock.sec * 10**9 + msg.clock.nanosec
        self.elapsed = round(max(self.elapsed, (stamp - self.start_ns) / 1e9), 4)

    def on_map(self, msg):
        info = msg.info
        if msg.header.frame_id != "map" or not info.width or not info.height:
            return
        cells = bytes(msg.data)
        origin = info.origin.position.x, info.origin.position.y, yaw(info.origin.orientation)
        key = (info.width, info.height, info.resolution, origin, cells)
        if key != self.last_grid:
            self.last_grid = key
            self.maps.append({
                "revision": len(self.maps) + 1, "width": info.width, "height": info.height,
                "resolution": info.resolution, "origin": origin,
                "cells": base64.b64encode(cells).decode("ascii"),
            })
            self.sample()

    def on_path(self, msg):
        self.path = [(round(p.pose.position.x, 4), round(p.pose.position.y, 4))
                     for p in msg.poses]

    def on_pose(self, msg):
        pose = msg.pose.pose
        self.pose = round(pose.position.x, 4), round(pose.position.y, 4), round(yaw(pose.orientation), 5)

    def sample(self):
        state = {"t": self.elapsed, "map": len(self.maps) - 1, "path": self.path, "pose": self.pose}
        if self.timeline and self.timeline[-1]["t"] == state["t"]:
            self.timeline[-1] = state
        else:
            self.timeline.append(state)


def capture_slam(bag, start_ns, duration):
    rclpy.init()
    node = Capture(start_ns)
    command = [
        "ros2", "launch", "scout_bag_slam", "reconstruct.launch.py",
        f"bag:={bag}", "exit_on_finish:=true",
    ]
    try:
        with subprocess.Popen(command) as process:
            deadline = time.monotonic() + duration + 45
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("SLAM did not finish within the expected recording time")
                    rclpy.spin_once(node, timeout_sec=0.1)
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command)
        if not node.maps or len(node.path) < 2 or node.elapsed < duration - 0.6:
            raise ValueError("Playback ended without a complete SLAM timeline")
        node.elapsed = duration
        node.sample()
        return node.maps, node.timeline
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


def read_messages(bag, files, topic):
    for relative in files:
        source = (bag / relative).resolve()
        with sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as db:
            yield from db.execute(
                "SELECT messages.timestamp, messages.data FROM messages "
                "JOIN topics ON topics.id=messages.topic_id "
                "WHERE topics.name=? ORDER BY messages.timestamp", (topic,),
            )


def encode_video(bag, files, start_ns, duration, output):
    frames = iter(read_messages(bag, files, CAMERA))
    first = next(frames, None)
    if first is None:
        raise ValueError("No recorded camera frames")

    def frame_data(row):
        frame = bytes(deserialize_message(row[1], CompressedImage).data)
        if not frame.startswith(b"\xff\xd8"):
            raise ValueError("Camera stream must contain JPEG images")
        return frame

    jpeg = frame_data(first)
    upcoming = next(frames, None)
    fps = 30
    command = [
        "ffmpeg", "-v", "error", "-f", "image2pipe", "-framerate", str(fps),
        "-vcodec", "mjpeg", "-i", "pipe:0", "-an", "-c:v", "libx264",
        "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output),
    ]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        with process.stdin:
            for index in range(math.ceil(duration * fps)):
                stamp = start_ns + index * 10**9 // fps
                while upcoming and upcoming[0] <= stamp:
                    jpeg = frame_data(upcoming)
                    upcoming = next(frames, None)
                process.stdin.write(jpeg)
        if process.wait():
            raise subprocess.CalledProcessError(process.returncode, command)


def encode_clouds(bag, files, start_ns):
    clouds = []
    last_time = -1.0
    for stamp, raw in read_messages(bag, files, LIDAR):
        t = (stamp - start_ns) / 1e9
        if t - last_time < 0.18:
            continue
        cloud = deserialize_message(raw, PointCloud2)
        xyz = read_points_numpy(cloud, field_names=["x", "y", "z"])[::18]
        xyz = xyz[np.isfinite(xyz).all(axis=1)]
        ranges = np.linalg.norm(xyz, axis=1)
        xyz = xyz[(ranges > 0.6) & (ranges < 18.0)]
        # Two centimetres per integer step keeps the browser file compact.
        packed = np.rint(xyz * 50).astype("<i2").tobytes()
        clouds.append({"t": round(t, 4), "points": base64.b64encode(packed).decode("ascii")})
        last_time = t
    return clouds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    bag = args.bag.resolve()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Replay already exists at {output}. Choose a new output path.")
    info = yaml.safe_load((bag / "metadata.yaml").read_text())["rosbag2_bagfile_information"]
    if info["storage_identifier"] != "sqlite3":
        parser.error("Replay export expects a SQLite bag")
    files = info["relative_file_paths"]
    start_ns = info["starting_time"]["nanoseconds_since_epoch"]
    duration = info["duration"]["nanoseconds"] / 1e9
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="replay-", dir=output.parent) as staging:
        directory = Path(staging)
        maps, timeline = capture_slam(bag, start_ns, duration)
        print("Encoding the synchronized camera and lidar tracks", flush=True)
        encode_video(bag, files, start_ns, duration, directory / "camera.mp4")
        clouds = encode_clouds(bag, files, start_ns)
        data = {"duration": duration, "maps": maps, "timeline": timeline, "clouds": clouds}
        with gzip.open(directory / "replay.json.gz", "wt", encoding="utf-8") as handle:
            json.dump(data, handle, separators=(",", ":"), allow_nan=False)
        output.mkdir()
        (directory / "camera.mp4").replace(output / "camera.mp4")
        (directory / "replay.json.gz").replace(output / "replay.json.gz")
    print(f"{output} · {len(maps)} maps, {len(timeline[-1]['path'])} keyframes, {len(clouds)} lidar frames")


if __name__ == "__main__":
    main()
