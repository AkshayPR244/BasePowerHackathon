"""Apply disruptions and interventions to a scenario."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.contracts.enums import InputIssueCode
from app.contracts.hashing import scenario_hash
from app.contracts.models import (
    AddCrewDay,
    ChangeReadyDate,
    CrewDay,
    DelayInventory,
    Edit,
    ForceInclude,
    InputIssue,
    InventoryReceipt,
    RemoveCrewDay,
    Scenario,
)


@dataclass
class Edited:
    scenario: Scenario
    forced: set[str] = field(default_factory=set)
    issues: list[InputIssue] = field(default_factory=list)


def _issue(code: InputIssueCode, message: str) -> InputIssue:
    return InputIssue(code=code, message=message, file="edits")


def apply_edits(base: Scenario, edits: Sequence[Edit]) -> Edited:
    crew_days = list(base.crew_days)
    inventory = list(base.inventory)
    sites = {s.site_id: s for s in base.sites}
    forced: set[str] = set()
    issues: list[InputIssue] = []

    for e in edits:
        match e:
            case RemoveCrewDay():
                keep = [c for c in crew_days if (c.crew_id, c.date) != (e.crew_id, e.date)]
                if len(keep) == len(crew_days):
                    issues.append(
                        _issue(
                            InputIssueCode.UNKNOWN_REFERENCE,
                            f"Crew {e.crew_id} has no working day on {e.date}.",
                        )
                    )
                crew_days = keep
            case AddCrewDay():
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

    edited = base.model_copy(
        update={
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
