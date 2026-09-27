"""Validator regressions from the QA sweep: each broken result must be caught, never crash."""

import datetime as dt

import pytest

from app.contracts.models import ChangeAppointment, PlanRequest, UnscheduledJob
from app.data import load_scenario
from app.planning.edits import apply_edits
from app.planning.solve import plan
from app.validate import validate_plan


@pytest.fixture(scope="module")
def good():
    s = load_scenario("tiny_two_visit")
    return s, plan(s, PlanRequest(scenario_id=s.scenario_id, revision=0))


def codes(s, r) -> set[str]:
    return {i.code for i in validate_plan(s, r).issues}


def with_unscheduled(r, **kw):
    extra = UnscheduledJob(state="unscheduled", reasons=[], detail="x", **kw)
    return r.model_copy(update={"unscheduled": [*r.unscheduled, extra]})


def with_assignment(r, job_id, **kw):
    rows = [a.model_copy(update=kw) if a.job_id == job_id else a for a in r.assignments]
    return r.model_copy(update={"assignments": rows})


def test_good_plan_is_valid(good):
    s, r = good
    assert codes(s, r) == set()


def test_unknown_site_in_unscheduled_list(good):
    s, r = good
    assert "UNKNOWN_SITE" in codes(s, with_unscheduled(r, site_id="GHOST"))


def test_unknown_visit_in_unscheduled_list(good):
    s, r = good
    assert "UNKNOWN_SITE" in codes(s, with_unscheduled(r, site_id="H1", job_id="H1-ZZZ"))


def test_duplicate_unscheduled_entries():
    s = load_scenario("tiny")
    r = plan(s, PlanRequest(scenario_id="tiny", revision=0))
    blocked = next(u for u in r.unscheduled if u.site_id == "S-03")
    twice = r.model_copy(update={"unscheduled": [*r.unscheduled, blocked]})
    assert "DUPLICATE_ASSIGNMENT" in codes(s, twice)


def test_wrong_visit_type_on_unscheduled_entry():
    s = load_scenario("tiny_two_visit")
    r = plan(s, PlanRequest(scenario_id=s.scenario_id, revision=0, mode="recovery"))
    r = r.model_copy(update={"assignments": [a for a in r.assignments if a.job_id != "H3-B"]})
    wrong = with_unscheduled(r, site_id="H3", job_id="H3-B", visit_type="install")
    assert "STATE_MISMATCH" in codes(s, wrong)


def test_assignment_with_unknown_site_is_reported_not_raised(good):
    s, r = good
    assert "UNKNOWN_SITE" in codes(s, with_assignment(r, "H1-B", site_id="BOGUS"))


def test_stale_scenario_hash(good):
    s, r = good
    assert "STATE_MISMATCH" in codes(s, r.model_copy(update={"scenario_hash": "deadbeef"}))


def test_missing_customer_counts_on_a_two_visit_plan(good):
    s, r = good
    blank = r.objective.model_copy(update={"visits_moved": None, "customers_to_reschedule": None})
    assert "OBJECTIVE_MISMATCH" in codes(s, r.model_copy(update={"objective": blank}))


def test_visit_outside_its_appointment_window(good):
    s, r = good
    window = ChangeAppointment(job_id="H1-B", available_from=dt.date(2018, 6, 6))
    edited = apply_edits(s, [window]).scenario
    claimed = r.model_copy(update={"edits": [window], "scenario_hash": edited.scenario_hash})
    assert "BEFORE_READY" in codes(edited, claimed)
