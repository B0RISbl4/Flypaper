import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

MAX_NAME = 40
MAX_TEXT = 1000


class GuestbookError(ValueError):
    pass


def validate(data) -> dict:
    if not isinstance(data, dict):
        raise GuestbookError("Неверный формат записи.")
    name = str(data.get("name") or "").strip()
    text = str(data.get("text") or "").strip()
    airport = str(data.get("airport") or "").strip().upper()
    airline = str(data.get("airline") or "").strip().upper()

    if not name or not text:
        raise GuestbookError("Заполните имя и сообщение.")
    if len(name) > MAX_NAME or len(text) > MAX_TEXT:
        raise GuestbookError(f"Имя — до {MAX_NAME} символов, сообщение — до {MAX_TEXT}.")
    if airport and not re.fullmatch(r"[A-Z]{3}", airport):
        raise GuestbookError("Код аэропорта — ровно 3 буквы, например LED.")
    if airline and not re.fullmatch(r"[A-Z0-9]{2}", airline):
        raise GuestbookError("Код авиакомпании — ровно 2 символа, например S7.")
    return {"name": name, "airport": airport, "airline": airline, "text": text}


class Guestbook:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()          # два одновременных POST не перемешают строки

    def entries(self) -> list[dict]:
        with self._lock:
            if not self.path.exists():
                return []
            lines = self.path.read_text(encoding="utf-8").splitlines()
        result = []
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                log.warning("%s:%d: строка пропущена — не JSON", self.path.name, number)
                continue
            if isinstance(entry, dict):
                result.append(entry)
        return result[::-1]

    def add(self, data) -> dict:
        entry = {**validate(data), "date": datetime.now().strftime("%d.%m.%Y")}
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(line)
        return entry
