import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .guestbook import Guestbook, GuestbookError
from .pollers import State

MAX_BODY = 16 * 1024

# Типы задаём явно: на Windows mimetypes берёт их из реестра, и там .js бывает
# text/plain — браузер с таким типом не загружает ES-модули.
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, **MIME_TYPES}

    def __init__(self, *args, state: State, public_dir: Path, guestbook: Guestbook, **kwargs):
        self.state = state
        self.public_dir = public_dir
        self.guestbook = guestbook
        super().__init__(*args, directory=str(public_dir), **kwargs)


    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/board":
            if self.state.board is None:
                return self.send_error(503, "Board is not ready")
            return self.send_json(self.state.board)

        if path == "/api/aircraft":
            return self.send_json({"aircraft": self.state.aircraft})

        if path == "/api/guestbook":
            return self.send_json({"entries": self.guestbook.entries()})

        return super().do_GET()

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/guestbook":
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            return self.send_json({"error": "Слишком длинная или пустая запись."}, 400)
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            entry = self.guestbook.add(data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json({"error": "Неверный формат записи."}, 400)
        except GuestbookError as error:
            return self.send_json({"error": str(error)}, 400)
        return self.send_json({"entry": entry}, 201)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass


    def send_head(self):
        target = Path(self.translate_path(self.path)).resolve()   # %xx и ../ уже разобраны
        if not target.is_relative_to(self.public_dir) or \
                any(part.startswith(".") for part in target.relative_to(self.public_dir).parts):
            self.send_error(404)
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404)
        return None


def make_server(host: str, port: int, state: State, public_dir: Path, guestbook: Guestbook) -> ThreadingHTTPServer:
    handler = partial(Handler, state=state, public_dir=Path(public_dir).resolve(), guestbook=guestbook)
    return ThreadingHTTPServer((host, port), handler)
