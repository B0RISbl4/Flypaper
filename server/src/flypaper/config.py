import os
from pathlib import Path

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_DIR = Path(os.environ.get("FLYPAPER_PUBLIC_DIR", PROJECT_ROOT / "public")).resolve()
# записи гостевой книги: текстовый файл вне public/, чтобы его нельзя было скачать с сайта
GUESTBOOK_FILE = Path(os.environ.get("FLYPAPER_GUESTBOOK_FILE", PROJECT_ROOT / "server" / "data" / "guestbook.txt")).resolve()

LAT, LON = 59.938744, 30.314166
RADIUS_M = 75_000
AIRCRAFT_POLL_S = 10

AIRPORT = "LED"
FLIGHT_LIMIT = 100
BOARD_POLL_S = 30

MAX_RATE_LIMIT_BACKOFF_S = 15 * 60
