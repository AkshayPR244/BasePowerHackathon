"""Apply disruptions and interventions to a scenario."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.contracts.enums import InputIssueCode
from app.contracts.hashing import scenario_hash
from app.contracts.models import (
    AddCrewDay,
    ChangeAppointment,
    ChangeReadyDate,
    CrewDay,
    DelayInventory,
    Edit,
    ExtendCrewDay,
    ForceInclude,
    InputIssue,
    InventoryReceipt,
    MoveVisit,
    PinVisit,
    PlannedInstall,
    ReduceCrewDay,
    RemoveCrewDay,
    Scenario,
)
from app.contracts.visits import all_jobs, job_of_row, jobs_of


@dataclass
class Edited:
    scenario: Scenario
    forced: set[str] = field(default_factory=set)
    issues: list[InputIssue] = field(default_factory=list)


GRANTED = "overtime_granted"  # config parameter prefix: "overtime_granted:<crew>:<date>"
SKILL_WORDS = {"install": "installs", "battery": "battery days"}


def _issue(code: InputIssueCode, message: str) -> InputIssue:
    return InputIssue(code=code, message=message, file="edits")


def granted_overtime(scenario: Scenario) -> dict[tuple, int]:
    """Overtime already approved into this scenario's crew-days, per (crew_id, date)."""
    out: dict[tuple, int] = {}
    for p in scenario.config.parameters:
        if p.name.startswith(GRANTED + ":"):
            _, crew, day = p.name.split(":", 2)
            out[crew, dt.date.fromisoformat(day)] = int(float(p.value))
    return out


