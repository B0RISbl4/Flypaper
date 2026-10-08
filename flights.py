import math
import time
from dataclasses import dataclass

from FlightRadarAPI import FlightRadar24API

LAT, LON = 59.938744, 30.314166   # твои координаты
RADIUS_M = 75_000
POLL_S = 10

R_EARTH = 6_371_000.0
FT = 0.3048


@dataclass
class Aircraft:
    callsign: str
    type: str
    airline: str
    origin: str
    dest: str
    alt_m: float
    speed_kt: float
    dist_m: float
    bearing: float
    elevation: float  # угол над горизонтом, градусы


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


def fetch_nearby(api: FlightRadar24API) -> list[Aircraft]:
    bounds = api.get_bounds_by_point(LAT, LON, RADIUS_M)
    result = []
    for f in api.get_flights(bounds=bounds):
        if f.on_ground:
            continue
        d = haversine(LAT, LON, f.latitude, f.longitude)
        alt = f.altitude * FT
        result.append(Aircraft(
            callsign=f.callsign or f.registration,
            type=f.aircraft_code,
            airline=f.airline_icao,
            origin=f.origin_airport_iata,
            dest=f.destination_airport_iata,
            alt_m=alt,
            speed_kt=f.ground_speed,
            dist_m=d,
            bearing=bearing(LAT, LON, f.latitude, f.longitude),
            elevation=math.degrees(math.atan2(alt, d)),
        ))
    # «над головой» = больший угол над горизонтом, а не просто меньшее расстояние
    return sorted(result, key=lambda a: -a.elevation)


if __name__ == "__main__":
    api = FlightRadar24API()
    while True:
        for a in fetch_nearby(api):
            print(f"{a.callsign:8} {a.type:5} {a.origin}->{a.dest} "
                  f"{a.alt_m:6.0f} m  {a.dist_m/1000:5.1f} km  "
                  f"az {a.bearing:3.0f}°  el {a.elevation:2.0f}°")
        print("-" * 40)
        time.sleep(POLL_S)