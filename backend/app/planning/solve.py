"""Planner entry point: scenario + request -> validated PlanResult. No FastAPI imports."""

import datetime as dt
import time

from app.contracts.enums import (
    Algorithm,
    DataKind,
    JobState,
    Mode,
    ObjectivePolicy,
    PlanStatus,
    ReasonCode,
    StageStatus,
)
from app.contracts.models import (
    Assumption,
    PlanRequest,
    PlanResult,
    Scenario,
    StageMeta,
    UnscheduledJob,
)
from app.contracts.visits import job_of_row, jobs_of
from app.planning import explain
from app.planning.edits import apply_edits, appointment_windows, restrict_appointments
from app.planning.infeasibility import conflicting_jobs
from app.planning.lexicographic import Stage, solve_stages
from app.planning.model import Eligibility, build, eligibility
from app.planning.result import build_result, no_legal_date_jobs
from app.validate import validate_plan
from app.valuation import value_table as valuation

# Value is a tie-breaker: a recovery tool should not move customers for small modeled value.
STRICT_STAGES = [
    Stage("changed_installs"),
    Stage("operating_value", maximize=True),
    Stage("travel"),
    Stage("canonical", max_s=2.0),
]
RECOVERY_STAGES = [
    Stage("jobs_late_or_unscheduled"),
    Stage("total_delay"),
    Stage("changed_installs"),
    Stage("operating_value", maximize=True),
    Stage("travel"),
    Stage("canonical", max_s=2.0),
]


class InvalidPlanError(RuntimeError):
    """The validator rejected a plan the planner produced. This is a bug, never a result."""


def site_values(scenario: Scenario) -> tuple[dict[tuple[str, dt.date], float], str | None]:
    """Values from Lane A's table, plus a note when the table could not be used."""
    try:
        rows = valuation.value_table(scenario)
    except ValueError as e:
        return {}, f"Energy values are unavailable ({e}). All values count as $0."
    usable = [r for r in rows if r.solver_status in ("optimal", "assumed_zero")]
    values = {(r.site_id, r.install_date): r.value_usd for r in usable}
    missing = len(rows) - len(usable)
    note = (
        f"{missing} site-date values had no solved valuation and count as $0." if missing else None
    )
    return values, note


def plan(base: Scenario, req: PlanRequest) -> PlanResult:
    t0 = time.monotonic()
    policy = req.objective_policy or base.config.objective_policy
    edited = apply_edits(base, req.edits)
    scenario = edited.scenario
    values, value_note = site_values(base)
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
    notes = list(result.assumptions)
    if value_note:
        notes.append(Assumption(key="unresolved_values", text=value_note, kind=DataKind.assumed))
    if policy == ObjectivePolicy.deadline_travel_only and values:
        notes.append(
            Assumption(
                key="revalued",
                text="This plan ignored energy value. Its value is recomputed with the same table.",
                kind=DataKind.derived,
            )
        )
    result = result.model_copy(
        update={"solve_ms": int((time.monotonic() - t0) * 1000), "assumptions": notes}
    )
    return _validated(scenario, result)


def _validated(scenario: Scenario, result: PlanResult) -> PlanResult:
    report = validate_plan(scenario, result)
    if report.checked and not report.valid:
        issues = "; ".join(i.message for i in report.issues)
        raise InvalidPlanError(f"Plan {result.plan_id} failed validation: {issues}")
    windows = appointment_windows(result.edits)
    for a in result.assignments:
        if (bounds := windows.get(a.job_id or a.site_id)) is not None:
            if a.date < bounds[0] or (bounds[1] is not None and a.date > bounds[1]):
                raise InvalidPlanError("Visit violates the requested appointment window.")
    return result.model_copy(update={"validation": report})


def _stage_list(mode: Mode, policy: ObjectivePolicy) -> list[Stage]:
    return STRICT_STAGES if mode == Mode.strict else RECOVERY_STAGES


