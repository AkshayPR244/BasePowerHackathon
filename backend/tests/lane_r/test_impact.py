import datetime as dt

from app.contracts.models import RemoveCrewDay
from app.data import load_scenario
from app.recovery.service import recover


def test_install_loss_traces_dependent_battery_days():
    s = load_scenario("tiny_two_visit")
    out = recover(s, [RemoveCrewDay(crew_id="I", date=dt.date(2018, 6, 5))], interactive=True)
    assert out.impact.lost_capacity_min == 480
    assert out.impact.affected_job_ids
    assert any(step.job_ids for step in out.impact.cascade if step.kind == "pushed")
    assert all(j.endswith("-I") for j in out.impact.affected_job_ids)
