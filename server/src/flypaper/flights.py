import logging
import math
import time
from dataclasses import dataclass

from FlightRadarAPI import FlightRadar24API

from .config import AIRCRAFT_POLL_S, LAT, LON, RADIUS_M
from .ratelimit import is_rate_limited, poll_delay
from .registration import registration_country

log = logging.getLogger(__name__)

R_EARTH = 6_371_000.0
FT = 0.3048


@dataclass
class Aircraft:
    callsign: str
    type: str
    registration: str
    airline: str
    airline_iata: str
    origin: str
    dest: str
    origin_city: str
    dest_city: str
    model_name: str
    year_built: str
    serial_number: str
    registration_country: str
    registration_country_iso2: str
    aircraft_age: str
    alt_m: float
    speed_kt: float
    dist_m: float
    bearing: float
    heading: float | None
    elevation: float


DETAIL_FIELDS = ("model_name", "year_built", "serial_number",
                 "registration_country", "registration_country_iso2", "aircraft_age")


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def aircraft_profile(api: FlightRadar24API, flight) -> dict[str, str]:
    details = api.get_flight_details(flight)
    flight.set_flight_details(details)
    raw_aircraft = details.get("aircraft")
    raw_aircraft = raw_aircraft if isinstance(raw_aircraft, dict) else {}
    airports = details.get("airport")
    airports = airports if isinstance(airports, dict) else {}

    def text(value) -> str:
        if value is None or value == "N/A":
            return ""
        return str(value).strip()

    def field(*names: str) -> str:
        for name in names:
            value = text(raw_aircraft.get(name))
            if value:
                return value
        return ""

    def airport_city(direction: str) -> str:
        airport = airports.get(direction)
        airport = airport if isinstance(airport, dict) else {}
        position = airport.get("position")
        position = position if isinstance(position, dict) else {}
        region = position.get("region")
        region = region if isinstance(region, dict) else {}
        city = region.get("city") or position.get("city") or airport.get("city")
        if isinstance(city, dict):
            city = city.get("name") or city.get("text")
        return text(city)

    country, country_iso2 = registration_country(text(getattr(flight, "registration", "")))
    return {
        "origin_city": airport_city("origin"),
        "dest_city": airport_city("destination"),
        "model_name": text(getattr(flight, "aircraft_model", "")),
        "year_built": field("yearBuilt", "year_built", "builtYear", "built_year"),
        "serial_number": field("serialNumber", "serial_number", "serial", "msn"),
        "registration_country": country,
        "registration_country_iso2": country_iso2,
        "aircraft_age": str(getattr(flight, "aircraft_age", "") or ""),
    }


def fetch_nearby(
    api: FlightRadar24API,
    detailed_registration: str | None = None,
    detailed_route: tuple[str, str] | None = None,
) -> list[Aircraft]:
    bounds = api.get_bounds_by_point(LAT, LON, RADIUS_M)
    result = []
    for f in api.get_flights(bounds=bounds):
        if f.on_ground:
            continue
        d = haversine(LAT, LON, f.latitude, f.longitude)
        alt = f.altitude * FT
        heading = f.heading
        if not isinstance(heading, (int, float)) or not math.isfinite(heading):
            heading = None
        aircraft = Aircraft(
            callsign=f.callsign or f.registration,
            type=f.aircraft_code,
            registration="" if f.registration in (None, "N/A") else f.registration,
            airline=f.airline_icao,
            airline_iata=f.airline_iata,
            origin=f.origin_airport_iata,
            dest=f.destination_airport_iata,
            origin_city="",
            dest_city="",
            model_name="",
            year_built="",
            serial_number="",
            registration_country="",
            registration_country_iso2="",
            aircraft_age="",
            alt_m=alt,
            speed_kt=f.ground_speed,
            dist_m=d,
            bearing=bearing(LAT, LON, f.latitude, f.longitude),
            heading=heading,
            elevation=math.degrees(math.atan2(alt, d)),
        )
        result.append((aircraft, f))

    result.sort(key=lambda item: item[0].dist_m)
    if result:
        selected, flight = result[0]
        route_changed = detailed_route is not None and (selected.origin, selected.dest) != detailed_route
        if selected.registration and (selected.registration != detailed_registration or route_changed):
            try:
                profile = aircraft_profile(api, flight)
            except Exception as error:
                log.warning("aircraft details unavailable for %s: %s", selected.registration, error)
            else:
                for name, value in profile.items():
                    setattr(selected, name, value)
    return [aircraft for aircraft, _ in result]


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    api = FlightRadar24API()
    rate_limit_streak = 0
    while True:
        error = None
        try:
            for a in fetch_nearby(api):
                print(f"{a.callsign:8} {a.type:5} {a.origin}->{a.dest} "
                      f"{a.alt_m:6.0f} m  {a.dist_m/1000:5.1f} km  "
                      f"az {a.bearing:3.0f}°  el {a.elevation:2.0f}°")
            rate_limit_streak = 0
        except Exception as e:
            error = e
            rate_limit_streak = rate_limit_streak + 1 if is_rate_limited(error) else 0
            print("poll failed:", error)
        delay = poll_delay(error, rate_limit_streak, AIRCRAFT_POLL_S)
        if error is not None:
            print(f"retrying in {delay:g} seconds")
        print("-" * 40)
        time.sleep(delay)


if __name__ == "__main__":
    main()
