"""Semantic input checks, separate from planning feasibility."""

from collections import Counter
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from app.contracts.models import InputIssue, Scenario


def validate_inputs(scenario: Scenario) -> list[InputIssue]:
    # Models can be mutated after loading (Pydantic does not validate assignment).
    # Revalidate their contents before semantic checks or arithmetic.
    try:
        Scenario.model_validate(scenario.model_dump(warnings=False))
    except ValidationError as exc:
        return [
            InputIssue(code="BAD_VALUE", message=f"{'.'.join(map(str, e['loc']))}: {e['msg']}")
            for e in exc.errors()
        ]
    issues = []

    def add(code, message, file=None):
        issues.append(InputIssue(code=code, message=message, file=file))

    for rows, key, file in (
        (scenario.sites, lambda x: x.site_id, "sites.csv"),
        (scenario.clusters, lambda x: x.cluster_id, "clusters.geojson"),
        (scenario.config.batteries, lambda x: x.configuration_id, "scenario.yaml"),
        (scenario.crew_days, lambda x: (x.crew_id, x.date), "crew_days.csv"),
    ):
        for identifier, count in Counter(key(x) for x in rows).items():
            if count > 1:
                add("DUPLICATE_ID", f"Duplicate ID: {identifier}", file)
    cfg = scenario.config
    if not cfg.planning_start <= cfg.planning_end <= cfg.evaluation_end:
        add("DATE_ORDER", "Require planning_start <= planning_end <= evaluation_end")
    if cfg.unscheduled_penalty_days <= (cfg.planning_end - cfg.planning_start).days:
        add("BAD_VALUE", "Unscheduled penalty must exceed within-horizon lateness")
    try:
        ZoneInfo(cfg.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        add("BAD_VALUE", "Unknown scheduling timezone")
    batteries = {b.configuration_id for b in cfg.batteries}
    clusters = {c.cluster_id for c in scenario.clusters}
    sites = {s.site_id: s for s in scenario.sites}
    crew_days = {(c.crew_id, c.date): c for c in scenario.crew_days}
    for b in cfg.batteries:
        if not (
            0 <= b.reserve_kwh <= b.capacity_kwh
            and b.capacity_kwh > 0
            and 0 < b.eta_charge <= 1
            and 0 < b.eta_discharge <= 1
        ):
            add("BAD_VALUE", f"Invalid battery energy or efficiency: {b.configuration_id}")
    for c in scenario.clusters:
        if len(c.outline) < 4 or c.outline[0] != c.outline[-1]:
            add("BAD_VALUE", f"Cluster {c.cluster_id} needs a closed polygon ring")
        if any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in c.outline):
            add("BAD_VALUE", f"Invalid cluster coordinates: {c.cluster_id}")
    for s in scenario.sites:
        if s.cluster_id not in clusters or s.configuration_id not in batteries:
            add("UNKNOWN_REFERENCE", f"Unknown cluster or battery for {s.site_id}", "sites.csv")
        if not (-180 <= s.lon <= 180 and -90 <= s.lat <= 90) or s.duration_min <= 0:
            add("BAD_VALUE", f"Invalid coordinates or duration: {s.site_id}", "sites.csv")
        # Ready-after-deadline is intentionally a valid planning case.
        if s.deadline < cfg.planning_start:
            if cfg.unscheduled_penalty_days <= (cfg.planning_end - s.deadline).days:
                add("BAD_VALUE", f"Unscheduled penalty is too small for {s.site_id}")
    for c in scenario.crew_days:
        if not set(c.allowed_clusters) <= clusters:
            add("UNKNOWN_REFERENCE", f"Unknown allowed cluster for {c.crew_id}")
        if not cfg.planning_start <= c.date <= cfg.planning_end:
            add("DATE_ORDER", f"Crew-day outside planning horizon: {c.crew_id}, {c.date}")
    for receipt in scenario.inventory:
        if receipt.configuration_id not in batteries:
            add("UNKNOWN_REFERENCE", f"Unknown inventory battery {receipt.configuration_id}")
    for sid, count in Counter(p.site_id for p in scenario.current_plan).items():
        if count > 1:
            add("DUPLICATE_PLANNED_INSTALL", f"Multiple current installs for {sid}")
    locks = []
    for p in scenario.current_plan:
        site, crew = sites.get(p.site_id), crew_days.get((p.crew_id, p.date))
        if site is None or crew is None:
            add("UNKNOWN_REFERENCE", f"Unknown site or crew-day in current plan: {p.site_id}")
        if p.locked:
            locks.append(p)
            if (
                site is None
                or crew is None
                or p.date < site.ready_date
                or not cfg.planning_start <= p.date <= cfg.planning_end
                or site.required_skill not in crew.skills
                or site.cluster_id not in crew.allowed_clusters
            ):
                add("CONTRADICTORY_LOCKS", f"Locked install has no legal slot: {p.site_id}")
    for sid, count in Counter(p.site_id for p in locks).items():
        if count > 1:
            add("CONTRADICTORY_LOCKS", f"Multiple locks for {sid}")
    for key, crew in crew_days.items():
        locked_sites = [
            sites[p.site_id] for p in locks if (p.crew_id, p.date) == key and p.site_id in sites
        ]
        used_clusters = {s.cluster_id for s in locked_sites}
        travel = sum(
            c.travel_allowance_min for c in scenario.clusters if c.cluster_id in used_clusters
        )
        if (
            len(used_clusters) > 1
            or sum(s.duration_min for s in locked_sites) + travel > crew.available_min
        ):
            add("CONTRADICTORY_LOCKS", f"Locks exceed crew-day capacity or clusters: {key}")
    for p in locks:
        if p.site_id not in sites:
            continue
        battery = sites[p.site_id].configuration_id
        used = sum(
            q.date <= p.date and q.site_id in sites and sites[q.site_id].configuration_id == battery
            for q in locks
        )
        available = sum(
            r.quantity
            for r in scenario.inventory
            if r.configuration_id == battery and r.available_date <= p.date
        )
        if used > available:
            add("CONTRADICTORY_LOCKS", f"Locked installs exceed {battery} inventory on {p.date}")
    return issues
