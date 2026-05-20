"""Video Review Tool server and API."""

import http.server
import json
import mimetypes
import os
import shutil
import socketserver
import urllib.parse
import webbrowser

from .. import logger

PAGE_SIZE = 20
_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "index.html")
_HTML_CACHE = None


def _load_template():
    """Load and cache the HTML template with runtime values."""
    global _HTML_CACHE
    if _HTML_CACHE is None:
        with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            _HTML_CACHE = f.read().replace("{{PAGE_SIZE}}", str(PAGE_SIZE))
    return _HTML_CACHE


def _scan_videos(config):
    """Scan all video files in configured class folders."""
    videos = []
    for cls_name in config["classes"]:
        videos_dir = os.path.join(config["output_dir"], cls_name, "Videos")
        if not os.path.exists(videos_dir):
            continue
        for root, dirs, files in os.walk(videos_dir):
            for f in sorted(files):
                if f.lower().endswith((".mp4", ".mkv", ".webm", ".avi")):
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, config["output_dir"])
                    status_hint = "rejected" if "_rejected" in rel_path.split(os.sep) else ""
                    size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 1)
                    videos.append(
                        {
                            "name": f,
                            "path": rel_path,
                            "cls": cls_name,
                            "size_mb": size_mb,
                            "status_hint": status_hint,
                        }
                    )
    return videos


def _load_decisions(config):
    """Load review decisions from JSON."""
    path = logger.get_decisions_path(config)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_decisions(config, decisions):
    """Save review decisions to JSON."""
    path = logger.get_decisions_path(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2, ensure_ascii=False)


def _guess_mime(path):
    """Return a best-effort MIME type for a video file."""
    mime, _ = mimetypes.guess_type(path)
    return mime or "video/mp4"


def _parse_range(range_header, file_size):
    """Parse a Range header into (start, end) byte positions."""
    if not range_header or not range_header.startswith("bytes="):
        return None
    range_spec = range_header.replace("bytes=", "", 1).strip()
    if "," in range_spec:
        range_spec = range_spec.split(",", 1)[0].strip()
    if "-" not in range_spec:
        return None

    start_str, end_str = range_spec.split("-", 1)
    try:
        if start_str == "":
            suffix = int(end_str)
            if suffix <= 0:
                return None
            start = max(0, file_size - suffix)
            end = file_size - 1
        else:
            start = int(start_str)
            if start < 0:
                return None
            if end_str == "":
                end = file_size - 1
            else:
                end = int(end_str)
            if start >= file_size:
                return None
            end = min(end, file_size - 1)
            if end < start:
                return None
    except ValueError:
        return None

    return start, end


def _create_handler(config):
    """Create a request handler class bound to the config."""

    class ReviewHandler(http.server.BaseHTTPRequestHandler):

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)

            if parsed.path == "/":
                self._send_html()

            elif parsed.path == "/api/videos":
                videos = _scan_videos(config)
                self._send_json(videos)

            elif parsed.path == "/api/decisions":
                decisions = _load_decisions(config)
                self._send_json(decisions)

            elif parsed.path == "/api/config":
                self._send_json(
                    {
                        "name": config["name"],
                        "classes": list(config["classes"].keys()),
                    }
                )

            elif parsed.path.startswith("/video/"):
                self._serve_video(parsed.path[7:])

            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/api/decide":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                decisions = _load_decisions(config)
                if body["status"] == "pending":
                    decisions.pop(body["path"], None)
                else:
                    decisions[body["path"]] = body["status"]
                _save_decisions(config, decisions)
                self._send_json({"ok": True})

            elif self.path == "/api/apply":
                decisions = _load_decisions(config)
                moved = 0
                for path, status in decisions.items():
                    if status == "rejected":
                        full = os.path.join(config["output_dir"], path)
                        if os.path.exists(full):
                            reject_dir = os.path.join(
                                os.path.dirname(full), "_rejected"
                            )
                            os.makedirs(reject_dir, exist_ok=True)
                            shutil.move(
                                full, os.path.join(reject_dir, os.path.basename(full))
                            )
                            moved += 1
                self._send_json({"moved": moved})
            else:
                self.send_error(404)

        def _send_html(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_load_template().encode("utf-8"))

        def _send_json(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        def _serve_video(self, encoded_path):
            """Serve video with HTTP Range support for seeking."""
            video_path = urllib.parse.unquote(encoded_path)
            full_path = os.path.join(config["output_dir"], video_path)

            if not os.path.exists(full_path):
                self.send_error(404, "Video not found")
                return

            file_size = os.path.getsize(full_path)
            range_header = self.headers.get("Range")
            mime_type = _guess_mime(full_path)
            byte_range = _parse_range(range_header, file_size) if range_header else None

            if range_header and byte_range is None:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return

            if byte_range:
                start, end = byte_range
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(full_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    try:
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                    except (
                        ConnectionResetError,
                        ConnectionAbortedError,
                        BrokenPipeError,
                    ):
                        pass  # Browser cancelled (user seeked)
            else:
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                try:
                    with open(full_path, "rb") as f:
                        shutil.copyfileobj(f, self.wfile)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    pass

        def log_message(self, format, *args):
            """Suppress noisy logs."""
            pass

    return ReviewHandler


def serve(config, port=8765):
    """Start the review server."""
    handler = _create_handler(config)

    class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        daemon_threads = True
        allow_reuse_address = True

    with ThreadedServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"\n  Video Review Tool")
        print(f"  Project: {config['name']}")
        print(f"  Open in browser: {url}")
        print(f"  Press Ctrl+C to stop\n")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Shutting down.")


def clean_rejected(config):
    """Move rejected videos to _rejected/ folders."""
    decisions = _load_decisions(config)
    moved = 0
    for path, status in decisions.items():
        if status == "rejected":
            full = os.path.join(config["output_dir"], path)
            if os.path.exists(full):
                reject_dir = os.path.join(os.path.dirname(full), "_rejected")
                os.makedirs(reject_dir, exist_ok=True)
                shutil.move(full, os.path.join(reject_dir, os.path.basename(full)))
                moved += 1
    return moved
