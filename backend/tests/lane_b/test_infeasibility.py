"""Strict infeasibility from capacity or inventory names the jobs that conflict."""

import datetime as dt

from app.contracts.enums import PlanStatus, ReasonCode
from app.contracts.models import PlanRequest
from app.planning.infeasibility import conflicting_jobs
from app.planning.solve import plan

MON = dt.date(2018, 6, 4)


def _short_monday(tiny):
    inv = [
        x.model_copy(update={"quantity": 2}) if x.available_date == MON else x
        for x in tiny.inventory
    ]
    return tiny.model_copy(update={"inventory": inv})


def test_core_names_monday_jobs(tiny):
    # Only 2 units arrive Monday. N-02 is due Monday and S-02 is due Tuesday.
    core = conflicting_jobs(_short_monday(tiny), set(), 5.0)
    assert core is not None
    assert "N-02" in core


def test_strict_result_lists_the_conflict(tiny):
    r = plan(_short_monday(tiny), PlanRequest(scenario_id="tiny", revision=0))
    assert r.status == PlanStatus.infeasible
    capacity = [u for u in r.unscheduled if ReasonCode.CAPACITY in u.reasons]
    assert capacity
    assert "cannot all finish by their deadlines" in r.message


def test_feasible_scenario_has_no_core(tiny):
    assert conflicting_jobs(tiny, set(), 5.0) is None
