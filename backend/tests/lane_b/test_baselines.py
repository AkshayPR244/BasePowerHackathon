"""B-13: baselines share eligibility, capacity, inventory, and locks with the planner."""

import pytest

from app.contracts.enums import Algorithm, JobState, Mode, PlanStatus
from app.contracts.models import PlanRequest
from app.planning.solve import plan
from tests.lane_b.conftest import REMOVE_A_MON, make_scenario

BASELINES = [Algorithm.baseline_edf, Algorithm.baseline_nearest_cluster]


def _check_rules(scenario, r):
    sites = {s.site_id: s for s in scenario.sites}
    cds = {(c.crew_id, c.date): c for c in scenario.crew_days}
    per_slot: dict = {}
    for a in r.assignments:
        s, c = sites[a.site_id], cds[a.crew_id, a.date]
        assert s.required_skill in c.skills and s.cluster_id in c.allowed_clusters
        assert a.date >= s.ready_date
        per_slot.setdefault((a.crew_id, a.date), []).append(s)
    travel = {k.cluster_id: k.travel_allowance_min for k in scenario.clusters}
    for slot, jobs in per_slot.items():
        assert len({j.cluster_id for j in jobs}) == 1
        used = sum(j.duration_min for j in jobs) + travel[jobs[0].cluster_id]
        assert used <= cds[slot].available_min
    for d in sorted({c.date for c in scenario.crew_days}):
        used = sum(1 for a in r.assignments if a.date <= d)
        assert used <= sum(x.quantity for x in scenario.inventory if x.available_date <= d)


@pytest.mark.parametrize("alg", BASELINES)
def test_baselines_follow_the_rules(alg, tiny):
    for req in [
        PlanRequest(scenario_id="tiny", revision=0, algorithm=alg),
        PlanRequest(
            scenario_id="tiny", revision=1, mode=Mode.recovery, algorithm=alg, edits=[REMOVE_A_MON]
        ),
    ]:
        r = plan(tiny, req)
        assert r.status == PlanStatus.feasible
        assert r.algorithm == alg
        assert "not an optimum" in r.message
        _check_rules(
            tiny
            if not req.edits
            else tiny.model_copy(
                update={
                    "crew_days": [
                        c for c in tiny.crew_days if (c.crew_id, str(c.date)) != ("A", "2018-06-04")
                    ]
                }
            ),
            r,
        )
        n01 = next(a for a in r.assignments if a.site_id == "N-01")
        assert n01.state == JobState.locked


@pytest.mark.parametrize("alg", BASELINES)
def test_baselines_on_30_jobs(alg):
    s = make_scenario(seed=5)
    r = plan(s, PlanRequest(scenario_id=s.scenario_id, revision=0, algorithm=alg))
    _check_rules(s, r)


@pytest.mark.parametrize("alg", BASELINES)
def test_cpsat_is_never_worse_than_a_baseline(alg):
    s = make_scenario(seed=9)
    req = PlanRequest(scenario_id=s.scenario_id, revision=0, mode=Mode.recovery)
    best = plan(s, req).objective
    base = plan(s, req.model_copy(update={"algorithm": alg})).objective
    key = lambda o: (o.jobs_late + o.jobs_unscheduled, o.total_delay_days)  # noqa: E731
    assert key(best)[0] <= key(base)[0]
