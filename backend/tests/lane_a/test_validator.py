import datetime as dt

import pytest

from app.contracts.enums import ViolationCode
from app.validate import validate_plan
from tests.lane_a.conftest import edited_scenario, expected_plans


@pytest.mark.parametrize("name,plan", list(expected_plans()))
def test_expected(name, plan):
    report = validate_plan(edited_scenario(plan), plan)
    assert report.checked and report.valid, report.issues
    assert not report.issues


@pytest.mark.parametrize("code", list(ViolationCode))
def test_broken_per_violation(code, scenario, plan):
    if code == "UNKNOWN_SITE":
        plan.assignments[1].site_id = "ghost"
    elif code == "DUPLICATE_ASSIGNMENT":
        plan.assignments.append(plan.assignments[1].model_copy())
    elif code == "NO_CREW_DAY":
        plan.assignments[1].crew_id = "ghost"
    elif code == "BEFORE_READY":
        scenario.sites[1].ready_date = dt.date(2018, 6, 6)
    elif code == "AFTER_DEADLINE":
        plan.assignments[1].date = dt.date(2018, 6, 6)
    elif code == "MISSING_JOB":
        plan.assignments.pop(1)
    elif code == "SKILL":
        scenario.sites[1].required_skill = "missing"
    elif code == "CLUSTER_NOT_ALLOWED":
        plan.assignments[1].crew_id = "B"
    elif code == "MULTIPLE_CLUSTERS":
        plan.assignments[3].crew_id = "A"
    elif code == "CAPACITY":
        scenario.crew_days[0].available_min = 200
    elif code == "INVENTORY":
        scenario.inventory[0].quantity = 0
    elif code == "LOCK_BROKEN":
        plan.assignments[0].date = dt.date(2018, 6, 6)
    elif code == "STATE_MISMATCH":
        plan.assignments[1].days_late = 3
    elif code == "OBJECTIVE_MISMATCH":
        plan.objective.jobs_on_time = 500
    report = validate_plan(scenario, plan)
    assert report.checked and not report.valid
    assert code in {i.code for i in report.issues}


def test_objective_does_not_trust_assignment_values(scenario, plan):
    plan.assignments[0].value_usd = 1234
    plan.objective.operating_value_usd = 1234
    assert "OBJECTIVE_MISMATCH" in {i.code for i in validate_plan(scenario, plan).issues}


def test_objective_recomputes_crew_usage(scenario, plan):
    plan.crew_days[0].travel_min = 0
    assert "OBJECTIVE_MISMATCH" in {i.code for i in validate_plan(scenario, plan).issues}


def test_fake_blocked_cannot_hide_required_job(scenario, plan):
    item = plan.assignments.pop(1)
    plan.unscheduled.append(plan.unscheduled[0].model_copy(update={"site_id": item.site_id}))
    codes = {i.code for i in validate_plan(scenario, plan).issues}
    assert {"MISSING_JOB", "STATE_MISMATCH"} <= codes


def test_no_incumbent_does_not_certify_infeasibility(scenario, plan):
    plan.status = "infeasible"
    report = validate_plan(scenario, plan)
    assert not report.valid
    assert "no-incumbent-shape" in report.validator
