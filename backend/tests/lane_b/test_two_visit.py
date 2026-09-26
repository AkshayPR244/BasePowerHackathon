"""Two-visit homes through the planner, the baselines, and the exhaustive enumerator."""

import datetime as dt

import pytest

from app.api.scenarios import load_scenario
from app.contracts.enums import Algorithm, Mode, PlanStatus
from app.contracts.models import AddCrewDay, ForceInclude, PlanRequest, RemoveCrewDay
from app.contracts.visits import gap_ok
from app.planning.edits import apply_edits
from app.planning.solve import plan
from app.validate.enumerate_tiny import enumerate_tiny
from tests.lane_b.conftest import frozen

MON, TUE, WED = dt.date(2018, 6, 4), dt.date(2018, 6, 5), dt.date(2018, 6, 6)
B_OUT_TUE = RemoveCrewDay(crew_id="B", date=TUE)
I_OUT_TUE = RemoveCrewDay(crew_id="I", date=TUE)
CASES = [
    ("strict", Mode.strict, []),
    ("battery crew out Tue", Mode.recovery, [B_OUT_TUE]),
    ("install crew out Tue", Mode.recovery, [I_OUT_TUE]),
    ("force H3 with battery crew out", Mode.recovery, [B_OUT_TUE, ForceInclude(site_id="H3")]),
]


@pytest.fixture(scope="module")
def scenario():
    return load_scenario("tiny_two_visit")


def _slots(assignments):
    return sorted((a.job_id, a.crew_id, a.date) for a in assignments)


@pytest.mark.parametrize("name,mode,edits", CASES, ids=[c[0] for c in CASES])
def test_planner_matches_exhaustive_enumeration(scenario, name, mode, edits):
    edited = apply_edits(scenario, edits)
    oracle = enumerate_tiny(edited.scenario, mode, sorted(edited.forced))
    r = plan(
        scenario, PlanRequest(scenario_id=scenario.scenario_id, revision=1, mode=mode, edits=edits)
    )
    if oracle is None:
        assert r.status == PlanStatus.infeasible
        return
    assert r.status == PlanStatus.optimal and r.validation.valid
    fields = frozen(r.objective)
    fields.pop("crew_utilization")  # rounded to 4 places in results
    oracle_fields = frozen(oracle.objective)
    oracle_fields.pop("crew_utilization")
    assert fields == pytest.approx(oracle_fields)
    if oracle.optimal_count == 1:
        assert _slots(r.assignments) == _slots(oracle.assignments)


@pytest.mark.parametrize("alg", [Algorithm.baseline_edf, Algorithm.baseline_nearest_cluster])
@pytest.mark.parametrize("edits", [[], [B_OUT_TUE], [I_OUT_TUE]], ids=["none", "B out", "I out"])
def test_baselines_respect_precedence(scenario, alg, edits):
    r = plan(
        scenario,
        PlanRequest(
            scenario_id=scenario.scenario_id,
            revision=1,
            mode=Mode.recovery,
            algorithm=alg,
            edits=edits,
        ),
    )
    assert r.validation.checked and r.validation.valid, r.validation.issues
    at = {a.job_id: a for a in r.assignments}
    for s in scenario.sites:
        battery = at.get(f"{s.site_id}-B")
        if battery:
            install = at[f"{s.site_id}-I"]
            assert gap_ok(install.date, battery.date, 1, scenario.config.planning_start)
            assert install.crew_id == "I" and battery.crew_id == "B"


def test_value_and_deadline_sit_on_battery_day(scenario):
    r = plan(scenario, PlanRequest(scenario_id=scenario.scenario_id, revision=0))
    for a in r.assignments:
        if a.visit_type == "install":
            assert a.value_usd == 0 and a.days_late == 0
        else:
            assert a.value_usd > 0


def test_customer_metrics(scenario):
    r = plan(
        scenario,
        PlanRequest(
            scenario_id=scenario.scenario_id, revision=1, mode=Mode.recovery, edits=[B_OUT_TUE]
        ),
    )
    o = r.objective
    moved_homes = {
        p.site_id
        for p in scenario.current_plan
        if not p.locked
        and (p.crew_id, p.date)
        != next(
            ((a.crew_id, a.date) for a in r.assignments if a.job_id == p.job_id),
            None,
        )
    }
    assert o.visits_moved == o.changed_installs
    assert o.customers_to_reschedule == len(moved_homes)
    assert o.customers_to_reschedule <= o.visits_moved


def test_adding_a_battery_crew_day_never_hurts(scenario):
    base = [B_OUT_TUE]
    add = AddCrewDay(
        crew_id="B2", date=TUE, available_min=480, skills=["battery"], allowed_clusters=["N", "S"]
    )
    req = PlanRequest(scenario_id=scenario.scenario_id, revision=1, mode=Mode.recovery, edits=base)
    before = plan(scenario, req)
    after = plan(scenario, req.model_copy(update={"edits": [*base, add]}))
    key = lambda r: tuple(m.value for m in r.stages)  # noqa: E731
    assert before.status == after.status == PlanStatus.optimal
    assert key(after) <= key(before)