def _solve(scenario, req, forced, values, policy, common) -> PlanResult:
    mode = req.mode
    elig = restrict_appointments(eligibility(scenario, mode, forced), req.edits)
    stages = _stage_list(mode, policy)

    stuck = sorted(forced & set(elig.blocked))
    if stuck:
        site = next(s for s in scenario.sites if s.site_id == stuck[0])
        detail = explain.blocked_detail(site, elig.blocked[stuck[0]], scenario)
        return build_result(
            scenario=scenario,
            elig=elig,
            placed=None,
            status=PlanStatus.infeasible,
            stages=_infeasible_stages(stages),
            message=f"{explain.cannot_finish(stuck)} {detail}",
            **common,
        )

    missing = [
        u for u in no_legal_date_jobs(scenario, elig) if mode == Mode.strict or u.site_id in forced
    ]
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
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}
    for p in scenario.current_plan:
        v = pm.x.get((job_of_row(p, by_site), p.crew_id, p.date))
        if v is not None and not p.locked:
            pm.model.add_hint(v, 1)

    workers = scenario.config.num_workers
    run = [
        s
        for s in stages
        if not (policy == ObjectivePolicy.deadline_travel_only and s.name == "operating_value")
        # One worker is already deterministic, so the tie-break stage would only cost time.
        and not (s.name == "canonical" and workers == 1)
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
    reported = [st for st in stages if st.name != "canonical"]
    metas = [_in_usd(m) for m in _merge_skipped(reported, lex.stages)]

    if lex.values is None:
        failed = next(
            m.status
            for m in lex.stages
            if m.status not in (StageStatus.optimal, StageStatus.feasible)
        )
        status = (
            PlanStatus.infeasible
            if failed == StageStatus.infeasible
            else PlanStatus.timeout_no_incumbent
        )
        extra: list[UnscheduledJob] = []
        if status == PlanStatus.timeout_no_incumbent:
            msg = f"No plan found within {budget:g} s. This does not prove none exists."
        elif mode == Mode.strict or forced:
            msg = (
                "No plan meets every deadline with this crew capacity and inventory. "
                "Try recovery mode."
            )
            core = conflicting_jobs(scenario, forced if mode == Mode.recovery else set(), budget)
            if core:
                if mode == Mode.recovery:
                    core = [sid for sid in core if sid in forced] or core
                ids = ", ".join(core)
                detail = (
                    f"{ids} cannot all finish by their deadlines "
                    "with the crews and inventory available."
                )
                msg = f"No plan meets every deadline. {detail} Try recovery mode."
                extra = [
                    UnscheduledJob(
                        site_id=sid,
                        state=JobState.unscheduled,
                        reasons=[ReasonCode.CAPACITY],
                        detail=detail,
                    )
                    for sid in core
                ]
        else:
            msg = "No recovery plan fits the locked installs, crews, and inventory."
        return build_result(
            scenario=scenario,
            elig=elig,
            placed=None,
            status=status,
            stages=metas,
            message=msg,
            extra_unscheduled=extra,
            **common,
        )

    placed = {
        names[n][0]: (names[n][1], names[n][2])
        for n, val in lex.values.items()
        if n in names and val
    }
    run_names = {s.name for s in run} - {"canonical"}
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
    stages = [st for st in stages if st.name != "canonical"]
    return [StageMeta(name=stages[0].name, status=StageStatus.infeasible, elapsed_ms=0)] + [
        StageMeta(name=s.name, status=StageStatus.skipped, elapsed_ms=0) for s in stages[1:]
    ]


def _in_usd(m: StageMeta) -> StageMeta:
    """The model counts value in cents. Report the stage in USD."""
    if m.name != "operating_value" or m.value is None:
        return m
    bound = None if m.bound is None else m.bound / 100
    return m.model_copy(update={"value": m.value / 100, "bound": bound})


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
            what = f"{a.site_id} battery day" if a.visit_type else a.site_id
            parts.append(
                f"{what} is {explain.plural(a.days_late, 'day')} late on {explain.day(a.date)}."
            )
        n_uns = o.jobs_unscheduled - o.jobs_blocked
        if n_uns:
            parts.append(f"{explain.plural(n_uns, 'job')} not scheduled.")
    if o.customers_to_reschedule and any(a.visit_type for a in r.assignments):
        parts.append(
            f"{explain.plural(o.visits_moved, 'visit')} move, so "
            f"{explain.plural(o.customers_to_reschedule, 'customer')} need a new date."
        )
    blocked = [u for u in r.unscheduled if u.state == JobState.blocked]
    if blocked:
        if len(blocked) == 1:
            parts.append(f"Blocked: {blocked[0].detail}")
        else:
            parts.append(f"{len(blocked)} jobs are blocked. See the deferred list.")
    if r.status == PlanStatus.feasible:
        parts.append("The time limit ended before the solver proved this plan is the best.")
    return " ".join(p.strip() for p in parts if p)
