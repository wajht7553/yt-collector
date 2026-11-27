"""Local HTTP server for reviewing saved YouTube links."""

import http.server
import json
from pathlib import Path
import webbrowser

from .. import catalog, search


PAGE_SIZE = 20
TEMPLATE_PATH = Path(__file__).with_name("templates") / "index.html"


def _create_handler(config, language=None):
    html = TEMPLATE_PATH.read_text(encoding="utf-8").replace("{{PAGE_SIZE}}", str(PAGE_SIZE))

    class ReviewHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self._send(html.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/config":
                self._send_json({
                    "name": config["name"],
                    "language": language or config["language"],
                    "locked_language": language,
                })
            elif self.path == "/api/videos":
                with catalog.connect(config) as db:
                    self._send_json(catalog.list_videos(db, language=language))
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/api/decide":
                self.send_error(404)
                return
            if self.headers.get_content_type() != "application/json":
                self.send_error(415)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError
                body = json.loads(self.rfile.read(length))
                class_name, lang, video_id = catalog.video_key(body)
                status = body["status"]
                if not isinstance(class_name, str) or not isinstance(lang, str):
                    raise ValueError
                if not search.valid_id(video_id) or status not in catalog.STATUSES:
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                self.send_error(400, "Invalid review decision")
                return
            if language is not None and lang != language:
                self.send_error(404)
                return

            with catalog.connect(config) as db:
                saved = catalog.set_status(db, (class_name, lang, video_id), status)
            if saved:
                self._send_json({"status": status})
            else:
                self.send_error(404)

        def _send(self, data, content_type):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, data):
            self._send(json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

        def log_message(self, format, *args):
            pass

    return ReviewHandler


def serve(config, port=8765, language=None):
    with catalog.connect(config):
        pass
    handler = _create_handler(config, language)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{httpd.server_port}"
        print(f"Reviewing {config['name']}" + (f" [{language}]" if language else ""))
        print(f"Open in browser: {url}\nPress Ctrl+C to stop.")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
