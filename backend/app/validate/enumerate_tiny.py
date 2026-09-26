"""Exhaustive oracle for small scenarios, independent of the scheduling solver."""

from dataclasses import dataclass
from itertools import product
from math import prod

from app.contracts.models import Assignment, ObjectiveComponents, Scenario


@dataclass(frozen=True)
class EnumerationResult:
    assignments: list[Assignment]
    objective: ObjectiveComponents
    key: tuple
    optimal_count: int


def enumerate_tiny(
    scenario: Scenario, mode="strict", force_include=(), *, values=None, max_combinations=2_000_000
) -> EnumerationResult | None:
    """Return the proven lexicographic optimum, or None when infeasible.

    Caller applies resource edits first. Forced jobs must finish by deadline.
    Exhaustive search is deliberately bounded and is not a production planner.
    """
    if len(scenario.sites) > 10:
        raise ValueError("Exhaustive enumeration supports at most ten jobs")
    if mode not in ("strict", "recovery"):
        raise ValueError("Unknown planning mode")
    if values is None:
        from app.valuation.value_table import value_table

        values = {(r.site_id, r.install_date): r.value_usd for r in value_table(scenario)}
    forced = set(force_include)
    if not forced <= {s.site_id for s in scenario.sites}:
        raise ValueError("Unknown forced site")
    locks = {p.site_id: (p.crew_id, p.date) for p in scenario.current_plan if p.locked}
    travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
    crews = {(c.crew_id, c.date): c for c in scenario.crew_days}
    options, blocked, possible_values = [], set(), []
    for site in scenario.sites:
        eligible = [
            (c.crew_id, c.date)
            for c in scenario.crew_days
            if scenario.config.planning_start <= c.date <= scenario.config.planning_end
            and c.date >= site.ready_date
            and site.required_skill in c.skills
            and site.cluster_id in c.allowed_clusters
        ]
        possible_values.extend(values.get((site.site_id, d), 0.0) for _, d in eligible)
        if not eligible:
            blocked.add(site.site_id)
        slots = [
            slot
            for slot in eligible
            if (mode == "recovery" and site.site_id not in forced) or slot[1] <= site.deadline
        ]
        if site.site_id in locks:
            slots = [slot for slot in slots if slot == locks[site.site_id]]
        elif site.site_id not in forced and (mode == "recovery" or not eligible):
            slots.append(None)
        if not slots:
            return None
        options.append(slots)
    if prod(len(o) for o in options) > max_combinations:
        raise ValueError("Exhaustive search exceeds the combination budget")
    best, count = None, 0
    for combination in product(*options):
        groups, consumption, assignments = {}, {}, []
        feasible = True
        for site, slot in zip(scenario.sites, combination, strict=True):
            if slot is None:
                continue
            cluster, minutes = groups.get(slot, (site.cluster_id, 0))
            minutes += site.duration_min
            if cluster != site.cluster_id or minutes + travel[cluster] > crews[slot].available_min:
                feasible = False
                break
            groups[slot] = (cluster, minutes)
            consumption.setdefault(site.configuration_id, []).append(slot[1])
            days_late = max(0, (slot[1] - site.deadline).days)
            assignments.append(
                Assignment(
                    site_id=site.site_id,
                    crew_id=slot[0],
                    date=slot[1],
                    days_late=days_late,
                    state="locked"
                    if site.site_id in locks
                    else ("late" if days_late else "scheduled"),
                    value_usd=values.get((site.site_id, slot[1]), 0.0),
                )
            )
        if not feasible:
            continue
        for cfg, dates in consumption.items():
            for day in set(dates):
                got = sum(
                    r.quantity
                    for r in scenario.inventory
                    if r.configuration_id == cfg and r.available_date <= day
                )
                if sum(d <= day for d in dates) > got:
                    feasible = False
                    break
        if not feasible:
            continue
        by_site = {a.site_id: (a.crew_id, a.date) for a in assignments}
        unscheduled = len(scenario.sites) - len(assignments)
        n_late = sum(a.days_late > 0 for a in assignments)
        delay = sum(a.days_late for a in assignments)
        value = sum(a.value_usd for a in assignments)
        changes = sum(
            not p.locked and by_site.get(p.site_id) != (p.crew_id, p.date)
            for p in scenario.current_plan
        )
        travel_minutes = sum(travel[cluster] for cluster, _ in groups.values())
        prefix = (
            (
                n_late + unscheduled - len(blocked),
                delay + (unscheduled - len(blocked)) * scenario.config.unscheduled_penalty_days,
            )
            if mode == "recovery"
            else ()
        )
        value_key = (
            (-sum(round(a.value_usd * 100) for a in assignments),)
            if scenario.config.objective_policy == "value_aware"
            else ()
        )
        key = (*prefix, changes, *value_key, travel_minutes)
        if best is not None and key > best.key:
            continue
        if best is not None and key == best.key:
            count += 1
            continue
        capacity = sum(c.available_min for c in scenario.crew_days)
        used = sum(minutes for _, minutes in groups.values()) + travel_minutes
        objective = ObjectiveComponents(
            jobs_on_time=len(assignments) - n_late,
            jobs_late=n_late,
            jobs_unscheduled=unscheduled,
            jobs_blocked=len(blocked),
            total_delay_days=delay,
            operating_value_usd=value,
            changed_installs=changes,
            travel_allowance_min=travel_minutes,
            crew_utilization=used / capacity if capacity else 0,
            value_distinguishes_choices=bool(
                possible_values and max(possible_values) - min(possible_values) > 1e-9
            ),
        )
        best = EnumerationResult(assignments, objective, key, 1)
        count = 1
    if best is None:
        return None
    return EnumerationResult(best.assignments, best.objective, best.key, count)
