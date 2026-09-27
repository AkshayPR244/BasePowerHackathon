"""Build business-action options with comparable metrics and costs."""

import hashlib
import json

from app.compare.diff import diff_plans
from app.contracts.models import (
    CrewLoad,
    DiffSummary,
    Explanation,
    PlanDiff,
    RecoveryCounts,
    RecoveryOption,
)
from app.recovery.economics import compute

FEASIBLE = {"optimal", "feasible"}


def solved(result):
    return result.status in FEASIBLE and result.objective is not None


def _no_changes(before, after):
    return PlanDiff(
        before_plan_id=before.plan_id,
        after_plan_id=after.plan_id,
        changes=[],
        summary=DiffSummary(
            moved=0,
            added=0,
            removed=0,
            newly_late=0,
            value_delta_usd=0,
            travel_delta_min=0,
            customers_to_reschedule=0,
        ),
        headline="No feasible plan, so no visits change.",
    )


def wrap(kind, label, original, result, interventions, rates, no_action=None):
    ok = solved(result)
    base_ok = no_action is not None and solved(no_action.result)
    o = result.objective
    # An infeasible option has no plan, so it reports no changes rather than every visit removed.
    diff = diff_plans(original, result) if ok else _no_changes(original, result)
    moved = [c for c in diff.changes if c.kind in {"moved", "removed", "added"}]
    missed = o.jobs_late + o.jobs_unscheduled if ok else 0
    counts = RecoveryCounts(
        deadlines_missed=missed,
        deadlines_recovered=(
            max(0, no_action.counts.deadlines_missed - missed) if ok and base_ok else 0
        ),
        delay_days=o.total_delay_days if ok else 0,
        visits_moved=len(moved),
        customers_to_reschedule=len({c.site_id for c in moved}),
        unscheduled=o.jobs_unscheduled if ok else 0,
    )
    eco = compute(
        original,
        result,
        interventions,
        counts,
        rates,
        no_action.economics.net_impact_usd if base_ok else None,
        no_action.counts.deadlines_missed if base_ok else None,
    )
    before = {(c.crew_id, c.date): c for c in original.crew_days}
    after = {(c.crew_id, c.date): c for c in result.crew_days}

    def load(c):
        return (c.onsite_min + c.travel_min) / c.available_min if c and c.available_min else 0

    reason = (
        "No-action repair keeps original crews and retained bookings."
        if kind == "no_action"
        else (
            "Joint recovery constraints: crew skill, capacity, inventory, "
            "appointment windows, locks, and visit precedence; no unique cause "
            "inferred."
        )
    )
    identity = {
        "kind": kind,
        "result": result.model_dump(mode="json", exclude={"solve_ms", "stages", "message"}),
        "economics": eco.model_dump(mode="json"),
    }
    ident = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    return RecoveryOption(
        option_id=f"{kind}-{ident}",
        kind=kind,
        action_label=label,
        intervention_edits=interventions,
        status=result.status,
        proven_optimal=result.status == "optimal",
        result=result,
        diff_vs_original=diff,
        diff_vs_no_action=(diff_plans(no_action.result, result) if ok and base_ok else None),
        counts=counts,
        economics=eco,
        overtime_min=sum(e.extra_min for e in interventions if e.kind == "extend_crew_day"),
        explanations=[
            Explanation(
                job_id=c.job_id or c.site_id,
                text=c.note + " " + reason,
                constraint="repair_rule" if kind == "no_action" else "joint_constraints",
            )
            for c in moved
        ],
        crew_load=[
            CrewLoad(
                crew_id=c, date=d, before=load(before.get((c, d))), after=load(after.get((c, d)))
            )
            for c, d in sorted(set(before) | set(after))
        ]
        if ok
        else [],
        stub=False,
    )


def rank(option):
    o = option.result.objective
    if option.status not in FEASIBLE or o is None:
        return (1,)
    return (
        0,
        o.jobs_late + o.jobs_unscheduled - o.jobs_blocked,
        o.total_delay_days,
        option.counts.visits_moved,
        -o.operating_value_usd,
        o.travel_allowance_min,
        option.economics.net_impact_usd,
        option.option_id,
    )


def dominated(option, others):
    """True when another option misses no more deadlines, costs no more, and wins on one."""
    m, c = option.counts.deadlines_missed, option.economics.net_impact_usd
    return any(
        p is not option
        and p.counts.deadlines_missed <= m
        and p.economics.net_impact_usd <= c
        and (p.counts.deadlines_missed < m or p.economics.net_impact_usd < c)
        for p in others
    )
