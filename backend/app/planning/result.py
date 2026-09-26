"""Build a PlanResult from assignments. Shared by the planner and the baselines."""

import datetime as dt

from app.contracts.enums import (
    Algorithm,
    DataKind,
    JobState,
    Mode,
    ObjectivePolicy,
    PlanStatus,
    ReasonCode,
)
from app.contracts.models import (
    Assignment,
    Assumption,
    CrewDayUsage,
    Edit,
    InputIssue,
    ObjectiveComponents,
    PlanResult,
    Scenario,
    StageMeta,
    UnscheduledJob,
    ValidationReport,
)
from app.planning import explain
from app.planning.model import Eligibility

NOT_RUN = ValidationReport(checked=False, valid=False, issues=[], validator="not run")


def assumptions(scenario: Scenario, values_equal: bool) -> list[Assumption]:
    out = [
        Assumption(
            key="travel_allowance",
            text="Travel is a fixed allowance per active crew-day and cluster, "
            "not a routed drive time.",
            kind=DataKind.assumed,
        )
    ]
    if scenario.config.synthetic:
        out.insert(
            0,
            Assumption(
                key="synthetic_inputs",
                text="All inputs in this scenario are synthetic.",
                kind=DataKind.synthetic,
            ),
        )
    if values_equal:
        out.append(
            Assumption(
                key="equal_values",
                text="All site values are equal, so energy value did not change any choice.",
                kind=DataKind.assumed,
            )
        )
    return out


def plan_id(scenario_id: str, revision: int, mode: Mode, algorithm: Algorithm, h: str) -> str:
    alg = "" if algorithm == Algorithm.cpsat else f"-{Algorithm(algorithm).value}"
    return f"{scenario_id}-r{revision}-{Mode(mode).value}{alg}-{h[:8]}"


def build_result(
    *,
    scenario: Scenario,
    elig: Eligibility,
    placed: dict[str, tuple[str, dt.date]] | None,
    status: PlanStatus,
    stages: list[StageMeta],
    mode: Mode,
    algorithm: Algorithm,
    policy: ObjectivePolicy,
    revision: int,
    edits: list[Edit],
    message: str,
    values: dict[tuple[str, dt.date], float],
    extra_unscheduled: list[UnscheduledJob] | None = None,
    input_issues: list[InputIssue] | None = None,
    solve_ms: int = 0,
) -> PlanResult:
    sites = {s.site_id: s for s in scenario.sites}
    travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
    locked = {(p.site_id, p.crew_id, p.date) for p in scenario.current_plan if p.locked}
    unlocked = [p for p in scenario.current_plan if not p.locked]
    values_equal = len(set(values.values()) | {0.0}) <= 1

    unscheduled = [
        UnscheduledJob(
            site_id=sid,
            state=JobState.blocked,
            reasons=reasons,
            detail=explain.blocked_detail(sites[sid], reasons, scenario),
        )
        for sid, reasons in elig.blocked.items()
    ]
    unscheduled += extra_unscheduled or []

    common = dict(
        plan_id=plan_id(scenario.scenario_id, revision, mode, algorithm, scenario.scenario_hash),
        scenario_id=scenario.scenario_id,
        scenario_hash=scenario.scenario_hash,
        revision=revision,
        mode=mode,
        algorithm=algorithm,
        objective_policy=policy,
        edits=edits,
        status=status,
        message=message,
        stages=stages,
        validation=NOT_RUN,
        input_issues=input_issues or [],
        assumptions=assumptions(scenario, values_equal),
        solve_ms=solve_ms,
    )
    if placed is None:
        return PlanResult(
            **common,
            assignments=[],
            unscheduled=sorted(unscheduled, key=lambda u: u.site_id),
            crew_days=[],
            objective=None,
        )

    assignments = []
    for sid in sorted(elig.options):
        slot = placed.get(sid)
        if slot is None:
            unscheduled.append(
                UnscheduledJob(
                    site_id=sid,
                    state=JobState.unscheduled,
                    reasons=[],
                    detail=explain.unscheduled_detail(sites[sid]),
                )
            )
            continue
        crew, d = slot
        late = max(0, (d - sites[sid].deadline).days)
        if (sid, crew, d) in locked:
            state = JobState.locked
        elif late:
            state = JobState.late
        else:
            state = JobState.scheduled
        assignments.append(
            Assignment(
                site_id=sid,
                crew_id=crew,
                date=d,
                state=state,
                days_late=late,
                value_usd=values.get((sid, d), 0.0),
            )
        )

    usage = []
    for c in sorted(scenario.crew_days, key=lambda c: (c.crew_id, c.date)):
        jobs = [a.site_id for a in assignments if (a.crew_id, a.date) == (c.crew_id, c.date)]
        k = sites[jobs[0]].cluster_id if jobs else None
        usage.append(
            CrewDayUsage(
                crew_id=c.crew_id,
                date=c.date,
                cluster_id=k,
                onsite_min=sum(sites[j].duration_min for j in jobs),
                travel_min=travel[k] if k else 0,
                available_min=c.available_min,
            )
        )
    busy = sum(u.onsite_min + u.travel_min for u in usage)
    avail = sum(u.available_min for u in usage)
    n_late = sum(1 for a in assignments if a.days_late)
    at = {a.site_id: (a.crew_id, a.date) for a in assignments}
    objective = ObjectiveComponents(
        jobs_on_time=len(assignments) - n_late,
        jobs_late=n_late,
        jobs_unscheduled=len(unscheduled),
        jobs_blocked=len(elig.blocked),
        total_delay_days=sum(a.days_late for a in assignments),
        operating_value_usd=round(sum(a.value_usd for a in assignments), 2),
        changed_installs=sum(
            1
            for p in unlocked
            if p.site_id in elig.options and at.get(p.site_id) != (p.crew_id, p.date)
        ),
        travel_allowance_min=sum(u.travel_min for u in usage),
        crew_utilization=round(busy / avail, 4) if avail else 0.0,
        value_distinguishes_choices=not values_equal,
    )
    return PlanResult(
        **common,
        assignments=assignments,
        unscheduled=sorted(unscheduled, key=lambda u: u.site_id),
        crew_days=usage,
        objective=objective,
    )


def no_legal_date_jobs(scenario: Scenario, elig: Eligibility) -> list[UnscheduledJob]:
    sites = {s.site_id: s for s in scenario.sites}
    return [
        UnscheduledJob(
            site_id=sid,
            state=JobState.unscheduled,
            reasons=[ReasonCode.NO_LEGAL_DATE],
            detail=explain.no_legal_date_detail(sites[sid], scenario),
        )
        for sid, opts in elig.options.items()
        if not opts
    ]
