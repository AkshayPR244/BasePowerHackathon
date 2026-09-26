"""Planner entry point: scenario + request -> validated PlanResult. No FastAPI imports."""

import datetime as dt
import time

from app.contracts.enums import (
    Algorithm,
    JobState,
    Mode,
    ObjectivePolicy,
    PlanStatus,
    ReasonCode,
    StageStatus,
)
from app.contracts.models import PlanRequest, PlanResult, Scenario, StageMeta, UnscheduledJob
from app.planning import explain
from app.planning.edits import apply_edits
from app.planning.lexicographic import Stage, solve_stages
from app.planning.model import Eligibility, build, eligibility
from app.planning.result import build_result, no_legal_date_jobs
from app.validate import validate_plan

STRICT_STAGES = [
    Stage("operating_value", maximize=True),
    Stage("changed_installs"),
    Stage("travel"),
]
RECOVERY_STAGES = [
    Stage("jobs_late_or_unscheduled"),
    Stage("total_delay"),
    Stage("operating_value", maximize=True),
    Stage("changed_installs"),
    Stage("travel"),
]


class InvalidPlanError(RuntimeError):
    """The validator rejected a plan the planner produced. This is a bug, never a result."""


def site_values(scenario: Scenario) -> dict[tuple[str, dt.date], float]:
    # TODO(lane-b, B-17): read Lane A's value table. Equal (zero) values until then.
    return {}


def plan(base: Scenario, req: PlanRequest) -> PlanResult:
    t0 = time.monotonic()
    policy = req.objective_policy or base.config.objective_policy
    edited = apply_edits(base, req.edits)
    scenario = edited.scenario
    values = site_values(scenario)
    common = dict(
        mode=req.mode,
        algorithm=req.algorithm,
        policy=policy,
        revision=req.revision,
        edits=list(req.edits),
        values=values,
    )

    if edited.issues:
        empty = Eligibility(any_option={}, options={}, blocked={})
        return build_result(
            scenario=scenario,
            elig=empty,
            placed=None,
            status=PlanStatus.invalid_input,
            stages=[],
            message="The changes do not match this scenario. "
            + " ".join(i.message for i in edited.issues),
            input_issues=edited.issues,
            **common,
        )

    if req.algorithm != Algorithm.cpsat:
        from app.baselines import run_baseline

        result = run_baseline(scenario, req, edited.forced, values, policy)
    else:
        result = _solve(scenario, req, edited.forced, values, policy, common)
    result = result.model_copy(update={"solve_ms": int((time.monotonic() - t0) * 1000)})
    return _validated(scenario, result)


def _validated(scenario: Scenario, result: PlanResult) -> PlanResult:
    report = validate_plan(scenario, result)
    if report.checked and not report.valid and result.assignments:
        issues = "; ".join(i.message for i in report.issues)
        raise InvalidPlanError(f"Plan {result.plan_id} failed validation: {issues}")
    return result.model_copy(update={"validation": report})


def _stage_list(mode: Mode, policy: ObjectivePolicy) -> list[Stage]:
    return STRICT_STAGES if mode == Mode.strict else RECOVERY_STAGES


