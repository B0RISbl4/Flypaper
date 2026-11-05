import re
import time

from .config import AIRPORT, FLIGHT_LIMIT

STATUSES = ("scheduled", "estimated", "delayed", "departed", "landed", "canceled", "diverted")


def _get(data, *keys):
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _status(flight):
    generic = str(_get(flight, "status", "generic", "status", "text") or "").lower()
    if generic in STATUSES:
        return generic
    text = str(_get(flight, "status", "text") or "").lower()
    for status in STATUSES:
        if text.startswith(status[:5]):           # cancel(l)ed, divert…, estimat…
            return status
    return "unknown"


def _number(flight, airline):
    number = _get(flight, "identification", "number", "default") or _get(flight, "identification", "callsign") or ""
    match = re.fullmatch(r"([A-Z0-9]{2})(\d+[A-Z]?)", number)
    return f"{match.group(1)} {match.group(2)}" if match else number or (airline or "—")


def _rows(items, kind):
    other = "destination" if kind == "departure" else "origin"
    rows = []
    for item in items or []:
        flight = _get(item, "flight")
        scheduled = _get(flight, "time", "scheduled", kind)
        if not isinstance(scheduled, (int, float)):
            continue
        airline = _get(flight, "airline", "code", "iata")
        airport = _get(flight, "airport", other)
        event = (_get(flight, "time", "real", kind)
                 or _get(flight, "time", "estimated", kind)
                 or _get(flight, "status", "generic", "eventTime", "utc"))
        rows.append({
            "time": int(scheduled),
            "event": int(event) if isinstance(event, (int, float)) else None,
            "flight": _number(flight, airline),
            "airline": airline if isinstance(airline, str) and re.fullmatch(r"[A-Z0-9]{2}", airline) else None,
            "city": _get(airport, "position", "region", "city") or _get(airport, "name") or "",
            "airport": _get(airport, "code", "iata") or "",
            "status": _status(flight),
        })
    rows.sort(key=lambda row: row["time"])
    return rows


def fetch_board(api, code=AIRPORT):
    result = api.get_airport_details(code, flight_limit=FLIGHT_LIMIT)
    schedule = _get(result, "airport", "pluginData", "schedule") or {}
    return {
        "airport": code,
        "updated": int(time.time()),
        "departures": _rows(_get(schedule, "departures", "data"), "departure"),
        "arrivals": _rows(_get(schedule, "arrivals", "data"), "arrival"),
    }
