"""B-17: the value-aware objective uses the value table. Deadline-and-travel-only is revalued.

Lane A's table does not exist yet, so these tests inject a synthetic table.
"""

import pytest

from app.contracts.enums import Mode, ObjectivePolicy, StageStatus
from app.contracts.models import PlanRequest
from app.planning import solve
from tests.lane_b.conftest import make_scenario


def _earlier_is_better(scenario):
    start = scenario.config.planning_start
    return lambda sid, d: round(120.0 - 7.5 * (d - start).days + int(sid[1:]) % 5, 2)


@pytest.fixture
def scenario():
    return make_scenario(n_jobs=24, n_crews=3, n_days=8, seed=21, stock=40)


def test_value_aware_beats_deadline_travel_only(synthetic_values, scenario):
    synthetic_values[scenario.scenario_id] = _earlier_is_better(scenario)
    req = PlanRequest(scenario_id=scenario.scenario_id, revision=0, mode=Mode.recovery)
    aware = solve.plan(scenario, req)
    blind = solve.plan(
        scenario, req.model_copy(update={"objective_policy": ObjectivePolicy.deadline_travel_only})
    )
    assert aware.objective.value_distinguishes_choices
    # Same commitments first, then value. The value-aware plan earns at least as much.
    assert aware.objective.jobs_late == blind.objective.jobs_late
    assert aware.objective.operating_value_usd >= blind.objective.operating_value_usd
    skipped = next(m for m in blind.stages if m.name == "operating_value")
    assert skipped.status == StageStatus.skipped
    assert any(a.key == "revalued" for a in blind.assumptions)


def test_values_flow_into_assignments(synthetic_values, scenario):
    synthetic_values[scenario.scenario_id] = _earlier_is_better(scenario)
    r = solve.plan(
        scenario, PlanRequest(scenario_id=scenario.scenario_id, revision=0, mode=Mode.recovery)
    )
    assert all(a.value_usd > 0 for a in r.assignments)
    assert r.objective.operating_value_usd == pytest.approx(sum(a.value_usd for a in r.assignments))


def test_unresolved_values_are_labeled(monkeypatch, scenario):
    note = "3 site-date values had no solved valuation and count as $0."
    monkeypatch.setattr(solve, "site_values", lambda _s: ({}, note))
    r = solve.plan(
        scenario, PlanRequest(scenario_id=scenario.scenario_id, revision=0, mode=Mode.recovery)
    )
    note = next(a for a in r.assumptions if a.key == "unresolved_values")
    assert note.text.startswith("3 site-date values")


def test_equal_values_say_so(tiny):
    r = solve.plan(tiny, PlanRequest(scenario_id="tiny", revision=0))
    assert not r.objective.value_distinguishes_choices
    assert any(a.key == "equal_values" for a in r.assumptions)