def _solve(scenario, req, forced, values, policy, common) -> PlanResult:
    mode = req.mode
    elig = eligibility(scenario, mode, forced)
    stages = _stage_list(mode, policy)

    missing = no_legal_date_jobs(scenario, elig)
    if missing:
        ids = ", ".join(u.site_id for u in missing)
        lead = (
            "No plan meets every deadline."
            if mode == Mode.strict
            else f"{ids} cannot finish by its deadline."
        )
        return build_result(
            scenario=scenario,
            elig=elig,
            placed=None,
            status=PlanStatus.infeasible,
            stages=_infeasible_stages(stages),
            message=f"{lead} {missing[0].detail}"
            + (" Try recovery mode." if mode == Mode.strict else ""),
            extra_unscheduled=missing,
            **common,
        )

    cents = {k: round(v * 100) for k, v in values.items()}
    pm = build(scenario, elig, mode, forced, cents)
    if pm.lock_conflicts:
        conflicts = [
            UnscheduledJob(
                site_id=sid,
                state=JobState.locked,
                reasons=[ReasonCode.LOCK_CONFLICT],
                detail=f"{sid} is locked to a crew-day it can no longer use.",
            )
            for sid in sorted(set(pm.lock_conflicts))
        ]
        ids = ", ".join(c.site_id for c in conflicts)
        return build_result(
            scenario=scenario,
            elig=elig,
            placed=None,
            status=PlanStatus.infeasible,
            stages=_infeasible_stages(stages),
            message=f"Locked install {ids} cannot keep its crew-day after these changes. "
            "Unlock it or undo the disruption.",
            extra_unscheduled=conflicts,
            **common,
        )

    names = {v.name: key for key, v in pm.x.items()}
    for p in scenario.current_plan:
        v = pm.x.get((p.site_id, p.crew_id, p.date))
        if v is not None and not p.locked:
            pm.model.add_hint(v, 1)

    run = [
        s
        for s in stages
        if not (policy == ObjectivePolicy.deadline_travel_only and s.name == "operating_value")
    ]
    budget = req.time_limit_s or scenario.config.solve_time_limit_s
    lex = solve_stages(
        pm.model,
        pm.exprs,
        run,
        budget_s=budget,
        seed=scenario.config.random_seed,
        workers=scenario.config.num_workers,
    )
    metas = _merge_skipped(stages, lex.stages)

    if lex.values is None:
        status = (
            PlanStatus.infeasible
            if lex.stages[0].status == StageStatus.infeasible
            else PlanStatus.timeout_no_incumbent
        )
        if status == PlanStatus.timeout_no_incumbent:
            msg = f"No plan found within {budget:g} s. This does not prove none exists."
        elif mode == Mode.strict:
            msg = (
                "No plan meets every deadline with this crew capacity and inventory. "
                "Try recovery mode."
            )
        else:
            msg = "No recovery plan fits the locked installs, crews, and inventory."
        return build_result(
            scenario=scenario,
            elig=elig,
            placed=None,
            status=status,
            stages=metas,
            message=msg,
            **common,
        )

    placed = {
        names[n][0]: (names[n][1], names[n][2])
        for n, val in lex.values.items()
        if n in names and val
    }
    run_names = {s.name for s in run}
    proven = all(m.status == StageStatus.optimal for m in metas if m.name in run_names)
    result = build_result(
        scenario=scenario,
        elig=elig,
        placed=placed,
        status=PlanStatus.optimal if proven else PlanStatus.feasible,
        stages=metas,
        message="",
        **common,
    )
    return result.model_copy(update={"message": plan_message(scenario, result)})


def _infeasible_stages(stages: list[Stage]) -> list[StageMeta]:
    return [StageMeta(name=stages[0].name, status=StageStatus.infeasible, elapsed_ms=0)] + [
        StageMeta(name=s.name, status=StageStatus.skipped, elapsed_ms=0) for s in stages[1:]
    ]


def _merge_skipped(stages: list[Stage], metas: list[StageMeta]) -> list[StageMeta]:
    by_name = {m.name: m for m in metas}
    return [
        by_name.get(s.name) or StageMeta(name=s.name, status=StageStatus.skipped, elapsed_ms=0)
        for s in stages
    ]


def plan_message(scenario: Scenario, r: PlanResult) -> str:
    o = r.objective
    assert o is not None
    parts = [explain.describe_edits(scenario, r.edits)] if r.edits else []
    schedulable = o.jobs_on_time + o.jobs_late + o.jobs_unscheduled - o.jobs_blocked
    if o.jobs_late == 0 and o.jobs_unscheduled == o.jobs_blocked:
        parts.append(f"All {schedulable} schedulable jobs meet their deadlines.")
    else:
        late = [a for a in r.assignments if a.days_late]
        for a in late:
            parts.append(
                f"{a.site_id} is {explain.plural(a.days_late, 'day')} late on "
                f"{explain.day(a.date)}."
            )
        n_uns = o.jobs_unscheduled - o.jobs_blocked
        if n_uns:
            parts.append(f"{explain.plural(n_uns, 'job')} not scheduled.")
    blocked = [u for u in r.unscheduled if u.state == JobState.blocked]
    if blocked:
        if len(blocked) == 1:
            parts.append(f"Blocked: {blocked[0].detail}")
        else:
            parts.append(f"{len(blocked)} jobs are blocked. See the deferred list.")
    if r.status == PlanStatus.feasible:
        parts.append("The time limit ended before the solver proved this plan is the best.")
    return " ".join(p.strip() for p in parts if p)