def _day(d: dt.date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def apply_edits(base: Scenario, edits: Sequence[Edit]) -> Edited:
    crew_days = list(base.crew_days)
    inventory = list(base.inventory)
    sites = {s.site_id: s for s in base.sites}
    overtime: dict[tuple, int] = {}
    current = list(base.current_plan)
    jobs = all_jobs(base)
    by_site = {s.site_id: jobs_of(s) for s in base.sites}
    forced: set[str] = set()
    issues: list[InputIssue] = []
    removed: set[tuple] = set()
    granted = granted_overtime(base)

    for e in edits:
        match e:
            case RemoveCrewDay():
                keep = [c for c in crew_days if (c.crew_id, c.date) != (e.crew_id, e.date)]
                removed.add((e.crew_id, e.date))
                if len(keep) == len(crew_days):
                    issues.append(
                        _issue(
                            InputIssueCode.UNKNOWN_REFERENCE,
                            f"Crew {e.crew_id} has no working day on {e.date}.",
                        )
                    )
                crew_days = keep
            case AddCrewDay():
                if not base.config.planning_start <= e.date <= base.config.planning_end:
                    issues.append(
                        _issue(
                            InputIssueCode.DATE_ORDER, "Crew date is outside the planning window."
                        )
                    )
                    continue
                if not set(e.allowed_clusters) <= {c.cluster_id for c in base.clusters}:
                    issues.append(_issue(InputIssueCode.UNKNOWN_REFERENCE, "Unknown crew cluster."))
                    continue
                if (e.crew_id, e.date) in removed:
                    issues.append(
                        _issue(
                            InputIssueCode.BAD_VALUE,
                            f"Crew {e.crew_id} is out on {_day(e.date)}. "
                            "Temporary capacity must be a different crew.",
                        )
                    )
                    continue
                normal = max(
                    (c.available_min for c in base.crew_days if set(c.skills) & set(e.skills)),
                    default=max((c.available_min for c in base.crew_days), default=480),
                )
                if e.available_min > normal:
                    issues.append(
                        _issue(
                            InputIssueCode.BAD_VALUE,
                            f"A temporary crew-day can have at most {normal} minutes, "
                            "one normal day.",
                        )
                    )
                    continue
                if any((c.crew_id, c.date) == (e.crew_id, e.date) for c in crew_days):
                    issues.append(
                        _issue(
                            InputIssueCode.DUPLICATE_ID,
                            f"Crew {e.crew_id} already works on {e.date}.",
                        )
                    )
                    continue
                crew_days.append(
                    CrewDay(
                        crew_id=e.crew_id,
                        date=e.date,
                        available_min=e.available_min,
                        skills=sorted(e.skills),
                        allowed_clusters=sorted(e.allowed_clusters),
                    )
                )
            case DelayInventory():
                inventory, err = _delay(inventory, e)
                if err:
                    issues.append(err)
            case ChangeReadyDate():
                if e.site_id not in sites:
                    issues.append(_issue(InputIssueCode.UNKNOWN_REFERENCE, f"No site {e.site_id}."))
                    continue
                sites[e.site_id] = sites[e.site_id].model_copy(update={"ready_date": e.ready_date})
            case ForceInclude():
                if e.site_id not in sites:
                    issues.append(_issue(InputIssueCode.UNKNOWN_REFERENCE, f"No site {e.site_id}."))
                    continue
                forced.add(e.site_id)
            case ReduceCrewDay() | ExtendCrewDay():
                index = next(
                    (
                        i
                        for i, c in enumerate(crew_days)
                        if (c.crew_id, c.date) == (e.crew_id, e.date)
                    ),
                    None,
                )
                if index is None:
                    issues.append(
                        _issue(InputIssueCode.UNKNOWN_REFERENCE, "Crew-day does not exist.")
                    )
                    continue
                cd = crew_days[index]
                if isinstance(e, ReduceCrewDay):
                    if e.available_min > cd.available_min:
                        issues.append(
                            _issue(
                                InputIssueCode.BAD_VALUE,
                                "Reduced capacity cannot increase availability.",
                            )
                        )
                        continue
                    minutes = e.available_min
                else:
                    original = next(
                        (
                            c.available_min
                            for c in base.crew_days
                            if (c.crew_id, c.date) == (e.crew_id, e.date)
                        ),
                        cd.available_min,
                    )
                    cap = next(
                        (
                            float(p.value)
                            for p in base.config.parameters
                            if p.name == "max_overtime_min"
                        ),
                        120,
                    )
                    minutes = cd.available_min + e.extra_min
                    slot = (e.crew_id, e.date)
                    already = granted.get(slot, 0)
                    requested = overtime.get(slot, 0) + e.extra_min
                    if already + requested > cap or minutes > original - already + cap:
                        issues.append(
                            _issue(
                                InputIssueCode.BAD_VALUE,
                                f"Overtime exceeds {cap:g} minutes per crew-day.",
                            )
                        )
                        continue
                if isinstance(e, ExtendCrewDay):
                    overtime[slot] = requested
                crew_days[index] = cd.model_copy(update={"available_min": minutes})
            case ChangeAppointment():
                if e.job_id not in jobs:
                    issues.append(
                        _issue(InputIssueCode.UNKNOWN_REFERENCE, f"Unknown visit {e.job_id}.")
                    )
                elif e.available_to is not None and e.available_to < e.available_from:
                    issues.append(
                        _issue(InputIssueCode.DATE_ORDER, "Appointment ends before it starts.")
                    )
            case PinVisit() | MoveVisit():
                job = jobs.get(e.job_id)
                if job is None:
                    issues.append(
                        _issue(InputIssueCode.UNKNOWN_REFERENCE, f"Unknown visit {e.job_id}.")
                    )
                    continue
                old = next((p for p in current if job_of_row(p, by_site) == e.job_id), None)
                if isinstance(e, PinVisit):
                    if old is None:
                        issues.append(
                            _issue(
                                InputIssueCode.UNKNOWN_REFERENCE, "Cannot pin an unbooked visit."
                            )
                        )
                        continue
                    row = old.model_copy(update={"locked": True})
                else:
                    if old and old.locked and (old.crew_id, old.date) != (e.crew_id, e.date):
                        issues.append(
                            _issue(InputIssueCode.BAD_VALUE, "Cannot move a locked visit.")
                        )
                        continue
                    target = next(
                        (c for c in crew_days if (c.crew_id, c.date) == (e.crew_id, e.date)), None
                    )
                    if target is None:
                        issues.append(
                            _issue(
                                InputIssueCode.UNKNOWN_REFERENCE,
                                f"Crew {e.crew_id} does not work on {_day(e.date)}.",
                            )
                        )
                        continue
                    if job.required_skill not in target.skills:
                        what = SKILL_WORDS.get(job.required_skill, f"{job.required_skill} visits")
                        msg = f"Crew {e.crew_id} does not do {what}."
                        issues.append(_issue(InputIssueCode.BAD_VALUE, msg))
                        continue
                    cluster = sites[job.site_id].cluster_id
                    if cluster not in target.allowed_clusters:
                        issues.append(
                            _issue(
                                InputIssueCode.BAD_VALUE,
                                f"Crew {e.crew_id} does not work in cluster {cluster}.",
                            )
                        )
                        continue
                    row = PlannedInstall(
                        site_id=job.site_id,
                        job_id=job.assignment_job_id,
                        crew_id=e.crew_id,
                        date=e.date,
                        locked=True,
                    )
                current = [p for p in current if job_of_row(p, by_site) != e.job_id] + [row]

    edited = base.model_copy(
        update={
            "current_plan": current,
            "crew_days": sorted(crew_days, key=lambda c: (c.date, c.crew_id)),
            "inventory": sorted(inventory, key=lambda r: (r.available_date, r.configuration_id)),
            "sites": [sites[s.site_id] for s in base.sites],
        }
    )
    edited = edited.model_copy(update={"scenario_hash": scenario_hash(base, edits)})
    return Edited(scenario=edited, forced=forced, issues=issues)


def _delay(
    inventory: list[InventoryReceipt], e: DelayInventory
) -> tuple[list[InventoryReceipt], InputIssue | None]:
    if e.to_date < e.from_date:
        return inventory, _issue(
            InputIssueCode.DATE_ORDER, f"Cannot delay inventory from {e.from_date} to {e.to_date}."
        )
    hits = [
        r
        for r in inventory
        if r.configuration_id == e.configuration_id and r.available_date == e.from_date
    ]
    if not hits:
        return inventory, _issue(
            InputIssueCode.UNKNOWN_REFERENCE,
            f"No {e.configuration_id} receipt on {e.from_date}.",
        )
    total = sum(r.quantity for r in hits)
    moved = total if e.quantity is None else e.quantity
    if moved > total:
        return inventory, _issue(
            InputIssueCode.BAD_VALUE,
            f"Cannot delay {moved} units. Only {total} arrive on {e.from_date}.",
        )
    rest = [r for r in inventory if r not in hits]
    if total - moved:
        rest.append(hits[0].model_copy(update={"quantity": total - moved}))
    merged: dict = {}
    for r in [*rest, hits[0].model_copy(update={"available_date": e.to_date, "quantity": moved})]:
        key = (r.configuration_id, r.available_date)
        merged[key] = merged.get(key, 0) + r.quantity
    rest = [
        InventoryReceipt(configuration_id=cfg, available_date=d, quantity=q)
        for (cfg, d), q in merged.items()
    ]
    return rest, None


def appointment_windows(edits):
    """Last appointment edit wins; bounds are inclusive and specific to one visit."""
    return {
        e.job_id: (e.available_from, e.available_to)
        for e in edits
        if isinstance(e, ChangeAppointment)
    }


def restrict_appointments(elig, edits):
    for jid, (start, end) in appointment_windows(edits).items():
        for slots in (elig.options, elig.any_option):
            if jid in slots:
                slots[jid] = [
                    (crew, day)
                    for crew, day in slots[jid]
                    if day >= start and (end is None or day <= end)
                ]
    return elig
