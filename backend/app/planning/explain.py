"""Plain-English text for plans, blockers, and diffs."""

import datetime as dt

from app.contracts.enums import ReasonCode
from app.contracts.models import (
    AddCrewDay,
    ChangeReadyDate,
    DelayInventory,
    Edit,
    ForceInclude,
    RemoveCrewDay,
    Scenario,
    Site,
)
from app.contracts.visits import gap_ok, jobs_of, min_gap


def day(d: dt.date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def join_ids(ids: list[str]) -> str:
    if len(ids) <= 2:
        return " and ".join(ids)
    return f"{', '.join(ids[:-1])}, and {ids[-1]}"


def cannot_finish(ids: list[str]) -> str:
    if len(ids) == 1:
        return f"{ids[0]} cannot finish by its deadline."
    return f"{join_ids(ids)} cannot finish by their deadlines."


def blocked_detail(site: Site, reasons: list[ReasonCode], scenario: Scenario) -> str:
    sid = site.site_id
    if ReasonCode.SKILL_MISMATCH in reasons:
        return f"{sid} needs skill {site.required_skill}. No crew has it."
    if ReasonCode.CLUSTER_NOT_ALLOWED in reasons:
        return (
            f"{sid} is in cluster {site.cluster_id}. "
            f"No crew with skill {site.required_skill} works there."
        )
    if ReasonCode.NOT_READY in reasons:
        ready = day(site.ready_date)
        return f"{sid} is ready {ready}. No eligible crew works on or after that day."
    if ReasonCode.NO_INVENTORY in reasons:
        cfg = site.configuration_id
        return f"{sid} needs configuration {cfg}. None arrives in the plan window."
    if ReasonCode.DEADLINE_BEFORE_READY in reasons:
        return f"{sid} is due {day(site.deadline)} but is not ready until {day(site.ready_date)}."
    return f"{sid} has no legal crew-day."


def no_legal_date_detail(site: Site, scenario: Scenario, windows: dict | None = None) -> str:
    """Why a home cannot finish by its deadline: readiness, crews, appointments, or the gap."""
    sid, due = site.site_id, f"{site.site_id} is due {day(site.deadline)}."
    if site.ready_date > site.deadline:
        return f"{sid} is due {day(site.deadline)} but is not ready until {day(site.ready_date)}."
    windows = windows or {}
    jobs = jobs_of(site)
    days = {j.job_id: _legal_days(scenario, site, j) for j in jobs}
    final = jobs[-1]
    by_deadline = [d for d in days[final.job_id] if d <= site.deadline]
    if not by_deadline:
        return f"{due} No crew that serves {site.cluster_id} works on or before that day."
    fitted = {j.job_id: _in_window(days[j.job_id], windows.get(j.job_id)) for j in jobs}
    in_window = [d for d in fitted[final.job_id] if d <= site.deadline]
    if not in_window:
        label = "Its battery day" if final.visit_type else "Its visit"
        return f"{due} {label} has an appointment window {window_text(*windows[final.job_id])}."
    if len(jobs) == 2:
        gap, origin = min_gap(scenario), scenario.config.planning_start
        if not any(gap_ok(i, b, gap, origin) for i in fitted[jobs[0].job_id] for b in in_window):
            return (
                f"{due} Its install must come at least {plural(gap, 'business day')} "
                "before the battery day. No install crew-day fits."
            )
    return f"{due} No legal crew-day remains by then."


def _legal_days(scenario: Scenario, site: Site, job) -> list[dt.date]:
    c = scenario.config
    return sorted(
        {
            cd.date
            for cd in scenario.crew_days
            if c.planning_start <= cd.date <= c.planning_end
            and cd.date >= site.ready_date
            and job.required_skill in cd.skills
            and site.cluster_id in cd.allowed_clusters
        }
    )


def _in_window(days: list[dt.date], window) -> list[dt.date]:
    if window is None:
        return days
    start, end = window
    return [d for d in days if d >= start and (end is None or d <= end)]


def window_text(start: dt.date, end: dt.date | None) -> str:
    return f"from {day(start)}" if end is None else f"from {day(start)} to {day(end)}"


def window_detail(what: str, start: dt.date, end: dt.date | None) -> str:
    window = window_text(start, end)
    return f"{what} has an appointment window {window}. No eligible crew works in it."


def visit_label(job) -> str:
    """'' for one-visit homes, else ' install' or ' battery day'."""
    if job is None or job.visit_type is None:
        return ""
    return " install" if job.visit_type == "install" else " battery day"


def unscheduled_detail(site: Site, job=None) -> str:
    return (
        f"{site.site_id}{visit_label(job)} is not in the best recovery. "
        "No single hard blocker applies. Force it in to see what it displaces."
    )


def describe_edit(e: Edit) -> str:
    match e:
        case RemoveCrewDay():
            return f"Crew {e.crew_id} is out {day(e.date)}."
        case AddCrewDay():
            return f"Crew {e.crew_id} is added on {day(e.date)}."
        case DelayInventory():
            qty = "All units" if e.quantity is None else plural(e.quantity, "unit")
            return (
                f"{qty} of {e.configuration_id} due {day(e.from_date)} "
                f"arrive {day(e.to_date)} instead."
            )
        case ChangeReadyDate():
            return f"{e.site_id} is now ready {day(e.ready_date)}."
        case ForceInclude():
            return f"{e.site_id} must finish by its deadline."
    return ""


def describe_edits(scenario: Scenario, edits: list[Edit]) -> str:
    return " ".join(describe_edit(e) for e in edits)
