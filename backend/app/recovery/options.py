"""Build business-action options with comparable metrics and costs."""

import hashlib
import json

from app.compare.diff import diff_plans
from app.contracts.models import CrewLoad, Explanation, RecoveryCounts, RecoveryOption
from app.recovery.economics import compute

FEASIBLE = {"optimal", "feasible"}


def wrap(kind, label, original, result, interventions, rates, no_action=None):
    diff = diff_plans(original, result)
    o = result.objective
    missed = (
        o.jobs_late + o.jobs_unscheduled if o else len({a.site_id for a in original.assignments})
    )
    old_ontime = (
        {
            a.site_id
            for a in no_action.result.assignments
            if a.visit_type != "install" and not a.days_late
        }
        if no_action
        else set()
    )
    new_ontime = {
        a.site_id for a in result.assignments if a.visit_type != "install" and not a.days_late
    }
    recovered = (
        len(new_ontime - old_ontime) if no_action and no_action.result.objective and o else 0
    )
    moved = [c for c in diff.changes if c.kind in {"moved", "removed", "added"}]
    counts = RecoveryCounts(
        deadlines_missed=missed,
        deadlines_recovered=recovered,
        delay_days=o.total_delay_days if o else 0,
        visits_moved=len(moved),
        customers_to_reschedule=len({c.site_id for c in moved}),
        unscheduled=o.jobs_unscheduled if o else missed,
    )
    eco = compute(
        original,
        result,
        interventions,
        counts,
        rates,
        no_action.economics.net_impact_usd if no_action and no_action.result.objective else None,
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
        diff_vs_no_action=diff_plans(no_action.result, result) if no_action else None,
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
        ],
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
