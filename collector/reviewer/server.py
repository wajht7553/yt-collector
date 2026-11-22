"""Video & Link Review Tool server and API"""

import os
import json
import shutil
import mimetypes
import webbrowser
import http.server
import socketserver
import urllib.parse

from .. import logger, downloader

PAGE_SIZE = 20
_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "index.html")
STATUS_FOLDERS = {"accepted": "_accepted", "rejected": "_rejected"}
VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi")


def _load_template():
    """Load the HTML template with runtime values."""
    with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read().replace("{{PAGE_SIZE}}", str(PAGE_SIZE))


def _format_duration(seconds_val):
    """Format duration in seconds into M:SS or H:MM:SS."""
    if seconds_val is None or str(seconds_val).strip() == "":
        return ""
    try:
        total = int(round(float(seconds_val)))
        if total <= 0:
            return ""
        m, s = divmod(total, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except (ValueError, TypeError):
        return str(seconds_val)


def _load_decisions(config):
    """Load review decisions from JSON."""
    return logger.load_decisions(config)


def _save_decisions(config, decisions):
    """Save review decisions to JSON."""
    path = logger.get_decisions_path(config)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2, ensure_ascii=False)


def _scan_videos(config):
    """Scan local video files on disk and collected video links across all classes and languages."""
    videos = []
    seen_ids = set()
    decisions = _load_decisions(config)

    if not config.get("links_only"):
        for cls_name in _list_classes(config):
            for lang in logger.get_language_folders(config, cls_name):
                videos_dir = os.path.join(config["output_dir"], cls_name, lang, "Videos")
                if not os.path.exists(videos_dir):
                    continue
                for root, dirs, files in os.walk(videos_dir):
                    for f in sorted(files):
                        if f.lower().endswith(VIDEO_EXTS):
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, config["output_dir"])
                            parts = rel_path.split(os.sep)
                            status_hint = next(
                                (
                                    status
                                    for status, folder in STATUS_FOLDERS.items()
                                    if folder in parts
                                ),
                                "",
                            )
                            size_mb = round(
                                os.path.getsize(full_path) / (1024 * 1024), 1
                            )
                            base = os.path.splitext(f)[0]
                            vid = base[-11:] if len(base) > 12 and base[-12] == "_" else ""
                            if vid:
                                seen_ids.add((cls_name, lang, vid))
                            videos.append(
                                {
                                    "is_file": True,
                                    "name": f,
                                    "title": f,
                                    "path": rel_path,
                                    "cls": cls_name,
                                    "lang": lang,
                                    "size_mb": size_mb,
                                    "status_hint": status_hint,
                                }
                            )

    for r in logger.load_all_entries(config):
        cls_name = r["Class"]
        lang = r["Language"]
        vid = r["Video_ID"]
        url = r["Source_URL"]
        if (cls_name, lang, vid) in seen_ids:
            continue

        key = logger.get_decision_key(cls_name, lang, vid or url)
        status = logger.get_decision_status(decisions, cls_name, lang, vid, url)

        is_yt = "youtube.com" in url or "youtu.be" in url
        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if (is_yt and vid) else ""
        embed_url = (
            f"https://www.youtube.com/embed/{vid}?autoplay=1&rel=0"
            if (is_yt and vid)
            else ""
        )

        videos.append(
            {
                "is_file": False,
                "name": r.get("Title") or vid or url,
                "title": r.get("Title") or vid or url,
                "path": key,
                "key": key,
                "video_id": vid,
                "url": url,
                "embed_url": embed_url,
                "thumbnail": thumb,
                "channel": r.get("Channel") or "Unknown",
                "duration": _format_duration(r.get("Duration", "")),
                "keyword": r.get("Keyword") or "",
                "cls": cls_name,
                "lang": lang,
                "status_hint": status if status != "pending" else "",
            }
        )

    return videos


def _list_classes(config):
    """Return all class names from config and collected links."""
    classes = list(config.get("classes", {}).keys())
    for r in logger.load_all_entries(config):
        if r["Class"] and r["Class"] not in classes:
            classes.append(r["Class"])
    return classes


def _list_languages(config):
    """Return the sorted set of languages present across all classes."""
    languages = set()
    for cls_name in _list_classes(config):
        languages.update(logger.get_language_folders(config, cls_name))
    if not languages and config.get("language"):
        languages.add(config["language"])
    return sorted(languages)


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
            end = file_size - 1 if end_str == "" else min(int(end_str), file_size - 1)
            if start >= file_size or end < start:
                return None
    except ValueError:
        return None

    return start, end


