import json
import os
import re
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from FlightRadarAPI import FlightRadar24API
from curl_cffi import requests
from downloader import download_airline_tail
from flights import POLL_S, fetch_nearby, is_rate_limited, poll_delay
from livery import PLANES, apply_livery, imread, imwrite

HERE = Path(__file__).parent
PORT = 8765
TAIL_CACHE = HERE / "tail-cache"
state = {"aircraft": None}
tail_locks = {}
tail_locks_guard = threading.Lock()


def get_tail(code):
    path = TAIL_CACHE / f"{code}.png"
    if path.exists():
        return path.read_bytes()

    with tail_locks_guard:
        lock = tail_locks.setdefault(code, threading.Lock())
    with lock:
        if path.exists():
            return path.read_bytes()

        TAIL_CACHE.mkdir(exist_ok=True)
        temporary_path = TAIL_CACHE / f".{code}.{threading.get_ident()}.tmp.png"
        try:
            download_airline_tail(code, temporary_path)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return path.read_bytes()


def plane_image_is_cached(code):
    config = PLANES["tail"]
    tail_path = TAIL_CACHE / f"{code}.png"
    template_path = HERE / config["template"]
    rendered_path = HERE / "plane" / f"{code}.png"
    if not tail_path.is_file() or not template_path.is_file() or not rendered_path.is_file():
        return False
    source_time = max(
        tail_path.stat().st_mtime,
        template_path.stat().st_mtime,
        (HERE / "livery.py").stat().st_mtime,
    )
    return rendered_path.stat().st_mtime >= source_time


def get_plane_image(code):
    plane = "tail"
    config = PLANES[plane]
    tail_path = TAIL_CACHE / f"{code}.png"
    template_path = HERE / config["template"]
    rendered_path = HERE / "plane" / f"{code}.png"

    get_tail(code)
    source_time = max(
        tail_path.stat().st_mtime,
        template_path.stat().st_mtime,
        (HERE / "livery.py").stat().st_mtime,
    )
    if rendered_path.exists() and rendered_path.stat().st_mtime >= source_time:
        return rendered_path.read_bytes()

    with tail_locks_guard:
        lock = tail_locks.setdefault(f"plane_{code}_{plane}", threading.Lock())
    with lock:
        if rendered_path.exists() and rendered_path.stat().st_mtime >= source_time:
            return rendered_path.read_bytes()

        rendered_path.parent.mkdir(exist_ok=True)
        image = apply_livery(
            imread(template_path),
            imread(tail_path),
            config["fin_poly"],
            config.get("lead"),
            config["faces"],
            fin_quad=config.get("fin_quad"),
        )
        temporary_path = TAIL_CACHE / f".plane_{code}_{plane}.{threading.get_ident()}.tmp.png"
        try:
            imwrite(temporary_path, image)
            os.replace(temporary_path, rendered_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return rendered_path.read_bytes()


def poll():
    api = FlightRadar24API()
    rate_limit_streak = 0
    while True:
        error = None
        try:
            previous_aircraft = state["aircraft"]
            previous_registration = previous_aircraft.get("registration") if previous_aircraft else None
            previous_route = (
                (previous_aircraft.get("origin", ""), previous_aircraft.get("dest", ""))
                if previous_aircraft
                else None
            )
            nearby = fetch_nearby(
                api,
                detailed_registration=previous_registration,
                detailed_route=previous_route,
            )
            selected = asdict(nearby[0]) if nearby else None
            if selected and previous_aircraft and selected["registration"] == previous_registration:
                for field in (
                    "model_name", "year_built", "serial_number",
                    "registration_country", "registration_country_iso2", "aircraft_age",
                ):
                    if not selected[field]:
                        selected[field] = previous_aircraft.get(field, "")
                if selected["origin"] == previous_aircraft["origin"] and not selected["origin_city"]:
                    selected["origin_city"] = previous_aircraft.get("origin_city", "")
                if selected["dest"] == previous_aircraft["dest"] and not selected["dest_city"]:
                    selected["dest_city"] = previous_aircraft.get("dest_city", "")
            state["aircraft"] = selected
            rate_limit_streak = 0
        except Exception as e:
            error = e
            if is_rate_limited(error):
                rate_limit_streak += 1
            else:
                rate_limit_streak = 0
            print("poll failed:", error)   # при сбое остаётся последнее состояние
        delay = poll_delay(error, rate_limit_streak)
        if is_rate_limited(error):
            print(f"rate limited; retrying in {delay:g} seconds")
        time.sleep(delay)


class Handler(BaseHTTPRequestHandler):
    def write_body(self, body):
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == "/api":
            body, ctype = json.dumps(state).encode(), "application/json"
        elif self.path == "/aircraft.svg":
            body, ctype = (HERE / "shapes SVG" / "B738.svg").read_bytes(), "image/svg+xml"
        elif match := re.fullmatch(r"/shapesSVG/([A-Z0-9]{1,4})\.svg", self.path):
            shape_path = HERE / "shapes SVG" / f"{match.group(1)}.svg"
            if shape_path.is_file():
                body, ctype = shape_path.read_bytes(), "image/svg+xml"
            else:
                body, ctype = b"aircraft silhouette not found", "text/plain; charset=utf-8"
                self.send_response(404)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.write_body(body)
                return
        elif self.path == "/plane/empty.png":
            body, ctype = (HERE / "plane" / "empty.png").read_bytes(), "image/png"
        elif match := re.fullmatch(r"/plane-status/([A-Z0-9]{2})\.json", self.path):
            body = json.dumps({"available": plane_image_is_cached(match.group(1))}).encode()
            ctype = "application/json"
        elif match := re.fullmatch(r"/plane/([A-Z0-9]{2})\.png", self.path):
            try:
                body, ctype = get_plane_image(match.group(1)), "image/png"
            except (
                OSError,
                requests.exceptions.RequestException,
                SystemExit,
                ValueError,
            ) as e:
                print("plane image failed:", e)
                body, ctype = b"plane image unavailable", "text/plain; charset=utf-8"
                self.send_response(502)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.write_body(body)
                return
        elif match := re.fullmatch(r"/tail/([A-Z0-9]{2})\.png", self.path):
            try:
                body, ctype = get_tail(match.group(1)), "image/png"
            except (
                OSError,
                requests.exceptions.RequestException,
                SystemExit,
                ValueError,
            ) as e:
                print("tail fetch failed:", e)
                body, ctype = b"tail image unavailable", "text/plain; charset=utf-8"
                self.send_response(502)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.write_body(body)
                return
        else:
            body = (HERE / "index.html").read_bytes()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.write_body(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=poll, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()