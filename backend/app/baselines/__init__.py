"""Baselines. Same data, eligibility, travel, inventory, and validator as the CP-SAT planner."""

import time

from app.baselines.edf import edf
from app.baselines.nearest_cluster import nearest_cluster
from app.contracts.enums import Algorithm, Mode, PlanStatus, StageStatus
from app.contracts.models import PlanRequest, PlanResult, Scenario, StageMeta
from app.planning.model import eligibility
from app.planning.result import build_result

_RUNNERS = {Algorithm.baseline_edf: edf, Algorithm.baseline_nearest_cluster: nearest_cluster}
_LABEL = {
    Algorithm.baseline_edf: "Earliest-deadline-first baseline",
    Algorithm.baseline_nearest_cluster: "Nearest-cluster-first baseline",
}


def run_baseline(scenario: Scenario, req: PlanRequest, forced, values, policy) -> PlanResult:
    elig = eligibility(scenario, Mode.recovery, set())
    locks = {
        p.site_id: (p.crew_id, p.date)
        for p in scenario.current_plan
        if p.locked and (p.crew_id, p.date) in elig.any_option.get(p.site_id, [])
    }
    t0 = time.monotonic()
    board = _RUNNERS[req.algorithm](scenario, elig, locks, forced)
    elapsed = int((time.monotonic() - t0) * 1000)
    result = build_result(
        scenario=scenario,
        elig=elig,
        placed=board.placed,
        status=PlanStatus.feasible,
        stages=[StageMeta(name="greedy", status=StageStatus.feasible, elapsed_ms=elapsed)],
        mode=Mode.recovery,  # a greedy rule cannot promise deadlines
        algorithm=req.algorithm,
        policy=policy,
        revision=req.revision,
        edits=list(req.edits),
        message="",
        values=values,
    )
    o = result.objective
    assert o is not None
    late, uns = o.jobs_late, o.jobs_unscheduled - o.jobs_blocked
    outcome = (
        "Every schedulable job meets its deadline."
        if not late and not uns
        else f"{late} late, {uns} not scheduled."
    )
    msg = f"{_LABEL[req.algorithm]}. {outcome} A greedy rule, not an optimum."
    if req.mode == Mode.strict:
        msg += " Baselines may miss deadlines, so they report in recovery terms."
    return result.model_copy(update={"message": msg})
