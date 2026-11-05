from flypaper.board import _number, _rows, _status, fetch_board


def flight(number="SU13", scheduled=1000, status_text="Scheduled", generic=None, iata="SU", city="Moscow", code="SVO"):
    return {"flight": {
        "identification": {"number": {"default": number}},
        "time": {"scheduled": {"departure": scheduled}, "real": {}, "estimated": {}},
        "status": {"text": status_text, "generic": {"status": {"text": generic}} if generic else {}},
        "airline": {"code": {"iata": iata}},
        "airport": {"destination": {"position": {"region": {"city": city}}, "code": {"iata": code}}},
    }}


def test_number_is_split_into_airline_and_digits():
    assert _number(flight("SU13")["flight"], "SU") == "SU 13"
    assert _number(flight("5N512")["flight"], "5N") == "5N 512"


def test_number_falls_back_to_airline_code():
    assert _number({}, "S7") == "S7"
    assert _number({}, None) == "—"


def test_status_prefers_generic_then_text():
    assert _status(flight(generic="delayed")["flight"]) == "delayed"
    assert _status(flight(status_text="Landed 12:30")["flight"]) == "landed"
    assert _status(flight(status_text="Cancelled")["flight"]) == "canceled"
    assert _status(flight(status_text="???")["flight"]) == "unknown"


def test_rows_are_sorted_and_skip_flights_without_time():
    rows = _rows([flight("SU2", 2000), flight("SU1", 1000), flight("SU3", None)], "departure")
    assert [r["flight"] for r in rows] == ["SU 1", "SU 2"]
    assert rows[0] == {"time": 1000, "event": None, "flight": "SU 1", "airline": "SU",
                       "city": "Moscow", "airport": "SVO", "status": "scheduled"}


def test_rows_drop_invalid_airline_codes():
    assert _rows([flight(iata="S7X")], "departure")[0]["airline"] is None


def test_fetch_board_reads_schedule_from_api():
    class FakeApi:
        def get_airport_details(self, code, flight_limit):
            return {"airport": {"pluginData": {"schedule": {
                "departures": {"data": [flight("SU13")]},
                "arrivals": {"data": []},
            }}}}

    board = fetch_board(FakeApi(), "LED")
    assert board["airport"] == "LED"
    assert [r["flight"] for r in board["departures"]] == ["SU 13"]
    assert board["arrivals"] == []
