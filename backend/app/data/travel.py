"""Travel allowance per active crew-day, derived from geometry.

allowance = (2 * depot-to-cluster-center + 2 * mean site distance from the center)
            * circuity / speed
The first term is the round trip from the yard. The second term covers moving between
sites inside the cluster.
"""

import math

EARTH_RADIUS_KM = 6371.0088
Point = tuple[float, float]  # (lon, lat)


def haversine_km(a: Point, b: Point) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def mean_point(points: list[Point]) -> Point:
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def travel_allowance_min(
    depot: Point, center: Point, sites: list[Point], circuity: float, speed_kmh: float
) -> int:
    radius = sum(haversine_km(center, s) for s in sites) / len(sites) if sites else 0.0
    road_km = (2 * haversine_km(depot, center) + 2 * radius) * circuity
    return round(road_km / speed_kmh * 60)
