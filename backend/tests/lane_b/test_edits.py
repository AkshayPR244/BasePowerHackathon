"""B-11: disruptions and interventions apply as edits."""

import datetime as dt

from app.contracts.enums import InputIssueCode, Mode, PlanStatus
from app.contracts.hashing import scenario_hash
from app.contracts.models import (
    AddCrewDay,
    ChangeReadyDate,
    DelayInventory,
    ForceInclude,
    PlanRequest,
    RemoveCrewDay,
)
from app.planning.edits import apply_edits
from app.planning.solve import plan
from tests.lane_b.conftest import REMOVE_A_MON

MON, TUE, WED = dt.date(2018, 6, 4), dt.date(2018, 6, 5), dt.date(2018, 6, 6)


def test_remove_crew_day(tiny):
    e = apply_edits(tiny, [REMOVE_A_MON])
    assert ("A", MON) not in {(c.crew_id, c.date) for c in e.scenario.crew_days}
    assert not e.issues


def test_add_crew_day(tiny):
    add = AddCrewDay(
        crew_id="C", date=MON, available_min=480, skills=["install"], allowed_clusters=["N"]
    )
    e = apply_edits(tiny, [add])
    assert ("C", MON) in {(c.crew_id, c.date) for c in e.scenario.crew_days}
    dup = apply_edits(tiny, [add, add])
    assert dup.issues[0].code == InputIssueCode.DUPLICATE_ID


def test_delay_inventory_moves_units(tiny):
    e = apply_edits(
        tiny, [DelayInventory(configuration_id="B13", from_date=MON, to_date=TUE, quantity=1)]
    )
    by_day = {r.available_date: r.quantity for r in e.scenario.inventory}
    assert by_day == {MON: 2, TUE: 3}
    whole = apply_edits(tiny, [DelayInventory(configuration_id="B13", from_date=MON, to_date=WED)])
    assert {r.available_date: r.quantity for r in whole.scenario.inventory}[WED] == 3


def test_delay_inventory_changes_the_plan(tiny):
    edit = DelayInventory(configuration_id="B13", from_date=MON, to_date=TUE, quantity=1)
    r = plan(tiny, PlanRequest(scenario_id="tiny", revision=1, mode=Mode.recovery, edits=[edit]))
    assert sum(1 for a in r.assignments if a.date == MON) <= 2
    # One unit short on Monday: the recovery stays on time but spends more travel.
    assert r.objective.jobs_late == 0
    assert r.objective.travel_allowance_min > 165


def test_change_ready_date(tiny):
    edit = ChangeReadyDate(site_id="S-02", ready_date=WED)
    e = apply_edits(tiny, [edit])
    assert next(s for s in e.scenario.sites if s.site_id == "S-02").ready_date == WED
    r = plan(tiny, PlanRequest(scenario_id="tiny", revision=1, mode=Mode.recovery, edits=[edit]))
    s02 = next(a for a in r.assignments if a.site_id == "S-02")
    assert s02.date == WED and s02.days_late == 1


def test_force_include_is_tracked(tiny):
    assert apply_edits(tiny, [ForceInclude(site_id="N-02")]).forced == {"N-02"}


def test_bad_edits_are_invalid_input(tiny):
    for edit in [
        RemoveCrewDay(crew_id="Z", date=MON),
        ChangeReadyDate(site_id="nope", ready_date=MON),
        DelayInventory(configuration_id="B13", from_date=WED, to_date=TUE),
        DelayInventory(configuration_id="B13", from_date=MON, to_date=TUE, quantity=9),
    ]:
        r = plan(tiny, PlanRequest(scenario_id="tiny", revision=1, edits=[edit]))
        assert r.status == PlanStatus.invalid_input, edit


def test_hash_and_revision(tiny):
    r = plan(
        tiny, PlanRequest(scenario_id="tiny", revision=5, mode=Mode.recovery, edits=[REMOVE_A_MON])
    )
    assert r.revision == 5
    assert r.scenario_hash == scenario_hash(tiny, [REMOVE_A_MON])
    assert r.scenario_hash != tiny.scenario_hash
    assert r.edits == [REMOVE_A_MON]
