"""Every generated number follows its stated rule."""

import datetime as dt

import pytest

from app.contracts.models import WeatherRule
from app.data import load as loader
from app.data.calendar import business_days, federal_holidays, is_business_day
from app.data.generate_standard import Spec, generate_standard
from app.data.travel import haversine_km, mean_point, travel_allowance_min
from app.data.weather import lost_reasons, parse_iem_csv


def test_federal_holidays_2018():
    h = federal_holidays(2018)
    assert dt.date(2018, 7, 4) in h
    assert dt.date(2018, 5, 28) in h  # Memorial Day
    assert dt.date(2018, 9, 3) in h  # Labor Day
    assert not is_business_day(dt.date(2018, 7, 4))
    assert business_days(dt.date(2018, 7, 2), 4) == [
        dt.date(2018, 7, 2),
        dt.date(2018, 7, 3),
        dt.date(2018, 7, 5),
        dt.date(2018, 7, 6),
    ]


def test_haversine_known_distance():
    # One degree of latitude is about 111.2 km.
    assert haversine_km((-95.0, 29.0), (-95.0, 30.0)) == pytest.approx(111.2, abs=0.2)


def test_travel_formula():
    depot, center = (-95.42, 29.75), (-95.40, 29.81)
    sites = [(-95.401, 29.811), (-95.399, 29.809)]
    radius = sum(haversine_km(center, s) for s in sites) / 2
    road = (2 * haversine_km(depot, center) + 2 * radius) * 1.417
    assert travel_allowance_min(depot, center, sites, 1.417, 40) == round(road / 40 * 60)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    root = tmp_path_factory.mktemp("gen")
    out = generate_standard(root / "standard", manifest_dir=root / "m")
    return root, out


def test_deadlines_follow_the_business_day_rule(generated, monkeypatch):
    root, _ = generated
    monkeypatch.setattr(loader, "DATA_ROOT", root)
    s = loader.load_scenario("standard")
    spec = Spec()
    days = sorted({c.date for c in s.crew_days})
    for site in s.sites:
        i = days.index(site.ready_date)
        assert i < spec.ready_window_days
        expected = days[min(i + spec.deadline_business_days, spec.window_days - 1)]
        assert site.deadline == expected, site.site_id


def test_travel_follows_geometry(generated, monkeypatch):
    root, _ = generated
    monkeypatch.setattr(loader, "DATA_ROOT", root)
    s = loader.load_scenario("standard")
    spec = Spec()
    depot = mean_point(list(spec.centers.values()))
    for c in s.clusters:
        pts = [(x.lon, x.lat) for x in s.sites if x.cluster_id == c.cluster_id]
        want = travel_allowance_min(
            depot, spec.centers[c.cluster_id], pts, spec.circuity, spec.speed_kmh
        )
        assert c.travel_allowance_min == want


def test_current_plan_and_inventory_are_feasible(generated, monkeypatch):
    root, _ = generated
    monkeypatch.setattr(loader, "DATA_ROOT", root)
    s = loader.load_scenario("standard")
    assert len(s.current_plan) == len(s.sites)
    by_day: dict = {}
    for p in s.current_plan:
        by_day[p.date] = by_day.get(p.date, 0) + 1
    for d in sorted({c.date for c in s.crew_days}):
        used = sum(n for day, n in by_day.items() if day <= d)
        got = sum(r.quantity for r in s.inventory if r.available_date <= d)
        assert used <= got
    assert sum(r.quantity for r in s.inventory) == len(s.sites)


def test_every_parameter_is_tagged_and_explained(generated, monkeypatch):
    root, _ = generated
    monkeypatch.setattr(loader, "DATA_ROOT", root)
    s = loader.load_scenario("standard")
    names = {p.name for p in s.config.parameters}
    for required in [
        "workday",
        "install_duration",
        "deadline_rule",
        "road_circuity",
        "average_speed",
        "battery_capacity",
        "battery_round_trip",
        "battery_one_way_efficiency",
        "weather_heavy_rain",
    ]:
        assert required in names
    for p in s.config.parameters:
        assert p.derivation
        if p.kind == "observed":
            assert p.source
    b = s.config.batteries[0]
    assert b.eta_charge == pytest.approx(0.89**0.5, abs=1e-6)
    assert b.eta_charge * b.eta_discharge == pytest.approx(0.89, abs=1e-5)


RAW = """station,valid,lon,lat,wxcodes,p01i
HOU,2018-06-25 07:53,-95.28,29.64,TSRA,0.40
HOU,2018-06-25 09:53,-95.28,29.64,-RA,0.02
HOU,2018-06-26 10:53,-95.28,29.64,null,0.31
HOU,2018-06-27 11:53,-95.28,29.64,VCTS,T
HOU,2018-06-28 12:53,-95.28,29.64,null,0.29
HOU,2018-06-29 17:53,-95.28,29.64,TSRA,1.00
"""


def test_weather_rule():
    rule = WeatherRule(heavy_rain_mm_per_h=7.6, work_start_hour=8, work_end_hour=17)
    lost = lost_reasons(parse_iem_csv(RAW), rule)
    assert lost == {
        dt.date(2018, 6, 26): ["heavy rain"],  # 0.31 in = 7.87 mm
        dt.date(2018, 6, 27): ["thunderstorm"],  # thunder in the vicinity counts
    }
    # 06-25 storm was before 08:00. 06-28 had 0.29 in = 7.37 mm. 06-29 was after 17:00.
    looser = rule.model_copy(update={"heavy_rain_mm_per_h": 7.0})
    assert dt.date(2018, 6, 28) in lost_reasons(parse_iem_csv(RAW), looser)
