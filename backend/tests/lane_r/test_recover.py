import datetime as dt

from app.contracts.models import RemoveCrewDay
from app.data import load_scenario
from app.recovery.service import recover


def test_options_live_and_lowest_includes_no_action():
    s = load_scenario("tiny_two_visit")
    out = recover(s, [RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5))])
    assert not out.stub
    assert {o.kind for o in out.options} == {"rebalance", "temporary_capacity"}
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


def test_inventory_delay_targets_battery_capacity_and_improves():
    from app.contracts.models import DelayInventory
    from app.recovery.options import rank
    from app.recovery.repair import repair
    from app.recovery.service import _candidates, _prepare

    s = load_scenario("standard")
    edits = [
        DelayInventory(
            configuration_id="B13", from_date=dt.date(2018, 6, 7), to_date=dt.date(2018, 6, 8)
        )
    ]
    base, original, _ = _prepare(s, None, None)
    _, candidates = _candidates(base, edits, 120, original, repair(base, edits))
    assert candidates
    assert all("battery" in e.skills for candidate in candidates for e in candidate)
    assert all(e.date >= dt.date(2018, 6, 8) for candidate in candidates for e in candidate)
    out = recover(s, edits)
    baseline = min([out.no_action, next(o for o in out.options if o.kind == "rebalance")], key=rank)
    temporary = [o for o in out.options if o.kind == "temporary_capacity"]
    assert temporary
    assert temporary[0].result.validation.valid
    assert rank(temporary[0])[:-2] < rank(baseline)[:-2]
    assert temporary[0].counts.deadlines_missed < out.no_action.counts.deadlines_missed


def test_no_disruption_does_not_offer_paid_capacity():
    out = recover(load_scenario("tiny_two_visit"), [])
    assert [o.kind for o in out.options] == ["rebalance"]


def test_non_improving_capacity_is_omitted(monkeypatch):
    from app.recovery import service
    from app.recovery.repair import repair

    s = load_scenario("tiny_two_visit").model_copy(deep=True)
    s.revision += 101
    edits = [RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5))]
    monkeypatch.setattr(
        service, "_solve", lambda base, edits, budget, hint=None: repair(base, edits[:1])
    )
    out = recover(s, edits)
    assert [o.kind for o in out.options] == ["rebalance"]
