"""Exhaustive oracle for small scenarios, independent of the scheduling solver."""

from dataclasses import dataclass
from itertools import product
from math import prod

from app.contracts.models import Assignment, ObjectiveComponents, Scenario
from app.contracts.visits import gap_ok, job_of_row, jobs_of, min_gap


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

    Caller applies resource edits first. Forced homes must finish by deadline.
    Exhaustive search is deliberately bounded and is not a production planner.
    """
    jobs = [j for site in scenario.sites for j in jobs_of(site)]
    if len(jobs) > 10:
        raise ValueError("Exhaustive enumeration supports at most ten visits")
    if mode not in ("strict", "recovery"):
        raise ValueError("Unknown planning mode")
    if values is None:
        from app.valuation.value_table import value_table

        values = {(r.site_id, r.install_date): r.value_usd for r in value_table(scenario)}
    forced = set(force_include)
    sites = {s.site_id: s for s in scenario.sites}
    if not forced <= set(sites):
        raise ValueError("Unknown forced site")
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}
    locks = {}
    for p in scenario.current_plan:
        if p.locked and (job := job_of_row(p, by_site)):
            locks[job] = (p.crew_id, p.date)
    gap, origin = min_gap(scenario), scenario.config.planning_start
    travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
    crews = {(c.crew_id, c.date): c for c in scenario.crew_days}

    def eligible(job):
        site = sites[job.site_id]
        return [
            (c.crew_id, c.date)
            for c in scenario.crew_days
            if scenario.config.planning_start <= c.date <= scenario.config.planning_end
            and c.date >= site.ready_date
            and job.required_skill in c.skills
            and site.cluster_id in c.allowed_clusters
        ]

    blocked, possible_values = set(), []
    for site in scenario.sites:
        slots = [eligible(j) for j in by_site[site.site_id]]
        possible_values.extend(values.get((site.site_id, d), 0.0) for _, d in slots[-1])
        no_pair = len(slots) == 2 and not any(
            gap_ok(i[1], b[1], gap, origin) for i in slots[0] for b in slots[1]
        )
        if any(not x for x in slots) or no_pair:
            blocked.add(site.site_id)
    options = []
    for job in jobs:
        site = sites[job.site_id]
        if site.site_id in blocked:
            slots = []
        else:
            slots = [
                slot
                for slot in eligible(job)
                if not job.final
                or (mode == "recovery" and site.site_id not in forced)
                or slot[1] <= site.deadline
            ]
        if job.job_id in locks:
            slots = [slot for slot in slots if slot == locks[job.job_id]]
        elif site.site_id not in forced and (mode == "recovery" or site.site_id in blocked):
            slots.append(None)
        if not slots:
            return None
        options.append(slots)
    if prod(len(o) for o in options) > max_combinations:
        raise ValueError("Exhaustive search exceeds the combination budget")
    best, count = None, 0
    for combination in product(*options):
        chosen = dict(zip((j.job_id for j in jobs), combination, strict=True))
        if not _precedence_ok(by_site, chosen, gap, origin):
            continue
        groups, consumption, assignments, finals = {}, {}, [], []
        feasible = True
        for job, slot in zip(jobs, combination, strict=True):
            if slot is None:
                continue
            site = sites[job.site_id]
            cluster, minutes = groups.get(slot, (site.cluster_id, 0))
            minutes += job.duration_min
            if cluster != site.cluster_id or minutes + travel[cluster] > crews[slot].available_min:
                feasible = False
                break
            groups[slot] = (cluster, minutes)
            days_late = max(0, (slot[1] - site.deadline).days) if job.final else 0
            a = Assignment(
                site_id=site.site_id,
                crew_id=slot[0],
                date=slot[1],
                days_late=days_late,
                state="locked" if job.job_id in locks else ("late" if days_late else "scheduled"),
                value_usd=values.get((site.site_id, slot[1]), 0.0) if job.final else 0.0,
                job_id=job.assignment_job_id,
                visit_type=job.visit_type,
            )
            assignments.append(a)
            if job.final:
                finals.append(a)
                consumption.setdefault(site.configuration_id, []).append(slot[1])
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
        unscheduled = len(scenario.sites) - len(finals)
        n_late = sum(a.days_late > 0 for a in finals)
        delay = sum(a.days_late for a in finals)
        value = sum(a.value_usd for a in finals)
        changes = sum(
            not p.locked and chosen.get(job_of_row(p, by_site)) != (p.crew_id, p.date)
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
            (-sum(round(a.value_usd * 100) for a in finals),)
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
            jobs_on_time=len(finals) - n_late,
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


def _precedence_ok(by_site, chosen, gap, origin) -> bool:
    for pair in by_site.values():
        if len(pair) != 2:
            continue
        first, last = (chosen[j.job_id] for j in pair)
        if last is not None and (first is None or not gap_ok(first[1], last[1], gap, origin)):
            return False
    return True
