"""Two-visit homes: install first, battery day at least one business day later."""

import datetime as dt

import pytest

from app.contracts.models import PlanResult, ValidationReport
from app.data import load_scenario
from app.validate import validate_plan
from app.validate.enumerate_tiny import enumerate_tiny
from app.validate.plan import recompute_usage

MON, TUE, WED = dt.date(2018, 6, 4), dt.date(2018, 6, 5), dt.date(2018, 6, 6)


@pytest.fixture
def scenario():
    return load_scenario("tiny_two_visit")


@pytest.fixture
def plan(scenario):
    best = enumerate_tiny(scenario, "strict")
    assert best is not None and best.optimal_count == 1
    return PlanResult(
        plan_id="enumerated",
        scenario_id=scenario.scenario_id,
        scenario_hash=scenario.scenario_hash,
        revision=0,
        mode="strict",
        algorithm="cpsat",
        objective_policy="value_aware",
        edits=[],
        status="optimal",
        message="",
        stages=[],
        assignments=best.assignments,
        unscheduled=[],
        crew_days=recompute_usage(scenario, best.assignments),
        objective=best.objective,
        validation=ValidationReport(checked=False, valid=False, validator="none"),
        assumptions=[],
        solve_ms=0,
    )


def _codes(scenario, plan):
    return {i.code for i in validate_plan(scenario, plan).issues}


def _visit(plan, job_id):
    return next(a for a in plan.assignments if a.job_id == job_id)


def test_enumerated_plan_is_valid(scenario, plan):
    report = validate_plan(scenario, plan)
    assert report.valid, report.issues
    assert len(plan.assignments) == 6
    for s in scenario.sites:
        install, battery = _visit(plan, f"{s.site_id}-I"), _visit(plan, f"{s.site_id}-B")
        assert install.date < battery.date
        assert install.value_usd == 0 and battery.value_usd > 0


def test_precedence_violation(scenario, plan):
    battery = _visit(plan, "H1-B")
    battery.date = MON  # same day as the H1 install
    plan.crew_days = recompute_usage(scenario, plan.assignments)
    assert "PRECEDENCE" in _codes(scenario, plan)


def test_battery_day_without_install(scenario, plan):
    plan.assignments = [a for a in plan.assignments if a.job_id != "H3-I"]
    plan.crew_days = recompute_usage(scenario, plan.assignments)
    codes = _codes(scenario, plan)
    assert "PRECEDENCE" in codes and "MISSING_JOB" in codes


def test_crew_skill_must_match_visit_type(scenario, plan):
    _visit(plan, "H3-I").crew_id = "B"  # battery crew cannot do the electrical install
    plan.crew_days = recompute_usage(scenario, plan.assignments)
    assert "SKILL" in _codes(scenario, plan)


def test_value_only_on_battery_day(scenario, plan):
    _visit(plan, "H2-I").value_usd = 5.0
    assert "OBJECTIVE_MISMATCH" in _codes(scenario, plan)


def test_deadline_only_on_battery_day(scenario, plan):
    _visit(plan, "H2-I").days_late = 1
    _visit(plan, "H2-I").state = "late"
    assert "STATE_MISMATCH" in _codes(scenario, plan)


def test_enumerator_recovery_after_battery_crew_loses_tuesday(scenario):
    scenario.crew_days = [c for c in scenario.crew_days if (c.crew_id, c.date) != ("B", TUE)]
    assert enumerate_tiny(scenario, "strict") is None  # H1 is due Tuesday
    best = enumerate_tiny(scenario, "recovery")
    assert best is not None
    assert best.objective.jobs_late + best.objective.jobs_unscheduled >= 1
