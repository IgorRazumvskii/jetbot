"""Local JetBot teleoperation panel for macOS."""

import argparse
import io
import json
import math
import secrets
import shlex
import subprocess
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
MAP_BRIDGE = HERE.parent.parent / "lab04_mapping" / "map_bridge.py"
LIMITS = (0.20, 1.0)
DEADMAN = 0.23
ROBOT_PREFIX = "cd ~/robotics-course && "
ODOMETRY_FIELDS = ("odom", "lidar_odom", "ekf_odom")


class Panel:
    def __init__(self, target, control_path):
        self.ssh = ["/usr/bin/ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
        if control_path:
            self.ssh.extend(["-S", control_path])
        self.ssh.append(target)
        self.condition = threading.Condition()
        self.done = threading.Event()
        self.frame = b""
        self.frame_id = 0
        self.frame_at = 0.0
        self.telemetry = {}
        self.telemetry_at = 0.0
        self.slam_state = {}
        self.slam_at = 0.0
        self.lease = None
        self.sequence = -1
        self.command_at = 0.0
        self.command = (0.0, 0.0)
        self.start_id = 0
        self.start_reference = None
        self.children = []
        self.error = ""

    def start_bridge(self, path):
        bootstrap = (
            "import sys; n = int(sys.stdin.buffer.readline()); "
            "exec(compile(sys.stdin.buffer.read(n), " + repr(path.name) + ", 'exec'))"
        )
        bridge = subprocess.Popen(
            [*self.ssh, ROBOT_PREFIX + "./dockers/scripts/ros.sh python3 -u -c " + shlex.quote(bootstrap)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0,
        )
        self.children.append(bridge)
        source = path.read_bytes()
        bridge.stdin.write(f"{len(source)}\n".encode() + source)
        return bridge

    def start(self):
        self.bridge = self.start_bridge(HERE / "robot.py")
        self.map_bridge = self.start_bridge(MAP_BRIDGE)
        self.camera = subprocess.Popen([
            *self.ssh, ROBOT_PREFIX + "./labs/lab02_sensors_actuators/camera-preview.sh",
        ], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
        self.children.append(self.camera)
        for task in (self.read_odom, self.read_slam, self.read_camera, self.send_commands):
            threading.Thread(target=task, daemon=True).start()

    def read_odom(self):
        for line in io.BufferedReader(self.bridge.stdout):
            if not line.startswith(b"{"):
                continue
            data = json.loads(line)
            if data["odom"] and not all(math.isfinite(value) for value in data["odom"]):
                data.update(odom=None, ready=False)
            with self.condition:
                self.telemetry = data
                self.telemetry_at = time.monotonic()
        with self.condition:
            self.error = "Соединение с ROS прервано"

    def read_slam(self):
        for line in io.BufferedReader(self.map_bridge.stdout):
            if not line.startswith(b"{"):
                continue
            data = json.loads(line)
            with self.condition:
                self.slam_state.update(data)
                self.slam_at = time.monotonic()

    def slam(self, revision):
        with self.condition:
            fresh = time.monotonic() - self.slam_at < 1.5
            grid = self.slam_state.get("map")
            result = {
                "connected": fresh,
                "pose": self.slam_state.get("pose") if fresh else None,
                "graph": self.slam_state.get("graph"),
            }
            if grid is None or str(grid["revision"]) != revision:
                result["map"] = grid
            return result

    def read_camera(self):
        buffer = b""
        while chunk := self.camera.stdout.read1(16384):
            buffer += chunk
            while True:
                start = buffer.find(b"\xff\xd8")
                if start < 0:
                    buffer = buffer[-1:]
                    break
                buffer = buffer[start:]
                end = buffer.find(b"\xff\xd9", 2)
                if end < 0:
                    if len(buffer) > 1024 * 1024:
                        buffer = buffer[-1:]
                    break
                frame, buffer = buffer[:end + 2], buffer[end + 2:]
                with self.condition:
                    self.frame = frame
                    self.frame_id += 1
                    self.frame_at = time.monotonic()
                    self.condition.notify_all()
        with self.condition:
            self.error = "Поток камеры завершился"

    def ready(self, now):
        return bool(self.telemetry.get("ready") and now - self.telemetry_at < 0.8
                    and self.frame_id and now - self.frame_at < 1.5 and not self.error)

    def disarm(self):
        self.lease = None
        self.sequence = -1
        self.command = (0.0, 0.0)

    def send_commands(self):
        last = (0.0, 0.0)
        while not self.done.wait(0.045):
            now = time.monotonic()
            with self.condition:
                if not self.ready(now) or now - self.command_at > DEADMAN:
                    self.disarm()
                current = self.command if self.lease else (0.0, 0.0)
                gate = self.telemetry.get("gate", 0.0)
            if not (any(current) or any(last)):
                continue
            try:
                self.bridge.stdin.write(f"{gate:.6f} {current[0]:.4f} {current[1]:.4f}\n".encode())
            except OSError:
                with self.condition:
                    self.disarm()
                    self.error = "Канал управления закрыт"
                return
            last = current

    def control(self, operation, payload):
        now = time.monotonic()
        with self.condition:
            if operation == "stop":
                if payload.get("lease") == self.lease:
                    self.disarm()
                return {"ok": True}
            if operation == "mark-start":
                if self.lease or not self.ready(now):
                    return {"ok": False}
                self.start_id += 1
                self.start_reference = None
                return {"ok": True}
            if operation == "arm":
                if not self.ready(now) or self.lease:
                    return {"ok": False}
                self.lease = secrets.token_urlsafe(18)
                self.command_at = now
                return {"ok": True, "lease": self.lease}
            if operation != "drive" or not self.lease or payload.get("lease") != self.lease:
                return {"ok": False}
            if not self.ready(now) or now - self.command_at > DEADMAN:
                self.disarm()
                return {"ok": False}
            sequence = payload.get("sequence")
            values = (payload.get("linear"), payload.get("angular"))
            if type(sequence) is not int or sequence <= self.sequence:
                return {"ok": False}
            if any(type(value) not in (int, float) or not -limit <= value <= limit
                   for value, limit in zip(values, LIMITS)):
                self.disarm()
                return {"ok": False}
            if any(values) and self.start_id and self.start_reference is None:
                self.start_reference = {
                    "utc": datetime.now(timezone.utc).isoformat(),
                    "origins": {
                        field: self.telemetry[field][:3] for field in ODOMETRY_FIELDS
                        if self.telemetry.get(field) is not None
                    },
                }
            self.sequence = sequence
            self.command_at = now
            self.command = values
            return {"ok": True}

    def status(self):
        now = time.monotonic()
        with self.condition:
            fresh = self.telemetry if now - self.telemetry_at < 0.8 else {}
            return {
                "ready": self.ready(now), "armed": self.lease is not None,
                "camera": bool(self.frame_id and now - self.frame_at < 1.5),
                "ros": bool(fresh),
                "odom": fresh.get("odom"),
                "lidar_odom": fresh.get("lidar_odom"),
                "ekf_odom": fresh.get("ekf_odom"),
                "start": {"id": self.start_id, "reference": self.start_reference} if self.start_id else None,
                "scan": fresh.get("scan"),
                "command": self.command, "error": self.error, "limits": LIMITS,
            }

    def close(self):
        self.done.set()
        with self.condition:
            self.disarm()
            self.condition.notify_all()
        for child in self.children:
            if child.stdin is None:
                continue
            child.stdin.close()
            try:
                child.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        for child in reversed(self.children):
            if child.poll() is None:
                child.terminate()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass

    def reply(self, body, mime):
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def reply_json(self, data):
        self.reply(json.dumps(data, allow_nan=False).encode(), "application/json")

    def valid_host(self):
        return self.headers.get("Host") == self.server.host

    def do_GET(self):
        if not self.valid_host():
            self.send_error(403)
            return
        request = urlsplit(self.path)
        panel = self.server.panel
        if request.path == "/":
            index = (HERE / "index.html").read_text().replace("__SESSION_TOKEN__", self.server.token)
            self.reply(index.encode(), "text/html; charset=utf-8")
        elif request.path in ("/panel.js", "/slam.js", "/panel.css"):
            mime = "text/javascript" if request.path.endswith(".js") else "text/css"
            self.reply((HERE / request.path[1:]).read_bytes(), mime)
        elif request.path == "/api/status":
            if self.headers.get("X-Teleop-Token") != self.server.token:
                self.send_error(403)
                return
            self.reply_json(panel.status())
        elif request.path == "/api/slam":
            if self.headers.get("X-Teleop-Token") != self.server.token:
                self.send_error(403)
                return
            revision = parse_qs(request.query).get("revision", [""])[0]
            self.reply_json(panel.slam(revision))
        elif request.path == "/video" and parse_qs(request.query).get("key") == [self.server.token]:
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            seen = 0
            try:
                while not panel.done.is_set():
                    with panel.condition:
                        panel.condition.wait_for(lambda: panel.frame_id != seen or panel.done.is_set(), timeout=1.0)
                        if panel.frame_id == seen:
                            continue
                        seen, frame = panel.frame_id, panel.frame
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                     + f"Content-Length: {len(frame)}\r\n\r\n".encode() + frame + b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                return
        else:
            self.send_error(404)

    def do_POST(self):
        if (not self.valid_host() or self.headers.get("Origin") != f"http://{self.server.host}"
                or self.headers.get("X-Teleop-Token") != self.server.token):
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 512:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            self.send_error(400)
            return
        operation = self.path.removeprefix("/api/")
        self.reply_json(self.server.panel.control(operation, payload))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--robot", default="jetbot@192.168.50.206")
    parser.add_argument("--control-path")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    panel = Panel(args.robot, args.control_path)
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.panel = panel
        server.host = f"127.0.0.1:{server.server_port}"
        server.token = secrets.token_urlsafe(24)
        try:
            panel.start()
            url = f"http://{server.host}"
            print(f"JetBot: {url}", flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            panel.close()


if __name__ == "__main__":
    main()
