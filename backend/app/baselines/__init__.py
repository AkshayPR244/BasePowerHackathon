"""Baselines. Same data, eligibility, travel, inventory, and validator as the CP-SAT planner."""

import time

from app.baselines.edf import edf
from app.baselines.greedy import Board
from app.baselines.nearest_cluster import nearest_cluster
from app.contracts.enums import Algorithm, Mode, PlanStatus, StageStatus
from app.contracts.models import PlanRequest, PlanResult, Scenario, StageMeta
from app.planning.edits import restrict_appointments
from app.planning.explain import cannot_finish, join_ids
from app.planning.model import eligibility
from app.planning.result import build_result, locked_job_slots

_RUNNERS = {Algorithm.baseline_edf: edf, Algorithm.baseline_nearest_cluster: nearest_cluster}
_LABEL = {
    Algorithm.baseline_edf: "Earliest-deadline-first baseline",
    Algorithm.baseline_nearest_cluster: "Nearest-cluster-first baseline",
}


def run_baseline(scenario: Scenario, req: PlanRequest, forced, values, policy) -> PlanResult:
    elig = restrict_appointments(eligibility(scenario, Mode.recovery, forced), req.edits)
    t0 = time.monotonic()
    common = dict(
        scenario=scenario,
        elig=elig,
        mode=Mode.recovery,  # a greedy rule cannot promise deadlines
        algorithm=req.algorithm,
        policy=policy,
        revision=req.revision,
        edits=list(req.edits),
        values=values,
    )

    def infeasible(reason: str) -> PlanResult:
        elapsed = int((time.monotonic() - t0) * 1000)
        return build_result(
            placed=None,
            status=PlanStatus.infeasible,
            stages=[StageMeta(name="greedy", status=StageStatus.infeasible, elapsed_ms=elapsed)],
            message=f"{_LABEL[req.algorithm]}. {reason}",
            **common,
        )

    unreachable = sorted(
        sid
        for sid in forced
        if sid in elig.blocked or any(not elig.options[j.job_id] for j in elig.jobs_of_site(sid))
    )
    if unreachable:
        return infeasible(cannot_finish(unreachable))
    board = Board(scenario, elig)
    locks = locked_job_slots(scenario)
    lost = sorted(jid for jid, slot in locks.items() if slot not in elig.options.get(jid, []))
    kept = sorted((jid for jid in locks if jid not in lost), key=lambda j: (elig.jobs[j].final, j))
    for jid in lost + kept:
        if jid in lost or not board.fits(jid, locks[jid], check_ready=False):
            return infeasible(
                f"Locked visit {jid} cannot keep its crew-day after these changes. "
                "Unlock it or undo the disruption."
            )
        board.place(jid, locks[jid])
    board = _RUNNERS[req.algorithm](scenario, elig, board, forced)
    for jid in locks:
        if not board.ready(elig.jobs[jid], locks[jid][1]):
            return infeasible(f"Locked visit {jid} has no install far enough before it.")
    missed = sorted(
        sid for sid in forced if any(j.job_id not in board.placed for j in elig.jobs_of_site(sid))
    )
    if missed:
        due = "its deadline" if len(missed) == 1 else "their deadlines"
        return infeasible(f"The rule could not place {join_ids(missed)} by {due}.")
    elapsed = int((time.monotonic() - t0) * 1000)
    result = build_result(
        placed=board.placed,
        status=PlanStatus.feasible,
        stages=[StageMeta(name="greedy", status=StageStatus.feasible, elapsed_ms=elapsed)],
        message="",
        **common,
    )
    o = result.objective
    assert o is not None
    late, uns = o.jobs_late, o.jobs_unscheduled - o.jobs_blocked
    outcome = (
        "Every schedulable home meets its deadline."
        if not late and not uns
        else f"{late} late, {uns} not scheduled."
    )
    msg = f"{_LABEL[req.algorithm]}. {outcome} A greedy rule, not an optimum."
    if req.mode == Mode.strict and (late or uns):
        msg += " Baselines may miss deadlines, so they report in recovery terms."
    return result.model_copy(update={"message": msg})
