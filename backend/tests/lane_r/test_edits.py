import datetime as dt

from app.contracts.models import (
    AddCrewDay,
    ChangeAppointment,
    ExtendCrewDay,
    MoveVisit,
    PinVisit,
    PlanRequest,
    ReduceCrewDay,
)
from app.data import load_scenario
from app.planning.edits import apply_edits
from app.planning.solve import plan

MON, TUE, WED = (dt.date(2018, 6, d) for d in (4, 5, 6))


def test_reduce_cannot_increase_or_reference_missing_day():
    s = load_scenario("tiny")
    assert apply_edits(s, [ReduceCrewDay(crew_id="A", date=MON, available_min=600)]).issues
    assert apply_edits(s, [ReduceCrewDay(crew_id="Z", date=MON, available_min=0)]).issues
    e = apply_edits(s, [ReduceCrewDay(crew_id="A", date=MON, available_min=0)])
    assert not e.issues
    assert (
        next(c for c in e.scenario.crew_days if c.crew_id == "A" and c.date == MON).available_min
        == 0
    )


def test_extend_overtime_cumulative_cap():
    s = load_scenario("tiny")
    e = ExtendCrewDay(crew_id="A", date=MON, extra_min=120)
    assert not apply_edits(s, [e]).issues
    assert apply_edits(s, [e, e]).issues


def test_appointment_reschedule_specific_visit():
    s = load_scenario("tiny_two_visit")
    e = ChangeAppointment(job_id="H3-B", available_from=WED, available_to=WED)
    r = plan(s, PlanRequest(scenario_id=s.scenario_id, revision=1, mode="recovery", edits=[e]))
    assert r.validation.valid
    a = next(a for a in r.assignments if a.job_id == "H3-B")
    assert a.date == WED
    assert next(a for a in r.assignments if a.job_id == "H3-I").date < WED


def test_appointment_impossible_window_is_unscheduled_not_crash():
    s = load_scenario("tiny")
    e = ChangeAppointment(job_id="S-02", available_from=dt.date(2018, 6, 9))
    r = plan(s, PlanRequest(scenario_id=s.scenario_id, revision=1, mode="recovery", edits=[e]))
    assert r.validation.valid
    assert not any(a.site_id == "S-02" for a in r.assignments)


def test_pin_current_slot_and_move_lock():
    s = load_scenario("tiny")
    p = apply_edits(s, [PinVisit(job_id="S-01")])
    assert next(p for p in p.scenario.current_plan if p.site_id == "S-01").locked
    r = plan(
        s,
        PlanRequest(
            scenario_id="tiny",
            revision=1,
            mode="recovery",
            edits=[MoveVisit(job_id="S-01", crew_id="B", date=TUE)],
        ),
    )
    assert r.validation.valid
    assert next(a for a in r.assignments if a.site_id == "S-01").date == TUE
    assert apply_edits(s, [MoveVisit(job_id="N-01", crew_id="A", date=MON)]).issues


def test_add_outside_horizon_is_invalid():
    s = load_scenario("tiny")
    e = AddCrewDay(
        crew_id="EXTRA",
        date=dt.date(2018, 6, 7),
        available_min=480,
        skills=["panel_upgrade"],
        allowed_clusters=["S"],
    )
    r = plan(s, PlanRequest(scenario_id="tiny", revision=1, edits=[e]))
    assert r.status == "invalid_input"


def test_reduce_does_not_reset_authorized_overtime_cap():
    s = load_scenario("tiny")
    edits = [
        ReduceCrewDay(crew_id="A", date=MON, available_min=100),
        ExtendCrewDay(crew_id="A", date=MON, extra_min=240),
    ]
    assert apply_edits(s, edits).issues
