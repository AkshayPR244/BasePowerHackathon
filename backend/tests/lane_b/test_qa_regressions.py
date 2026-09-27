"""Regressions from the QA sweep of the planner, baselines, and explanation text."""

import datetime as dt

import pytest

from app.api.scenarios import load_scenario
from app.contracts.enums import Mode, PlanStatus
from app.contracts.models import ForceInclude, PlanRequest, RemoveCrewDay
from app.planning.solve import plan


def D(day: int) -> dt.date:
    return dt.date(2018, 6, day)


def run(scenario, edits=(), mode=Mode.recovery, **kw):
    req = PlanRequest(
        scenario_id=scenario.scenario_id, revision=0, mode=mode, edits=list(edits), **kw
    )
    return plan(scenario, req)


@pytest.mark.parametrize("mode", [Mode.strict, Mode.recovery])
def test_forcing_a_blocked_home_is_infeasible(tiny, mode):
    r = run(tiny, [ForceInclude(site_id="S-03")], mode)
    assert r.status == PlanStatus.infeasible
    assert r.message.startswith("S-03 cannot finish by its deadline.")
    assert "panel_upgrade" in r.message
    assert r.validation.valid


@pytest.fixture(scope="module")
def two_visit():
    return load_scenario("tiny_two_visit")


def unlocked(scenario):
    rows = [p.model_copy(update={"locked": False}) for p in scenario.current_plan]
    return scenario.model_copy(update={"current_plan": rows})


@pytest.mark.parametrize("days,unlock", [((4, 5), False), ((4, 6), False), ((4, 5, 6), True)])
def test_value_flag_matches_the_validator(two_visit, days, unlock):
    s = unlocked(two_visit) if unlock else two_visit
    r = run(s, [RemoveCrewDay(crew_id="B", date=D(d)) for d in days])
    assert r.validation.valid
    assert r.objective is not None