def apply_decisions(config):
    """Move accepted/rejected video files into status folders and sync accepted/rejected/pending link files."""
    decisions = _load_decisions(config)
    updated = {}
    moved = {"accepted": 0, "rejected": 0, "pending": 0}

    # 1. Handle local video files if any exist on disk
    for path, status in decisions.items():
        folder_name = STATUS_FOLDERS.get(status)
        full = os.path.join(config["output_dir"], path)
        if folder_name and os.path.isfile(full):
            if folder_name not in path.split(os.sep):
                dest_dir = os.path.join(os.path.dirname(full), folder_name)
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, os.path.basename(full))
                try:
                    shutil.move(full, dest)
                    path = os.path.relpath(dest, config["output_dir"])
                    moved[status] += 1
                except OSError as e:
                    print(f"  [WARN] Could not move {path}: {e}")
        updated[path] = status

    # 2. Sync link lists (accepted_links.txt, rejected_links.txt, pending_links.txt)
    records = logger.load_all_entries(config)
    grouped = {}
    link_counts = {"accepted": 0, "rejected": 0, "pending": 0}
    all_accepted_urls = []

    for r in records:
        cls_name = r["Class"]
        lang = r["Language"]
        vid = r["Video_ID"]
        url = r["Source_URL"]
        key = logger.get_decision_key(cls_name, lang, vid or url)
        status = logger.get_decision_status(updated, cls_name, lang, vid, url)

        if status in ("accepted", "rejected"):
            updated[key] = status
            link_counts[status] += 1
        else:
            status = "pending"
            link_counts["pending"] += 1

        bucket = grouped.setdefault(
            (cls_name, lang), {"accepted": [], "rejected": [], "pending": []}
        )
        if url not in bucket[status]:
            bucket[status].append(url)
        if status == "accepted" and url not in all_accepted_urls:
            all_accepted_urls.append(url)

    out_dir = config["output_dir"]
    for (cls_name, lang), lists in grouped.items():
        lang_dir = os.path.join(out_dir, cls_name, lang)
        os.makedirs(lang_dir, exist_ok=True)
        for st_name, filename in (
            ("accepted", "accepted_links.txt"),
            ("rejected", "rejected_links.txt"),
            ("pending", "pending_links.txt"),
        ):
            fpath = os.path.join(lang_dir, filename)
            with open(fpath, "w", encoding="utf-8") as f:
                for u in lists[st_name]:
                    f.write(u + "\n")

    if os.path.exists(out_dir) and records:
        master_accepted = os.path.join(out_dir, "accepted_links.txt")
        with open(master_accepted, "w", encoding="utf-8") as f:
            for u in all_accepted_urls:
                f.write(u + "\n")

    _save_decisions(config, updated)
    if config.get("links_only") or (moved["accepted"] == 0 and moved["rejected"] == 0):
        return link_counts
    return moved


def _create_handler(config):
    """Create a request handler class bound to the config."""

    class ReviewHandler(http.server.BaseHTTPRequestHandler):

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)

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
                        "classes": _list_classes(config),
                        "languages": _list_languages(config),
                        "language": config["language"],
                        "links_only": config.get("links_only", False),
                    }
                )

            elif parsed.path == "/api/stream":
                video_url = (query.get("url") or [""])[0]
                if not video_url:
                    self._send_json({"error": "Missing url parameter"}, status=400)
                    return
                stream_url = downloader.get_direct_stream_url(
                    video_url, resolution=config.get("resolution", 720)
                )
                if stream_url:
                    self._send_json({"stream_url": stream_url})
                else:
                    self._send_json(
                        {"error": "Could not extract direct stream URL via yt-dlp"},
                        status=404,
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
                path = body["path"]
                status = body["status"]

                path_parts = path.split(os.sep)
                current_folder = next(
                    (
                        folder
                        for folder in STATUS_FOLDERS.values()
                        if folder in path_parts
                    ),
                    None,
                )
                if current_folder and STATUS_FOLDERS.get(status) != current_folder:
                    full = os.path.join(config["output_dir"], path)
                    if os.path.isfile(full):
                        restored_dir = os.path.dirname(os.path.dirname(full))
                        restored_full = os.path.join(
                            restored_dir, os.path.basename(full)
                        )
                        if not os.path.exists(restored_full):
                            shutil.move(full, restored_full)
                            decisions.pop(path, None)
                            path = os.path.relpath(restored_full, config["output_dir"])

                if status == "pending":
                    decisions.pop(path, None)
                else:
                    decisions[path] = status
                _save_decisions(config, decisions)
                apply_decisions(config)
                self._send_json({"ok": True, "path": path})
            else:
                self.send_error(404)

        def _send_html(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_load_template().encode("utf-8"))

        def _send_json(self, data, status=200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))

        def _serve_video(self, encoded_path):
            """Serve local video file with HTTP Range support for seeking."""
            video_path = urllib.parse.unquote(encoded_path)
            full_path = os.path.join(config["output_dir"], video_path)

            if not os.path.isfile(full_path):
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
                        pass
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
