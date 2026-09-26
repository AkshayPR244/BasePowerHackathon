"""B-18: recovery keeps the current plan where it can."""

from app.contracts.enums import Mode
from app.contracts.models import PlannedInstall, PlanRequest
from app.planning.solve import plan


def test_current_plan_rows_stay_put(tiny):
    r = plan(tiny, PlanRequest(scenario_id="tiny", revision=0, mode=Mode.recovery))
    s01 = next(a for a in r.assignments if a.site_id == "S-01")
    assert (s01.crew_id, str(s01.date)) == ("B", "2018-06-04")
    assert r.objective.changed_installs == 0


def test_changed_installs_counts_moves(tiny):
    # Plan S-02 on Wednesday. Its deadline is Tuesday, so recovery must move it.
    row = PlannedInstall(site_id="S-02", crew_id="B", date="2018-06-06", locked=False)
    s = tiny.model_copy(update={"current_plan": [*tiny.current_plan, row]})
    r = plan(s, PlanRequest(scenario_id="tiny", revision=0, mode=Mode.recovery))
    s02 = next(a for a in r.assignments if a.site_id == "S-02")
    assert str(s02.date) != "2018-06-06"
    assert r.objective.changed_installs == 1
