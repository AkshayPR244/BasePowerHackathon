"""Changelog-style diff between two plans."""

from app.contracts.enums import ChangeKind, JobState
from app.contracts.models import DiffSummary, PlanChange, PlanDiff, PlanResult, Slot
from app.planning.explain import day, plural


def _slot(a) -> Slot:
    return Slot(crew_id=a.crew_id, date=a.date)


def _key(v) -> str:
    return v.job_id or v.site_id


def _state(key, site_id, assigned, unscheduled):
    if key in assigned:
        return assigned[key].state
    u = unscheduled.get(key) or unscheduled.get(site_id)
    return u.state if u else JobState.unscheduled


def diff_plans(before: PlanResult, after: PlanResult) -> PlanDiff:
    """Changes per visit. A one-visit home has a single visit named by its site_id."""
    b = {_key(a): a for a in before.assignments}
    a_ = {_key(a): a for a in after.assignments}
    bu = {_key(u): u for u in before.unscheduled}
    au = {_key(u): u for u in after.unscheduled}
    owner = {
        _key(v): (v.site_id, v.visit_type)
        for v in [*before.assignments, *after.assignments, *before.unscheduled, *after.unscheduled]
    }
    changes: list[PlanChange] = []
    for key in sorted(set(b) | set(a_) | set(bu) | set(au), key=lambda k: (owner[k][0], k)):
        sid, visit_type = owner[key]
        if (
            key == sid
            and visit_type is None
            and any(owner[k][0] == sid and owner[k][1] for k in owner if k != key)
        ):
            continue  # a whole-home unscheduled entry; its visits are compared one by one
        x, y = b.get(key), a_.get(key)
        bs = _state(key, sid, b, bu)
        as_ = _state(key, sid, a_, au)
        what = f"{sid} {visit_type.value.replace('_', ' ')}" if visit_type else sid
        if x and y and (x.crew_id, x.date) != (y.crew_id, y.date):
            note = (
                f"{what} moves from Crew {x.crew_id} {day(x.date)} "
                f"to Crew {y.crew_id} {day(y.date)}."
            )
            if y.days_late:
                note += f" {plural(y.days_late, 'day')} late."
            kind = ChangeKind.moved
        elif x and not y:
            note = f"{what} is no longer scheduled."
            kind = ChangeKind.removed
        elif y and not x:
            note = f"{what} is now scheduled on Crew {y.crew_id} {day(y.date)}."
            kind = ChangeKind.added
        elif bs != as_:
            note = f"{what} changes from {bs.value} to {as_.value}."
            kind = ChangeKind.state_changed
        else:
            continue
        changes.append(
            PlanChange(
                site_id=sid,
                kind=kind,
                before=_slot(x) if x else None,
                after=_slot(y) if y else None,
                before_state=bs,
                after_state=as_,
                note=note,
                job_id=key if visit_type else None,
                visit_type=visit_type,
            )
        )
    ob, oa = before.objective, after.objective
    summary = DiffSummary(
        moved=sum(c.kind == ChangeKind.moved for c in changes),
        added=sum(c.kind == ChangeKind.added for c in changes),
        removed=sum(c.kind == ChangeKind.removed for c in changes),
        newly_late=sum(
            1 for c in changes if c.after_state == JobState.late and c.before_state != JobState.late
        ),
        value_delta_usd=oa.operating_value_usd - ob.operating_value_usd if ob and oa else 0.0,
        travel_delta_min=(oa.travel_allowance_min - ob.travel_allowance_min) if ob and oa else 0,
        customers_to_reschedule=len(
            {c.site_id for c in changes if c.kind in (ChangeKind.moved, ChangeKind.removed)}
        ),
    )
    return PlanDiff(
        before_plan_id=before.plan_id,
        after_plan_id=after.plan_id,
        changes=changes,
        summary=summary,
        headline=headline(summary, after),
    )


def headline(s: DiffSummary, after: PlanResult) -> str:
    if not (s.moved or s.added or s.removed or s.newly_late):
        return "No jobs change."
    parts = []
    two_visit = any(a.visit_type for a in after.assignments)
    if s.moved and two_visit:
        verb = "moves" if s.moved == 1 else "move"
        who = plural(s.customers_to_reschedule or 0, "customer")
        parts.append(f"{plural(s.moved, 'visit')} {verb}, {who} to reschedule.")
    elif s.moved:
        parts.append(f"{plural(s.moved, 'job')} {'moves' if s.moved == 1 else 'move'}.")
    if s.added:
        parts.append(f"{plural(s.added, 'job')} added.")
    if s.removed:
        parts.append(f"{plural(s.removed, 'job')} dropped.")
    if s.newly_late:
        late = [a for a in after.assignments if a.state == JobState.late]
        days = max((a.days_late for a in late), default=0)
        verb = "misses its deadline" if s.newly_late == 1 else "miss their deadlines"
        suffix = f" by {plural(days, 'day')}" if s.newly_late == 1 and days else ""
        parts.append(f"{s.newly_late} {verb}{suffix}.")
    return " ".join(parts)
