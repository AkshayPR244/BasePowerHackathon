import datetime as dt

import pytest

from app.contracts.models import ExtendCrewDay
from app.data import load_scenario
from app.recovery.economics import assumptions
from app.recovery.service import evaluate


def test_authorized_overtime_cost_and_penalty_off():
    s = load_scenario("tiny_two_visit")
    e = ExtendCrewDay(crew_id="B", date=dt.date(2018, 6, 5), extra_min=120)
    option = evaluate(s, [], [e])
    lines = {line.label: line for line in option.economics.lines}
    assert lines["Overtime"].amount_usd == 169.98
    assert lines["Deadline penalty"].amount_usd == 0
    assert option.economics.cost_per_deadline_recovered_usd is None
    assert all(line.basis for line in lines.values())
    assert "bls.gov" in assumptions()[0].source


@pytest.mark.parametrize(
    "overrides", [{"hourly_wage": -1}, {"nope": 3}, {"hourly_wage": float("nan")}]
)
def test_reject_bad_assumptions(overrides):
    with pytest.raises(ValueError):
        assumptions(overrides)


def test_overtime_cap_whole_minutes():
    with pytest.raises(ValueError, match="whole minutes"):
        assumptions({"max_overtime_min": 0.5})
