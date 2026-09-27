"""Generate a rule-based synthetic two-visit benchmark, without network access.

Each home needs an install (the electrical disconnect visit), then a battery day (the battery
is placed) at least one business day later. Install crews do installs; battery crews do
battery days. Every number comes from a stated rule or a cited source, written into
scenario.yaml as `parameters` so the API can show them.

Run from backend: python -m app.data.generate_standard [--scenario storm_2018 --start ...]
"""

import argparse
import csv
import datetime as dt
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.contracts.calendar import business_days
from app.data.load import DATA_ROOT
from app.data.manifest import MANIFEST_ROOT, build_manifest, write_manifest
from app.data.travel import haversine_km, mean_point, travel_allowance_min

GENERATOR = "generator-v3"
POWERWALL3_DATASHEET = (
    "https://energylibrary.tesla.com/docs/Public/EnergyStorage/Powerwall/3/Datasheet/"
    "en-us/Powerwall-3-Datasheet.pdf"
)
BOSCOE_2012 = (
    "Boscoe, Henry, Zdeb (2012). A Nationwide Comparison of Driving Distance Versus "
    "Straight-Line Distance to Hospitals. The Professional Geographer 64(2):188-196."
)
AMS_HEAVY_RAIN = "https://glossary.ametsoc.org/wiki/Rain"
INSTALL, BATTERY = "install", "battery"


@dataclass(frozen=True)
class CrewSpec:
    crew_id: str
    skills: tuple[str, ...]
    allowed_clusters: tuple[str, ...]
    start_offset: int = 0
    available_min: int = 480


@dataclass
class Spec:
    """Generator inputs. Defaults are the committed `standard` scenario."""

    scenario_id: str = "standard"
    start: dt.date = dt.date(2018, 6, 4)
    window_days: int = 10
    overflow_days: int = 0
    evaluation_end: dt.date = dt.date(2018, 7, 29)
    n_homes: int = 45
    install_crews: tuple[str, ...] = ("IA", "IB")
    battery_crews: tuple[str, ...] = ("BA",)
    ready_window_days: int = 5
    deadline_business_days: int = 6
    battery_start_offset: int = 1
    plan_work_limit: float = 20.0  # CP-SAT deterministic time units
    install_durations_min: tuple[int, ...] = (90, 120, 150, 180)
    battery_durations_min: tuple[int, ...] = (60, 75, 90)
    min_gap_business_days: int = 1
    workday_min: int = 480
    delivery_every_days: int = 3
    circuity: float = 1.417
    speed_kmh: float = 40.0
    centers: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {"N": (-95.40, 29.81), "S": (-95.37, 29.68), "W": (-95.49, 29.75)}
    )
    site_spread_deg: float = 0.01
    capacity_kwh: float = 13.5
    reserve_fraction: float = 0.10
    charge_kw: float = 5.0
    discharge_kw: float = 11.5
    round_trip: float = 0.89
    heavy_rain_mm_per_h: float = 7.6
    work_start_hour: int = 8
    work_end_hour: int = 17
    weather_station: str = "HOU"
    unscheduled_penalty_days: int = 30
    crew_specs: tuple[CrewSpec, ...] = ()
    # Optional explicit incoming receipts: business-day offset, quantity.
    inventory_receipts: tuple[tuple[int, int], ...] = ()
    lock_policy: str = "first_day"
    qualification_lag_days: int = 0
    objective_policy: str = "value_aware"
    solve_time_limit_s: float = 15
    num_workers: int = 8


def _csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _geojson(path: Path, features: list[dict]) -> None:
    body = json.dumps({"type": "FeatureCollection", "features": features}, indent=2, sort_keys=True)
    path.write_text(body + "\n", encoding="utf-8", newline="\n")


def _param(name, value, unit, kind, derivation, source=None) -> dict:
    out = {"name": name, "value": value, "unit": unit, "kind": kind, "derivation": derivation}
    if source:
        out["source"] = source
    return out


