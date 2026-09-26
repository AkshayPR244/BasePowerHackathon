import datetime as dt

from app.contracts.models import RemoveCrewDay
from app.data import load_scenario
from app.recovery.service import recover


def test_options_live_and_lowest_includes_no_action():
    s = load_scenario("tiny_two_visit")
    out = recover(s, [RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5))])
    assert not out.stub
    assert {o.kind for o in out.options} == {"rebalance", "overtime", "temporary_capacity"}
    options = [out.no_action, *out.options]
    assert sum(o.lowest_modeled_cost for o in options) == 1
    for o in options:
        assert o.result.validation.valid
        assert not o.stub
        assert o.economics.net_impact_usd == round(
            sum(line.amount_usd for line in o.economics.lines), 2
        )
        if o.kind != "no_action":
            assert o.economics.advantage_vs_no_action_usd == round(
                out.no_action.economics.net_impact_usd - o.economics.net_impact_usd, 2
            )


def test_crew_load_has_before_and_after():
    s = load_scenario("tiny_two_visit")
    out = recover(s, [])
    assert out.no_action.crew_load
    assert all(c.before == c.after for c in out.no_action.crew_load)
