import json
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from FlightRadarAPI import FlightRadar24API
from flights import POLL_S, fetch_nearby

HERE = Path(__file__).parent
PORT = 8765
state = {"aircraft": None}


def poll():
    api = FlightRadar24API()
    while True:
        try:
            nearby = fetch_nearby(api)
            state["aircraft"] = asdict(nearby[0]) if nearby else None
        except Exception as e:
            print("poll failed:", e)   # при сбое остаётся последнее состояние
        time.sleep(POLL_S)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api":
            body, ctype = json.dumps(state).encode(), "application/json"
        else:
            body = (HERE / "index.html").read_bytes()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=poll, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()