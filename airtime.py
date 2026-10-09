import csv
import os
import time
from pathlib import Path

from FlightRadarAPI import FlightRadar24API
from flights import fetch_nearby, is_rate_limited, poll_delay

OUT = Path(__file__).parent / "airtime.csv"
INTERVAL_S = 60


def airline_of(a) -> str:
    if a.airline:
        return a.airline
    cs = a.callsign or ""
    return cs[:3] if len(cs) > 3 and cs[:3].isalpha() and cs[3].isdigit() else "?"

def load_names(api) -> dict[str, str]:
    try:
        return {a["ICAO"]: a["Name"] for a in api.get_airlines() if a.get("ICAO")}
    except Exception as e:
        print("airline names unavailable:", e)
        return {}

def load() -> dict[tuple[str, str], float]:
    if not OUT.exists():
        return {}
    with OUT.open(encoding="utf-8") as f:
        return {(r["airline"], r["type"]): float(r["minutes"]) for r in csv.DictReader(f)}


def save(totals, names):
    tmp = OUT.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["airline", "name", "type", "minutes"])
        for (al, t), m in sorted(totals.items(), key=lambda kv: -kv[1]):
            w.writerow([al, names.get(al, ""), t, round(m, 1)])
    os.replace(tmp, OUT)

if __name__ == "__main__":
    api = FlightRadar24API()
    names = load_names(api)
    totals = load()   # продолжает копить после перезапуска
    rate_limit_streak = 0
    while True:
        error = None
        try:
            nearby = fetch_nearby(api)
        except Exception as e:
            error = e
            if is_rate_limited(error):
                rate_limit_streak += 1
            else:
                rate_limit_streak = 0
            print(time.strftime("%H:%M:%S"), "poll failed:", e)
        else:
            rate_limit_streak = 0
            for a in nearby:
                key = (airline_of(a), a.type or "?")
                totals[key] = totals.get(key, 0) + INTERVAL_S / 60
            if nearby:
                save(totals, names)
        if is_rate_limited(error):
            delay = poll_delay(error, rate_limit_streak, INTERVAL_S)
            print(f"rate limited; retrying in {delay:g} seconds")
        else:
            delay = INTERVAL_S - time.time() % INTERVAL_S
        time.sleep(delay)