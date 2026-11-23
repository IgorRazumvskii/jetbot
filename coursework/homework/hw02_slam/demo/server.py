"""Serve the finished rosbag replay over loopback, including MP4 byte ranges."""

import argparse
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
SHARED = HERE.parents[2] / "labs/lab03_odometry/teleop"
PAGES = {
    "/": (HERE / "index.html", "text/html; charset=utf-8"),
    "/playback.js": (HERE / "playback.js", "text/javascript; charset=utf-8"),
    "/cloud.js": (HERE / "cloud.js", "text/javascript; charset=utf-8"),
    "/playback.css": (HERE / "playback.css", "text/css; charset=utf-8"),
    "/slam.js": (SHARED / "slam.js", "text/javascript; charset=utf-8"),
    "/panel.css": (SHARED / "panel.css", "text/css; charset=utf-8"),
}


def byte_range(value, size):
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not match or not any(match.groups()) or not size:
        raise ValueError("Invalid byte range")
    start, end = match.groups()
    if not start:
        length = int(end)
        if length <= 0:
            raise ValueError("Empty suffix")
        return max(0, size - length), size - 1
    first = int(start)
    last = min(int(end), size - 1) if end else size - 1
    if first > last:
        raise ValueError("Unsatisfiable byte range")
    return first, last


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.serve_file(send_body=True)

    def do_HEAD(self):
        self.serve_file(send_body=False)

    def serve_file(self, send_body):
        if self.headers.get("Host") not in {"127.0.0.1:8767", "localhost:8767"}:
            self.send_error(403)
            return
        route = urlsplit(self.path).path
        if route not in self.server.pages:
            self.send_error(404)
            return
        path, kind = self.server.pages[route]
        with path.open("rb") as source:
            size = path.stat().st_size
            first, last = 0, size - 1
            requested = self.headers.get("Range") if route == "/camera.mp4" else None
            if requested:
                try:
                    first, last = byte_range(requested, size)
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            self.send_response(206 if requested else 200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(last - first + 1))
            self.send_header("Cache-Control", "no-store")
            if route == "/camera.mp4":
                self.send_header("Accept-Ranges", "bytes")
            if requested:
                self.send_header("Content-Range", f"bytes {first}-{last}/{size}")
            if route == "/replay.json":
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            if send_body:
                source.seek(first)
                remaining = last - first + 1
                try:
                    while remaining and (chunk := source.read(min(remaining, 256 * 1024))):
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    replay = args.replay.resolve()
    media = {
        "/camera.mp4": (replay / "camera.mp4", "video/mp4"),
        "/replay.json": (replay / "replay.json.gz", "application/json"),
    }
    for path, _ in media.values():
        if not path.is_file():
            parser.error(f"Missing replay data: {path}")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8767), Handler)
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        raise SystemExit("Port 8767 is in use. Stop the previous demo before starting another.")

    with server:
        server.pages = PAGES | media
        print("SLAM replay: http://127.0.0.1:8767/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
