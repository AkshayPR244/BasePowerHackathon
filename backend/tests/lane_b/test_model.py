import datetime as dt

from app.contracts.enums import JobState, Mode, PlanStatus, ReasonCode
from app.contracts.models import PlannedInstall, PlanRequest
from app.planning.model import build, eligibility
from app.planning.solve import plan
from tests.lane_b.conftest import make_scenario

MON, TUE, WED = dt.date(2018, 6, 4), dt.date(2018, 6, 5), dt.date(2018, 6, 6)
STRICT = PlanRequest(scenario_id="tiny", revision=0)
RECOVERY = PlanRequest(scenario_id="tiny", revision=0, mode=Mode.recovery)


def test_pruning_creates_only_legal_triples(tiny):
    elig = eligibility(tiny, Mode.strict, set())
    pm = build(tiny, elig, Mode.strict, set(), {})
    sites = {s.site_id: s for s in tiny.sites}
    cds = {(c.crew_id, c.date): c for c in tiny.crew_days}
    for sid, crew, d in pm.x:
        s, c = sites[sid], cds[crew, d]
        assert s.required_skill in c.skills
        assert s.cluster_id in c.allowed_clusters
        assert s.ready_date <= d <= s.deadline
    # N-02 is due Monday and only crew A serves North.
    assert [k for k in pm.x if k[0] == "N-02"] == [("N-02", "A", MON)]
    assert "S-03" not in {k[0] for k in pm.x}


def test_blocked_job_does_not_make_strict_infeasible(tiny):
    r = plan(tiny, STRICT)
    assert r.status == PlanStatus.optimal
    s03 = next(u for u in r.unscheduled if u.site_id == "S-03")
    assert s03.state == JobState.blocked
    assert s03.reasons == [ReasonCode.SKILL_MISMATCH]


def test_blocked_reasons_cover_cluster_and_readiness(tiny):
    sites = [
        s.model_copy(update={"cluster_id": "S", "required_skill": "install"})
        if s.site_id == "S-03"
        else s
        for s in tiny.sites
    ]
    days = [c.model_copy(update={"allowed_clusters": ["S"]}) for c in tiny.crew_days]
    elig = eligibility(tiny.model_copy(update={"crew_days": days}), Mode.strict, set())
    assert elig.blocked["N-01"] == [ReasonCode.CLUSTER_NOT_ALLOWED]
    late_ready = [
        s.model_copy(update={"ready_date": dt.date(2018, 6, 9)}) if s.site_id == "S-02" else s
        for s in sites
    ]
    elig = eligibility(tiny.model_copy(update={"sites": late_ready}), Mode.strict, set())
    assert elig.blocked["S-02"] == [ReasonCode.DEADLINE_BEFORE_READY, ReasonCode.NOT_READY]


def test_one_cluster_per_crew_day(tiny):
    r = plan(tiny, STRICT)
    sites = {s.site_id: s for s in tiny.sites}
    per_slot: dict = {}
    for a in r.assignments:
        per_slot.setdefault((a.crew_id, a.date), set()).add(sites[a.site_id].cluster_id)
    assert all(len(ks) == 1 for ks in per_slot.values())


def test_capacity_includes_travel(tiny):
    # Crew A Tuesday holds N-01 (180) + N-03 (240) + 60 travel = 480, exactly full.
    shorter = [
        c.model_copy(update={"available_min": 479}) if (c.crew_id, c.date) == ("A", TUE) else c
        for c in tiny.crew_days
    ]
    r = plan(tiny.model_copy(update={"crew_days": shorter}), STRICT)
    for u in r.crew_days:
        assert u.onsite_min + u.travel_min <= u.available_min
    tue = sorted(a.site_id for a in r.assignments if (a.crew_id, a.date) == ("A", TUE))
    assert tue != ["N-01", "N-03"]


def test_cumulative_inventory(tiny):
    r = plan(tiny, STRICT)
    for d in [MON, TUE, WED]:
        used = sum(1 for a in r.assignments if a.date <= d)
        got = sum(x.quantity for x in tiny.inventory if x.available_date <= d)
        assert used <= got
    assert sum(1 for a in r.assignments if a.date == MON) == 3  # all of Monday's stock


def test_inventory_shortage_makes_strict_infeasible(tiny):
    inv = [
        x.model_copy(update={"quantity": 2}) if x.available_date == MON else x
        for x in tiny.inventory
    ]
    r = plan(tiny.model_copy(update={"inventory": inv}), STRICT)
    assert r.status == PlanStatus.infeasible
    assert r.assignments == []


def test_lock_is_kept(tiny):
    r = plan(tiny, STRICT)
    n01 = next(a for a in r.assignments if a.site_id == "N-01")
    assert (n01.crew_id, n01.date, n01.state) == ("A", TUE, JobState.locked)


def test_lock_conflict_is_reported_not_dropped(tiny):
    # Crew B cannot serve North, so this lock can never hold.
    bad_lock = PlannedInstall(site_id="N-03", crew_id="B", date=WED, locked=True)
    r = plan(tiny.model_copy(update={"current_plan": [*tiny.current_plan, bad_lock]}), RECOVERY)
    assert r.status == PlanStatus.infeasible
    conflict = next(u for u in r.unscheduled if u.site_id == "N-03")
    assert conflict.reasons == [ReasonCode.LOCK_CONFLICT]
    assert "Unlock" in r.message


def test_synthetic_30_jobs_solves():
    s = make_scenario()
    r = plan(s, PlanRequest(scenario_id=s.scenario_id, revision=0, mode=Mode.recovery))
    assert r.status in (PlanStatus.optimal, PlanStatus.feasible)
    assert r.objective is not None
