"""Counterfactuals: re-plan the same request with one extra intervention."""

from app.compare.diff import diff_plans
from app.contracts.enums import JobState, PlanStatus
from app.contracts.models import (
    AddCrewDay,
    CounterfactualRequest,
    CounterfactualResult,
    ForceInclude,
    PlanDiff,
    PlanResult,
    Scenario,
)
from app.planning.explain import day, plural
from app.planning.solve import plan


def counterfactual(base: Scenario, req: CounterfactualRequest) -> CounterfactualResult:
    request = req.request.model_copy(update={"edits": [*req.request.edits, req.intervention]})
    result = plan(base, request)
    feasible = result.status in (PlanStatus.optimal, PlanStatus.feasible)
    if feasible:
        diff = diff_plans(req.base, result)
    else:
        same = diff_plans(req.base, req.base)
        diff = PlanDiff(
            **same.model_dump(exclude={"after_plan_id", "headline"}),
            after_plan_id=result.plan_id,
            headline="No change. The intervention is infeasible.",
        )
    return CounterfactualResult(
        intervention=req.intervention,
        feasible=feasible,
        result=result,
        diff=diff,
        summary=_summary(req, result, diff, feasible),
    )


def _summary(req: CounterfactualRequest, result: PlanResult, diff: PlanDiff, feasible: bool) -> str:
    e = req.intervention
    if isinstance(e, ForceInclude):
        lead = f"Including {e.site_id} by its deadline"
    elif isinstance(e, AddCrewDay):
        lead = (
            f"Adding Crew {e.crew_id} on {day(e.date)} "
            f"({', '.join(e.allowed_clusters)}, {e.available_min} min)"
        )
    else:
        lead = "This intervention"
    if not feasible:
        why = next(
            (u.detail for u in result.unscheduled if u.reasons and u.state != JobState.blocked),
            result.message,
        )
        return f"{lead} is infeasible. {why}"
    back = [
        c.site_id
        for c in diff.changes
        if c.before_state == JobState.late and c.after_state != JobState.late
    ]
    o = result.objective
    parts = [f"{lead} is feasible."]
    displaced = [
        c.site_id
        for c in diff.changes
        if c.after_state == JobState.late and c.before_state != JobState.late
    ]
    if back:
        parts.append(f"{', '.join(back)} {'is' if len(back) == 1 else 'are'} back on time.")
    if displaced:
        verb = "becomes" if len(displaced) == 1 else "become"
        parts.append(f"{', '.join(displaced)} {verb} late instead.")
    if o and o.jobs_late == 0 and o.jobs_unscheduled == o.jobs_blocked:
        parts.append("No job is late.")
    elif o:
        parts.append(f"{plural(o.jobs_late, 'job')} late.")
    moved = diff.summary.moved
    if moved:
        parts.append(f"{plural(moved, 'job')} {'moves' if moved == 1 else 'move'}.")
    return " ".join(parts)
