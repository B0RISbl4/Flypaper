import logging
import threading
import time
from dataclasses import asdict, dataclass

from FlightRadarAPI import FlightRadar24API

from .board import fetch_board
from .config import AIRCRAFT_POLL_S, BOARD_POLL_S
from .flights import DETAIL_FIELDS, fetch_nearby
from .ratelimit import is_rate_limited, poll_delay

log = logging.getLogger(__name__)


@dataclass
class State:
    aircraft: dict | None = None
    board: dict | None = None


def carry_over_details(selected: dict | None, previous: dict | None) -> dict | None:
    if not selected or not previous or selected["registration"] != previous.get("registration"):
        return selected
    for field in DETAIL_FIELDS:
        if not selected[field]:
            selected[field] = previous.get(field, "")
    if selected["origin"] == previous.get("origin") and not selected["origin_city"]:
        selected["origin_city"] = previous.get("origin_city", "")
    if selected["dest"] == previous.get("dest") and not selected["dest_city"]:
        selected["dest_city"] = previous.get("dest_city", "")
    return selected


def poll_aircraft(state: State) -> None:
    api = FlightRadar24API()
    rate_limit_streak = 0
    while True:
        error = None
        try:
            previous = state.aircraft
            previous_registration = previous.get("registration") if previous else None
            previous_route = (previous.get("origin", ""), previous.get("dest", "")) if previous else None
            nearby = fetch_nearby(api, detailed_registration=previous_registration, detailed_route=previous_route)
            selected = asdict(nearby[0]) if nearby else None
            state.aircraft = carry_over_details(selected, previous)
            rate_limit_streak = 0
        except Exception as e:
            error = e
            rate_limit_streak = rate_limit_streak + 1 if is_rate_limited(error) else 0
            log.warning("aircraft poll failed: %s", error)
        delay = poll_delay(error, rate_limit_streak, AIRCRAFT_POLL_S)
        if is_rate_limited(error):
            log.warning("rate limited; retrying in %g seconds", delay)
        time.sleep(delay)


def poll_board(state: State) -> None:
    api = FlightRadar24API()
    rate_limit_streak = 0
    while True:
        error = None
        try:
            state.board = fetch_board(api)
            rate_limit_streak = 0
        except Exception as e:
            error = e
            rate_limit_streak = rate_limit_streak + 1 if is_rate_limited(error) else 0
            log.warning("board poll failed: %s", error)
        time.sleep(poll_delay(error, rate_limit_streak, BOARD_POLL_S))


def start(state: State) -> None:
    for target in (poll_aircraft, poll_board):
        threading.Thread(target=target, args=(state,), name=target.__name__, daemon=True).start()
