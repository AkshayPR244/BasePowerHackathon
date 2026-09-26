"""B-19: 30 jobs replan under 5 s. The 100-job timing prints for PROGRESS.md.

The travel stage is bin packing and can use the whole budget. It then ends as `feasible`
with its gap reported. The four priority stages must still be proven optimal.
"""

import os
import time

import pytest

from app.contracts.enums import Mode, StageStatus
from app.contracts.models import PlanRequest
from app.planning.solve import plan
from tests.lane_b.conftest import make_scenario

PRIORITY = ["jobs_late_or_unscheduled", "total_delay", "operating_value", "changed_installs"]


def _run(n_jobs: int, n_crews: int, seed: int, limit: float):
    s = make_scenario(n_jobs=n_jobs, n_crews=n_crews, n_days=10, seed=seed)
    req = PlanRequest(scenario_id=s.scenario_id, revision=0, mode=Mode.recovery, time_limit_s=limit)
    t0 = time.monotonic()
    r = plan(s, req)
    return r, time.monotonic() - t0


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_30_jobs_under_5s(seed):
    r, elapsed = _run(30, 3, seed, limit=4.5)
    assert elapsed < 5, f"{elapsed:.2f} s"
    stages = {m.name: m.status for m in r.stages}
    assert all(stages[n] == StageStatus.optimal for n in PRIORITY)
    travel = next(m for m in r.stages if m.name == "travel")
    assert travel.status in (StageStatus.optimal, StageStatus.feasible)
    assert travel.gap is not None


@pytest.mark.skipif(not os.environ.get("PERF_100"), reason="Set PERF_100=1 to time 100 jobs")
def test_100_jobs_timing():
    r, elapsed = _run(100, 6, 1, limit=15)
    print(f"\n100 jobs: {elapsed:.2f} s, status {r.status.value}")
    for m in r.stages:
        print(f"  {m.name}: {m.status.value}, gap {m.gap}, {m.elapsed_ms} ms")
