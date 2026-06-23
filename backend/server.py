from __future__ import annotations

import json
import mimetypes
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from content_store import read_content, refresh_content, start_daily_refresh_thread
from scheduler import enqueue_digest
from subscription_store import ValidationError, create_subscription, read_subscriptions


ROOT = Path(__file__).resolve().parent.parent
PORT = 3000


class CultureHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return

        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def guess_type(self, path):
        if path.endswith(".js"):
            return "application/javascript; charset=utf-8"
        if path.endswith(".css"):
            return "text/css; charset=utf-8"
        guessed = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if guessed.startswith("text/") or guessed == "application/json":
            return f"{guessed}; charset=utf-8"
        return guessed

    def handle_api_get(self, parsed):
        if parsed.path == "/api/health":
            self.send_json({"ok": True, "app": "Культурная лента"})
            return

        if parsed.path == "/api/subscriptions":
            query = parse_qs(parsed.query)
            email = query.get("email", [""])[0].lower()
            items = read_subscriptions()
            if email:
                items = [item for item in items if item.get("email") == email]
            self.send_json({"items": items})
            return

        if parsed.path == "/api/content":
            self.send_json(read_content())
            return

        self.send_json({"error": "API endpoint not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/subscriptions":
            self.handle_subscription_post()
            return
        if parsed.path == "/api/refresh":
            self.handle_refresh_post()
            return
        self.send_json({"error": "API endpoint not found"}, HTTPStatus.NOT_FOUND)

    def handle_subscription_post(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            subscription = create_subscription(payload)
            job = enqueue_digest(subscription)
            next_run = datetime.fromisoformat(subscription["nextRunAt"])
            self.send_json(
                {
                    "subscription": subscription,
                    "job": job,
                    "nextRunLabel": next_run.strftime("%d.%m.%Y, %H:%M"),
                },
                HTTPStatus.CREATED,
            )
        except ValidationError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except json.JSONDecodeError:
            self.send_json({"error": "Некорректный JSON"}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            self.send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_refresh_post(self):
        def run_refresh():
            try:
                refresh_content(force=True)
            except Exception as error:
                print(f"[parser] manual refresh failed: {error}")

        threading.Thread(target=run_refresh, daemon=True).start()
        self.send_json({"ok": True, "message": "Обновление источников запущено"})

    def send_json(self, payload, status=HTTPStatus.OK):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    start_daily_refresh_thread()
    server = ThreadingHTTPServer(("localhost", PORT), CultureHandler)
    print(f"Культурная лента запущена: http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
