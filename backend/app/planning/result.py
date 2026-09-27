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
from app.contracts.visits import job_of_row, jobs_of
from app.planning import explain
from app.planning.model import Eligibility
from app.validate.plan import value_distinguishes_choices

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
    unlocked = [p for p in scenario.current_plan if not p.locked]
    values_equal = not value_distinguishes_choices(scenario, values)

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
            unscheduled=sorted(unscheduled, key=lambda u: (u.site_id, u.job_id or "")),
            crew_days=[],
            objective=None,
        )

    assignments = []
    locked_jobs = locked_job_slots(scenario)
    order = sorted(elig.jobs.values(), key=lambda j: (j.site_id, j.final))
    for job in order:
        site = sites[job.site_id]
        slot = placed.get(job.job_id)
        if slot is None:
            unscheduled.append(
                UnscheduledJob(
                    site_id=job.site_id,
                    state=JobState.unscheduled,
                    reasons=[],
                    detail=explain.unscheduled_detail(site, job),
                    job_id=job.assignment_job_id,
                    visit_type=job.visit_type,
                )
            )
            continue
        crew, d = slot
        late = max(0, (d - site.deadline).days) if job.final else 0
        if locked_jobs.get(job.job_id) == (crew, d):
            state = JobState.locked
        elif late:
            state = JobState.late
        else:
            state = JobState.scheduled
        assignments.append(
            Assignment(
                site_id=job.site_id,
                crew_id=crew,
                date=d,
                state=state,
                days_late=late,
                value_usd=values.get((job.site_id, d), 0.0) if job.final else 0.0,
                job_id=job.assignment_job_id,
                visit_type=job.visit_type,
            )
        )

    durations = {j.job_id: j.duration_min for j in elig.jobs.values()}
    usage = []
    for c in sorted(scenario.crew_days, key=lambda c: (c.crew_id, c.date)):
        here = [a for a in assignments if (a.crew_id, a.date) == (c.crew_id, c.date)]
        k = sites[here[0].site_id].cluster_id if here else None
        usage.append(
            CrewDayUsage(
                crew_id=c.crew_id,
                date=c.date,
                cluster_id=k,
                onsite_min=sum(durations[a.job_id or a.site_id] for a in here),
                travel_min=travel[k] if k else 0,
                available_min=c.available_min,
            )
        )
    busy = sum(u.onsite_min + u.travel_min for u in usage)
    avail = sum(u.available_min for u in usage)
    finals = [a for a in assignments if elig.jobs[a.job_id or a.site_id].final]
    n_late = sum(1 for a in finals if a.days_late)
    at = {(a.job_id or a.site_id): (a.crew_id, a.date) for a in assignments}
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}
    moved = [p for p in unlocked if at.get(job_of_row(p, by_site)) != (p.crew_id, p.date)]
    objective = ObjectiveComponents(
        jobs_on_time=len(finals) - n_late,
        jobs_late=n_late,
        jobs_unscheduled=len(scenario.sites) - len(finals),
        jobs_blocked=len(elig.blocked),
        total_delay_days=sum(a.days_late for a in finals),
        operating_value_usd=sum(a.value_usd for a in finals),
        changed_installs=len(moved),
        travel_allowance_min=sum(u.travel_min for u in usage),
        crew_utilization=min(1.0, round(busy / avail, 4)) if avail else 0.0,
        value_distinguishes_choices=not values_equal,
        visits_moved=len(moved),
        customers_to_reschedule=len({p.site_id for p in moved}),
    )
    return PlanResult(
        **common,
        assignments=assignments,
        unscheduled=sorted(unscheduled, key=lambda u: (u.site_id, u.job_id or "")),
        crew_days=usage,
        objective=objective,
    )


def locked_job_slots(scenario: Scenario) -> dict[str, tuple[str, dt.date]]:
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}
    out = {}
    for p in scenario.current_plan:
        if p.locked and (jid := job_of_row(p, by_site)):
            out[jid] = (p.crew_id, p.date)
    return out


def no_legal_date_jobs(scenario: Scenario, elig: Eligibility) -> list[UnscheduledJob]:
    sites = {s.site_id: s for s in scenario.sites}
    return [
        UnscheduledJob(
            site_id=sid,
            state=JobState.unscheduled,
            reasons=[ReasonCode.NO_LEGAL_DATE],
            detail=explain.no_legal_date_detail(sites[sid], scenario),
        )
        for sid in sorted({j.site_id for j in elig.jobs.values()})
        if any(not elig.options[j.job_id] for j in elig.jobs_of_site(sid))
    ]
