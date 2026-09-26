"""Changelog-style diff between two plans."""

from app.contracts.enums import ChangeKind, JobState
from app.contracts.models import DiffSummary, PlanChange, PlanDiff, PlanResult, Slot
from app.planning.explain import day, plural


def _slot(a) -> Slot:
    return Slot(crew_id=a.crew_id, date=a.date)


def diff_plans(before: PlanResult, after: PlanResult) -> PlanDiff:
    b = {a.site_id: a for a in before.assignments}
    a_ = {a.site_id: a for a in after.assignments}
    bu = {u.site_id: u for u in before.unscheduled}
    au = {u.site_id: u for u in after.unscheduled}
    changes: list[PlanChange] = []
    for sid in sorted(set(b) | set(a_) | set(bu) | set(au)):
        x, y = b.get(sid), a_.get(sid)
        bs = x.state if x else bu[sid].state if sid in bu else JobState.unscheduled
        as_ = y.state if y else au[sid].state if sid in au else JobState.unscheduled
        if x and y and (x.crew_id, x.date) != (y.crew_id, y.date):
            note = (
                f"{sid} moves from Crew {x.crew_id} {day(x.date)} "
                f"to Crew {y.crew_id} {day(y.date)}."
            )
            if y.days_late:
                note += f" {plural(y.days_late, 'day')} late."
            kind = ChangeKind.moved
        elif x and not y:
            note = f"{sid} is no longer scheduled."
            kind = ChangeKind.removed
        elif y and not x:
            note = f"{sid} is now scheduled on Crew {y.crew_id} {day(y.date)}."
            kind = ChangeKind.added
        elif bs != as_:
            note = f"{sid} changes from {bs.value} to {as_.value}."
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
    if s.moved:
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
