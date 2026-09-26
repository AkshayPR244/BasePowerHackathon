"""B-15: adding a crew-day never worsens a proven optimal recovery objective."""

import pytest

from app.contracts.enums import Mode, PlanStatus
from app.contracts.models import AddCrewDay, PlanRequest
from app.planning.solve import plan
from tests.lane_b.conftest import REMOVE_A_MON, make_scenario


def _key(r):
    """Recovery objective in stage order. Lower is better."""
    v = {m.name: m.value for m in r.stages}
    return (
        v["jobs_late_or_unscheduled"],
        v["total_delay"],
        v["changed_installs"],
        -v["operating_value"],
        v["travel"],
    )


def _check(scenario, base_edits, add):
    req = PlanRequest(
        scenario_id=scenario.scenario_id, revision=0, mode=Mode.recovery, edits=base_edits
    )
    before = plan(scenario, req)
    after = plan(scenario, req.model_copy(update={"edits": [*base_edits, add]}))
    assert before.status == after.status == PlanStatus.optimal
    # The old plan stays feasible with the new day unused, so no stage may get worse.
    assert _key(after) <= _key(before)


def test_tiny(tiny):
    add = AddCrewDay(
        crew_id="C",
        date="2018-06-04",
        available_min=480,
        skills=["install"],
        allowed_clusters=["N"],
    )
    _check(tiny, [REMOVE_A_MON], add)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_synthetic(seed):
    s = make_scenario(n_jobs=24, n_days=6, seed=seed, stock=40)
    day = s.crew_days[0].date
    add = AddCrewDay(
        crew_id="X",
        date=day,
        available_min=480,
        skills=["install"],
        allowed_clusters=sorted(c.cluster_id for c in s.clusters),
    )
    _check(s, [], add)
