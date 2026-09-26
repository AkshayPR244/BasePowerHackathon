import datetime as dt

from app.contracts.models import RemoveCrewDay
from app.data import load_scenario
from app.recovery.repair import current_result, repair


def test_current_is_not_optimized():
    s = load_scenario("tiny")
    r = current_result(s)
    assert len(r.assignments) == len(s.current_plan)
    assert r.validation.valid


def test_no_action_keeps_other_bookings_and_original_crews():
    s = load_scenario("tiny_two_visit")
    before = current_result(s)
    edit = RemoveCrewDay(crew_id="I", date=dt.date(2018, 6, 5))
    r = repair(s, [edit])
    assert r.validation.valid
    old = {a.job_id: a for a in before.assignments}
    for a in r.assignments:
        assert a.crew_id == old[a.job_id].crew_id
        assert a.date >= old[a.job_id].date
    assert r.objective.visits_moved > 0


def test_no_disruption_keeps_current_plan_exactly():
    s = load_scenario("tiny_two_visit")
    a, b = current_result(s), repair(s, [])
    assert a.assignments == b.assignments
    assert b.objective.visits_moved == 0


def test_locked_disruption_is_infeasible():
    s = load_scenario("tiny")
    r = repair(s, [RemoveCrewDay(crew_id="A", date=dt.date(2018, 6, 5))])
    assert r.status == "infeasible"
    assert not r.assignments
    assert r.validation.valid


def test_unknown_current_row_rejected():
    import pytest

    from app.contracts.models import PlannedInstall

    s = load_scenario("tiny")
    s.current_plan.append(
        PlannedInstall(site_id="UNKNOWN", crew_id="A", date=dt.date(2018, 6, 4), locked=False)
    )
    with pytest.raises(ValueError):
        repair(s, [])


def test_locks_reserve_capacity_before_unlocked_bookings():
    from app.contracts.models import ReduceCrewDay

    s = load_scenario("tiny_two_visit").model_copy(deep=True)
    for row in s.current_plan:
        row.locked = row.job_id == "H2-I"
    r = repair(s, [ReduceCrewDay(crew_id="I", date=dt.date(2018, 6, 4), available_min=210)])
    assert r.validation.valid
    assert next(a for a in r.assignments if a.job_id == "H2-I").date == dt.date(2018, 6, 4)
    assert not any(a.job_id == "H1-I" and a.date == dt.date(2018, 6, 4) for a in r.assignments)


def test_inventory_receipt_delay_never_overbooks_stock():
    from app.contracts.models import DelayInventory

    s = load_scenario("tiny_two_visit")
    receipt = s.inventory[0]
    r = repair(
        s,
        [
            DelayInventory(
                configuration_id=receipt.configuration_id,
                from_date=receipt.available_date,
                to_date=s.config.planning_end,
            )
        ],
    )
    assert r.validation.valid
    assert all(a.visit_type == "install" or a.date == s.config.planning_end for a in r.assignments)


def test_repaired_install_does_not_release_retainable_battery_booking():
    from app.contracts.models import CrewDay, PlannedInstall

    s = load_scenario("tiny_two_visit").model_copy(deep=True)
    s.sites = s.sites[:2]
    for site in s.sites:
        site.ready_date = dt.date(2018, 6, 4)
        site.deadline = dt.date(2018, 6, 6)
        site.duration_min = 75
        for visit in site.visits:
            visit.duration_min = 60 if visit.visit_type == "install" else 75
    clusters = [c.cluster_id for c in s.clusters]
    s.crew_days = [
        CrewDay(
            crew_id=crew,
            date=dt.date(2018, 6, day),
            available_min=135 if crew == "B" else 480,
            skills=["battery" if crew == "B" else "install"],
            allowed_clusters=clusters,
        )
        for crew in ("I", "J", "B")
        for day in (4, 5, 6)
    ]
    s.current_plan = [
        PlannedInstall(
            site_id=site, job_id=job, crew_id=crew, date=dt.date(2018, 6, day), locked=False
        )
        for site, job, crew, day in [
            ("H1", "H1-I", "I", 4),
            ("H2", "H2-I", "J", 4),
            ("H1", "H1-B", "B", 6),
            ("H2", "H2-B", "B", 5),
        ]
    ]
    r = repair(
        s,
        [
            RemoveCrewDay(crew_id="I", date=dt.date(2018, 6, 4)),
            RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5)),
        ],
    )
    assert r.validation.valid
    at = {a.job_id: a for a in r.assignments}
    assert at["H1-I"].date == dt.date(2018, 6, 5)
    assert at["H1-B"].date == dt.date(2018, 6, 6)
    assert "H2-B" not in at