def _optimizer_plan(output: Path, spec: Spec) -> dict[str, tuple[str, dt.date]]:
    """Strict plan for the undisrupted scenario: every visit placed, every deadline met.

    One worker and a deterministic work limit make the result identical on every machine.
    """
    from ortools.sat.python import cp_model

    from app.contracts.enums import Mode
    from app.data import load as loader
    from app.planning.model import build, eligibility

    root = loader.DATA_ROOT
    try:
        loader.DATA_ROOT = output.parent
        scenario = loader.load_scenario(output.name)
    finally:
        loader.DATA_ROOT = root
    elig = eligibility(scenario, Mode.strict, set())
    pm = build(scenario, elig, Mode.strict, set(), {})
    pm.model.minimize(pm.exprs["travel"])
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_deterministic_time = spec.plan_work_limit
    if solver.solve(pm.model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError(
            f"No on-time plan found for {spec.n_homes} homes: lower n_homes or relax deadlines"
        )
    return {jid: (crew, d) for (jid, crew, d), v in pm.x.items() if solver.value(v)}


def _carryover_provenance(output: Path) -> list[dict]:
    """Keep provenance that preparation steps added for prices and loads."""
    path = output / "scenario.yaml"
    if not path.exists():
        return []
    old = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    keep = ("prices.parquet", "loads.parquet", "sites.csv:profile_id")
    return [p for p in old.get("provenance", []) if p["input"] in keep]


def _parameters(spec: Spec, depot, travel, eta: float, reserve: float) -> list[dict]:
    ratio = f"{len(spec.install_crews)}:{len(spec.battery_crews)}"
    return [
        _param("workday", spec.workday_min, "min", "assumed", "One 8-hour crew day"),
        _param(
            "install_duration",
            "/".join(map(str, spec.install_durations_min)),
            "min",
            "assumed",
            "Electrical disconnect visit of 1.5 to 3 hours, varied per home (seeded)",
        ),
        _param(
            "battery_day_duration",
            "/".join(map(str, spec.battery_durations_min)),
            "min",
            "assumed",
            "About 75 min to place one battery, so a battery crew fits 5 to 6 a day with travel",
        ),
        _param(
            "min_gap_install_to_battery_day",
            spec.min_gap_business_days,
            "business days",
            "assumed",
            "The battery day comes at least one business day after the install",
        ),
        _param(
            "crew_mix",
            ratio,
            "install:battery crews",
            "assumed",
            "Installs take longer per home, so two install crews feed one battery crew",
        ),
        _param(
            "battery_crew_start",
            spec.battery_start_offset,
            "business days",
            "assumed",
            "Battery crews start after the first window day because no install is finished yet",
        ),
        _param(
            "ready_dates",
            spec.ready_window_days,
            "business days",
            "synthetic",
            "Each home becomes ready on a uniform random day in the first N business days",
        ),
        _param(
            "deadline_rule",
            spec.deadline_business_days,
            "business days",
            "assumed",
            "Battery-day deadline = ready date + N business days, capped at the last window day",
        ),
        _param(
            "business_days",
            "weekdays",
            "",
            "assumed",
            "Crews work weekdays that are not US federal holidays",
        ),
        _param(
            "overflow_days",
            spec.overflow_days,
            "business days",
            "assumed",
            "Crew days after the window where late visits can still land",
        ),
        _param(
            "current_plan_rule",
            "EDF",
            "",
            "derived",
            "Current plan = this tool's strict plan for the undisrupted scenario, day 0 locked. "
            "Deliveries are sized to it",
        ),
        _param(
            "depot",
            f"{depot[0]:.4f},{depot[1]:.4f}",
            "lon,lat",
            "assumed",
            "Crew yard at the mean of the cluster centers",
        ),
        _param(
            "road_circuity",
            spec.circuity,
            "ratio",
            "assumed",
            "US nationwide driving distance / straight-line distance",
            BOSCOE_2012,
        ),
        _param("average_speed", spec.speed_kmh, "km/h", "assumed", "Urban driving including stops"),
        *[
            _param(
                f"travel_{k}",
                v,
                "min",
                "derived",
                "(2 x depot-to-center + 2 x mean site radius) x circuity / speed, "
                f"depot distance {haversine_km(depot, spec.centers[k]):.2f} km",
            )
            for k, v in travel.items()
        ],
        _param(
            "deliveries",
            spec.delivery_every_days,
            "business days",
            "assumed",
            "A delivery every N business days, sized to the planned battery days until the next",
        ),
        _param(
            "battery_capacity",
            spec.capacity_kwh,
            "kWh",
            "observed",
            "Powerwall 3 nominal battery energy (13.5 kWh AC)",
            POWERWALL3_DATASHEET,
        ),
        _param(
            "battery_charge_limit",
            spec.charge_kw,
            "kW",
            "observed",
            "Powerwall 3 maximum continuous charge power",
            POWERWALL3_DATASHEET,
        ),
        _param(
            "battery_discharge_limit",
            spec.discharge_kw,
            "kW",
            "observed",
            "Powerwall 3 nominal output power, highest rating",
            POWERWALL3_DATASHEET,
        ),
        _param(
            "battery_round_trip",
            spec.round_trip,
            "fraction",
            "observed",
            "Powerwall 3 solar-to-battery-to-home/grid efficiency (typical solar shifting). "
            "The datasheet gives no grid-charge figure",
            POWERWALL3_DATASHEET,
        ),
        _param(
            "battery_one_way_efficiency",
            eta,
            "fraction",
            "derived",
            "Charge and discharge efficiency = sqrt(round trip)",
        ),
        _param(
            "battery_reserve",
            reserve,
            "kWh",
            "assumed",
            f"{spec.reserve_fraction:.0%} of capacity held back; start and end at reserve",
        ),
        _param(
            "value_start",
            "after battery day",
            "",
            "assumed",
            "Energy value starts after the battery day; the install alone earns nothing",
        ),
        _param(
            "unscheduled_penalty",
            spec.unscheduled_penalty_days,
            "days",
            "assumed",
            "Delay charged for a home left unscheduled; larger than any lateness in the horizon",
        ),
        _param(
            "weather_thunder",
            "any TS in METAR",
            "",
            "assumed",
            "Electrical work stops for lightning. A thunderstorm report in working hours "
            "loses the crew-day",
        ),
        _param(
            "weather_battery_day",
            "same rule",
            "",
            "assumed",
            "Battery days stop for the same weather as installs; their sensitivity is untested",
        ),
        _param(
            "weather_heavy_rain",
            spec.heavy_rain_mm_per_h,
            "mm/h",
            "assumed",
            "AMS heavy-rain threshold (0.30 in/h) in any working hour loses the crew-day",
            AMS_HEAVY_RAIN,
        ),
        _param(
            "weather_working_hours",
            f"{spec.work_start_hour:02d}-{spec.work_end_hour:02d}",
            "local hour",
            "assumed",
            "Hours in which weather can stop work",
        ),
        _param(
            "weather_station",
            spec.weather_station,
            "",
            "assumed",
            "Nearest ASOS station to the study area (Houston Hobby)",
        ),
    ]


def generate_standard(
    output: Path | None = None, seed: int = 42, manifest_dir: Path | None = None, spec=None
) -> Path:
    spec = spec or Spec()
    output = DATA_ROOT / spec.scenario_id if output is None else Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    all_days = business_days(spec.start, spec.window_days + spec.overflow_days)
    window = all_days[: spec.window_days]
    index = {d: i for i, d in enumerate(all_days)}

    points, homes = {}, []
    names = list(spec.centers)
    for i in range(spec.n_homes):
        k = names[i % len(names)]
        ready = window[rng.randrange(spec.ready_window_days)]
        deadline = all_days[min(index[ready] + spec.deadline_business_days, len(window) - 1)]
        sid = f"{k}-{i // len(names) + 1:02d}"
        lon, lat = spec.centers[k]
        points[sid] = (
            round(lon + rng.uniform(-spec.site_spread_deg, spec.site_spread_deg), 6),
            round(lat + rng.uniform(-spec.site_spread_deg, spec.site_spread_deg), 6),
        )
        homes.append(
            dict(
                site_id=sid,
                cluster_id=k,
                ready_date=ready,
                deadline=deadline,
                install_min=rng.choice(spec.install_durations_min),
                battery_min=rng.choice(spec.battery_durations_min),
            )
        )

    depot = mean_point(list(spec.centers.values()))
    travel = {
        k: travel_allowance_min(
            depot,
            center,
            [points[h["site_id"]] for h in homes if h["cluster_id"] == k],
            spec.circuity,
            spec.speed_kmh,
        )
        for k, center in spec.centers.items()
    }
    eta = round(math.sqrt(spec.round_trip), 6)
    reserve = round(spec.capacity_kwh * spec.reserve_fraction, 4)
    provenance = [
        {
            "input": "all operational and geometry files",
            "kind": "synthetic",
            "source": f"Rule-based generator v3, seed {seed}. Not customers.",
        },
        *_carryover_provenance(output),
    ]
    crews = [*spec.install_crews, *spec.battery_crews]
    extra = f" plus {spec.overflow_days} overflow days" if spec.overflow_days else ""
    cfg = {
        "name": f"{spec.scenario_id} synthetic two-visit recovery benchmark",
        "description": (
            f"{spec.n_homes} synthetic homes, each needing an install then a battery day. "
            f"{len(spec.centers)} clusters, {len(spec.install_crews)} install crews, "
            f"{len(spec.battery_crews)} battery crew(s), {spec.window_days} business days{extra}. "
            "Every number comes from a stated rule or source."
        ),
        "timezone": "America/Chicago",
        "planning_start": all_days[0],
        "planning_end": all_days[-1],
        "evaluation_end": spec.evaluation_end,
        "qualification_lag_days": spec.qualification_lag_days,
        "unscheduled_penalty_days": spec.unscheduled_penalty_days,
        "objective_policy": spec.objective_policy,
        "solve_time_limit_s": spec.solve_time_limit_s,
        "random_seed": seed,
        "num_workers": spec.num_workers,
        "synthetic": True,
        "min_gap_business_days": spec.min_gap_business_days,
        "travel_allowance_min": travel,
        "batteries": [
            {
                "configuration_id": "B13",
                "capacity_kwh": spec.capacity_kwh,
                "reserve_kwh": reserve,
                "charge_limit_kw": spec.charge_kw,
                "discharge_limit_kw": spec.discharge_kw,
                "eta_charge": eta,
                "eta_discharge": eta,
            }
        ],
        "weather_rule": {
            "thunder": True,
            "heavy_rain_mm_per_h": spec.heavy_rain_mm_per_h,
            "work_start_hour": spec.work_start_hour,
            "work_end_hour": spec.work_end_hour,
        },
        "parameters": _parameters(spec, depot, travel, eta, reserve),
        "provenance": provenance,
    }
    profile = ""
    has_loads = (output / "loads.parquet").exists()
    if has_loads:
        from app.data.prepare_resstock import PROFILE_ID

        profile = PROFILE_ID
    (output / "scenario.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8", newline="\n"
    )

    clusters = []
    for k, (lon, lat) in spec.centers.items():
        d = 0.015
        corners = [(-d, -d), (d, -d), (d, d), (-d, d), (-d, -d)]
        ring = [[round(lon + x, 6), round(lat + y, 6)] for x, y in corners]
        clusters.append(
            {
                "type": "Feature",
                "properties": {"cluster_id": k, "name": k},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    _geojson(output / "clusters.geojson", clusters)
    _csv(
        output / "sites.csv",
        [
            dict(
                site_id=h["site_id"],
                cluster_id=h["cluster_id"],
                program_id="P1",
                ready_date=h["ready_date"],
                deadline=h["deadline"],
                duration_min=h["battery_min"],
                required_skill=BATTERY,
                configuration_id="B13",
                load_zone="LZ_HOUSTON",
                profile_id=profile,
            )
            for h in homes
        ],
    )
    _csv(
        output / "visits.csv",
        [
            row
            for h in homes
            for row in (
                dict(
                    job_id=f"{h['site_id']}-I",
                    site_id=h["site_id"],
                    visit_type="install",
                    duration_min=h["install_min"],
                    required_skill=INSTALL,
                ),
                dict(
                    job_id=f"{h['site_id']}-B",
                    site_id=h["site_id"],
                    visit_type="battery_day",
                    duration_min=h["battery_min"],
                    required_skill=BATTERY,
                ),
            )
        ],
    )
    _geojson(
        output / "sites.geojson",
        [
            {
                "type": "Feature",
                "properties": {"site_id": h["site_id"]},
                "geometry": {"type": "Point", "coordinates": list(points[h["site_id"]])},
            }
            for h in homes
        ],
    )
    battery_days = all_days[spec.battery_start_offset :]
    crew_rows = [
        dict(
            crew_id=c,
            date=d,
            available_min=spec.workday_min,
            skills=INSTALL if c in spec.install_crews else BATTERY,
            allowed_clusters=";".join(spec.centers),
        )
        for c in crews
        for d in (all_days if c in spec.install_crews else battery_days)
    ]
    if spec.crew_specs:
        crew_rows = [
            dict(
                crew_id=c.crew_id,
                date=d,
                available_min=c.available_min,
                skills=";".join(c.skills),
                allowed_clusters=";".join(c.allowed_clusters),
            )
            for c in spec.crew_specs
            for d in all_days[c.start_offset :]
        ]
    _csv(output / "crew_days.csv", crew_rows)
    header = "site_id,job_id,crew_id,date,locked\n"
    (output / "current_plan.csv").write_text(header, encoding="utf-8", newline="\n")
    _csv(
        output / "inventory.csv",
        [dict(configuration_id="B13", available_date=window[0], quantity=len(homes))],
    )
    if spec.inventory_receipts:
        _csv(
            output / "inventory.csv",
            [
                dict(configuration_id="B13", available_date=all_days[i], quantity=q)
                for i, q in spec.inventory_receipts
            ],
        )
    placed = _optimizer_plan(output, spec)

    deliveries = window[:: spec.delivery_every_days]
    qty = dict.fromkeys(deliveries, 0)
    for jid, (_, day) in placed.items():
        if jid.endswith("-B"):
            qty[max(d for d in deliveries if d <= day)] += 1
    rows = [
        dict(
            site_id=jid.rsplit("-", 1)[0],
            job_id=jid,
            crew_id=crew,
            date=day,
            locked="true"
            if spec.lock_policy == "all" or (spec.lock_policy == "first_day" and day == window[0])
            else "false",
        )
        for jid, (crew, day) in placed.items()
    ]
    rows.sort(key=lambda r: (r["date"], r["crew_id"], r["job_id"]))
    _csv(output / "current_plan.csv", rows)
    _csv(
        output / "inventory.csv",
        [dict(configuration_id="B13", available_date=d, quantity=q) for d, q in qty.items() if q],
    )

    if spec.inventory_receipts:
        _csv(
            output / "inventory.csv",
            [
                dict(configuration_id="B13", available_date=all_days[i], quantity=q)
                for i, q in spec.inventory_receipts
            ],
        )
        qty = dict(spec.inventory_receipts)

    counts = {
        "scenario.yaml": 1,
        "sites.csv": len(homes),
        "visits.csv": 2 * len(homes),
        "sites.geojson": len(homes),
        "clusters.geojson": len(clusters),
        "crew_days.csv": len(crew_rows),
        "inventory.csv": sum(1 for q in qty.values() if q),
        "current_plan.csv": len(rows),
    }
    for name, count in counts.items():
        path = output / name
        if path.suffix == ".csv":
            fields = {k: "synthetic" for k in path.read_text().splitlines()[0].split(",")}
            if has_loads and name == "sites.csv":
                fields["profile_id"] = "modeled"
        else:
            fields = {"geometry" if path.suffix == ".geojson" else "config": "synthetic"}
        write_manifest(
            build_manifest(
                path,
                dataset_id=output.name + "_" + name.replace(".", "_"),
                kind="synthetic",
                row_count=count,
                fields=fields,
                release=f"{GENERATOR}-seed-{seed}",
                covered_start=all_days[0],
                covered_end=all_days[-1],
                transformation="Rule-based synthetic inputs; no real customers.",
            ),
            manifest_dir,
        )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", default="standard")
    parser.add_argument("--start", type=dt.date.fromisoformat)
    parser.add_argument("--overflow-days", type=int, default=0)
    parser.add_argument("--homes", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec = Spec(scenario_id=args.scenario, overflow_days=args.overflow_days)
    if args.start:
        spec.start = args.start
    if args.homes:
        spec.n_homes = args.homes
    print(generate_standard(args.output, args.seed, MANIFEST_ROOT, spec))
