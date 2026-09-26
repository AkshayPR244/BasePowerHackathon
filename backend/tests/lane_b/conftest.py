import datetime as dt
import random
from pathlib import Path

import pytest

from app.api.scenarios import load_scenario
from app.contracts.hashing import scenario_hash
from app.contracts.models import (
    BatteryConfig,
    Cluster,
    CounterfactualResult,
    CrewDay,
    InventoryReceipt,
    PlanDiff,
    PlannedInstall,
    PlanResult,
    ProvenanceNote,
    RemoveCrewDay,
    Scenario,
    ScenarioConfig,
    Site,
)

EXPECTED = Path(__file__).resolve().parents[3] / "data" / "demo" / "tiny" / "expected"
REMOVE_A_MON = RemoveCrewDay(crew_id="A", date=dt.date(2018, 6, 4))


@pytest.fixture(scope="session")
def tiny() -> Scenario:
    return load_scenario("tiny")


def expected(name: str):
    text = (EXPECTED / f"{name}.json").read_text("utf-8")
    if name.startswith("plan_"):
        return PlanResult.model_validate_json(text)
    if name.startswith("compare_"):
        return PlanDiff.model_validate_json(text)
    return CounterfactualResult.model_validate_json(text)


def slots(r: PlanResult) -> list[tuple]:
    return [(a.site_id, a.crew_id, a.date, a.state, a.days_late) for a in r.assignments]


def deferred(r: PlanResult) -> list[tuple]:
    return [(u.site_id, u.state, u.reasons) for u in r.unscheduled]


def make_scenario(
    n_jobs: int = 30,
    n_crews: int = 3,
    n_days: int = 10,
    n_clusters: int = 3,
    seed: int = 7,
    stock: int | None = None,
    workers: int = 8,
) -> Scenario:
    """Seeded synthetic scenario for tests. Not demo data."""
    rng = random.Random(seed)
    start = dt.date(2018, 6, 4)
    days = []
    d = start
    while len(days) < n_days:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    ks = [f"K{i}" for i in range(n_clusters)]
    clusters = [
        Cluster(
            cluster_id=k,
            name=k,
            travel_allowance_min=rng.choice([45, 60, 75]),
            outline=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)],
        )
        for k in ks
    ]
    crews = [chr(ord("A") + i) for i in range(n_crews)]
    crew_days = [
        CrewDay(
            crew_id=c,
            date=day,
            available_min=480,
            skills=["install"],
            allowed_clusters=sorted(rng.sample(ks, k=min(len(ks), 2))),
        )
        for c in crews
        for day in days
    ]
    sites = []
    for i in range(n_jobs):
        ready = rng.choice(days[: max(1, n_days // 2)])
        deadline = rng.choice([x for x in days if x >= ready])
        sites.append(
            Site(
                site_id=f"J{i:03d}",
                cluster_id=rng.choice(ks),
                program_id="P1",
                ready_date=ready,
                deadline=deadline,
                duration_min=rng.choice([120, 180, 240]),
                required_skill="install",
                configuration_id="B13",
                load_zone="LZ_HOUSTON",
                lon=0.5,
                lat=0.5,
            )
        )
    total = stock if stock is not None else n_jobs
    inventory = [
        InventoryReceipt(configuration_id="B13", available_date=days[0], quantity=total // 2),
        InventoryReceipt(
            configuration_id="B13", available_date=days[n_days // 3], quantity=total - total // 2
        ),
    ]
    config = ScenarioConfig(
        name=f"test-{n_jobs}",
        description="Seeded synthetic test scenario.",
        planning_start=days[0],
        planning_end=days[-1],
        evaluation_end=days[-1] + dt.timedelta(days=40),
        unscheduled_penalty_days=30,
        solve_time_limit_s=20,
        random_seed=0,
        num_workers=workers,
        batteries=[
            BatteryConfig(
                configuration_id="B13",
                capacity_kwh=13.5,
                reserve_kwh=1.35,
                charge_limit_kw=5,
                discharge_limit_kw=5,
                eta_charge=0.95,
                eta_discharge=0.95,
            )
        ],
        synthetic=True,
        provenance=[ProvenanceNote(input="all", kind="synthetic", source="tests/lane_b")],
    )
    s = Scenario(
        scenario_id=f"test-{n_jobs}",
        scenario_hash="",
        config=config,
        clusters=clusters,
        sites=sites,
        crew_days=crew_days,
        inventory=inventory,
        current_plan=[
            PlannedInstall(
                site_id=sites[0].site_id, crew_id="A", date=sites[0].ready_date, locked=False
            )
        ],
    )
    return s.model_copy(update={"scenario_hash": scenario_hash(s)})
