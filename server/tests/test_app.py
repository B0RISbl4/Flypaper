import http.client
import json
import threading
from functools import partial

import pytest

from flypaper.app import make_server
from flypaper.guestbook import Guestbook
from flypaper.pollers import State


@pytest.fixture
def site(tmp_path):
    public = tmp_path / "public"
    (public / "assets" / "js").mkdir(parents=True)
    (public / "index.html").write_text("<!doctype html><title>Flypaper</title>", encoding="utf-8")
    (public / "assets" / "js" / "main.js").write_text("export {};", encoding="utf-8")
    (public / ".secret").write_text("hidden", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("outside", encoding="utf-8")

    state = State()
    guestbook_file = tmp_path / "data" / "guestbook.txt"
    server = make_server("127.0.0.1", 0, state, public, Guestbook(guestbook_file))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        conn.request(method, path, body=body, headers={"Content-Type": "application/json"} if body else {})
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()

    get = partial(request, "GET")
    get.post = partial(request, "POST")
    get.guestbook_file = guestbook_file
    yield state, get
    server.shutdown()
    server.server_close()


def test_static_pages_are_served(site):
    _, get = site
    status, ctype, body = get("/")
    assert status == 200 and b"Flypaper" in body
    assert ctype.startswith("text/html")


def test_js_modules_get_javascript_mime_type(site):
    _, get = site
    status, ctype, _ = get("/assets/js/main.js")
    assert status == 200
    assert ctype.startswith("text/javascript")


@pytest.mark.parametrize("path", ["/.secret", "/../outside.txt", "/%2e%2e/outside.txt", "/assets/"])
def test_hidden_files_parent_dirs_and_listings_are_not_served(site, path):
    _, get = site
    assert get(path)[0] == 404


def test_board_is_unavailable_until_first_poll(site):
    state, get = site
    assert get("/api/board")[0] == 503
    state.board = {"airport": "LED", "updated": 1, "departures": [], "arrivals": []}
    status, ctype, body = get("/api/board")
    assert status == 200 and ctype.startswith("application/json")
    assert json.loads(body)["airport"] == "LED"


def test_aircraft_api_returns_current_state(site):
    state, get = site
    assert json.loads(get("/api/aircraft")[2]) == {"aircraft": None}
    state.aircraft = {"callsign": "SBI1037"}
    assert json.loads(get("/api/aircraft?t=1")[2]) == {"aircraft": {"callsign": "SBI1037"}}


def test_guestbook_starts_empty_and_saves_entries(site):
    _, get = site
    assert json.loads(get("/api/guestbook")[2]) == {"entries": []}

    for name in ("Аня", "Борис"):
        body = json.dumps({"name": name, "airport": "led", "airline": "s7", "text": "Привет!"}).encode()
        status, _, data = get.post("/api/guestbook", body)
        assert status == 201
        assert json.loads(data)["entry"]["airport"] == "LED"

    entries = json.loads(get("/api/guestbook")[2])["entries"]
    assert [e["name"] for e in entries] == ["Борис", "Аня"]
    assert len(get.guestbook_file.read_text(encoding="utf-8").splitlines()) == 2


@pytest.mark.parametrize("payload, error", [
    ({"name": "", "text": "Привет"}, "Заполните имя и сообщение."),
    ({"name": "Аня", "text": "Привет", "airport": "LE"}, "Код аэропорта — ровно 3 буквы, например LED."),
    ({"name": "Аня", "text": "Привет", "airline": "S7X"}, "Код авиакомпании — ровно 2 символа, например S7."),
    ("не объект", "Неверный формат записи."),
])
def test_guestbook_rejects_invalid_entries(site, payload, error):
    _, get = site
    status, _, data = get.post("/api/guestbook", json.dumps(payload).encode())
    assert status == 400 and json.loads(data)["error"] == error
    assert not get.guestbook_file.exists()


def test_guestbook_rejects_broken_json_and_other_paths(site):
    _, get = site
    assert get.post("/api/guestbook", b"{oops")[0] == 400
    assert get.post("/api/board", b"{}")[0] == 404
