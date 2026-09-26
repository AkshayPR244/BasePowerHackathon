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


def day(d: dt.date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


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


def no_legal_date_detail(site: Site, scenario: Scenario) -> str:
    if site.ready_date > site.deadline:
        return (
            f"{site.site_id} is due {day(site.deadline)} but is not ready until "
            f"{day(site.ready_date)}."
        )
    return (
        f"{site.site_id} is due {day(site.deadline)}. No crew that serves "
        f"{site.cluster_id} works on or before that day."
    )


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
