"""Independently recompute plan constraints; no scheduling-model helpers are used.

For a no-incumbent response, validate its empty-result shape, not the solver's
infeasibility claim. The caller must pass the scenario with edits already applied.
"""

from collections import Counter, defaultdict
from math import isclose

from app.contracts.models import (
    Assignment,
    CrewDayUsage,
    ObjectiveComponents,
    PlanResult,
    Scenario,
    ValidationIssue,
    ValidationReport,
)


def legal_slots(scenario: Scenario, site) -> list:
    """Eligibility before deadline filtering, independent of competing jobs."""
    return [
        c
        for c in scenario.crew_days
        if scenario.config.planning_start <= c.date <= scenario.config.planning_end
        and c.date >= site.ready_date
        and site.required_skill in c.skills
        and site.cluster_id in c.allowed_clusters
    ]


def recompute_usage(scenario: Scenario, assignments: list[Assignment]) -> list[CrewDayUsage]:
    sites = {s.site_id: s for s in scenario.sites}
    clusters = {c.cluster_id: c for c in scenario.clusters}
    result = []
    for cd in scenario.crew_days:
        jobs = [
            sites[a.site_id]
            for a in assignments
            if a.site_id in sites and (a.crew_id, a.date) == (cd.crew_id, cd.date)
        ]
        used = {s.cluster_id for s in jobs}
        result.append(
            CrewDayUsage(
                crew_id=cd.crew_id,
                date=cd.date,
                cluster_id=next(iter(used)) if len(used) == 1 else None,
                onsite_min=sum(s.duration_min for s in jobs),
                travel_min=sum(clusters[k].travel_allowance_min for k in used),
                available_min=cd.available_min,
            )
        )
    return result


def recompute_objective(scenario: Scenario, assignments: list[Assignment], *, values=None):
    """Revalue assignments from the source table, never from claimed dollar fields."""
    if values is None:
        from app.valuation.value_table import value_table

        values = {(r.site_id, r.install_date): r.value_usd for r in value_table(scenario)}
    sites = {s.site_id: s for s in scenario.sites}
    known = [a for a in assignments if a.site_id in sites]
    by_site = {a.site_id: a for a in known}
    blocked = {s.site_id for s in scenario.sites if not legal_slots(scenario, s)}
    late = [max(0, (a.date - sites[a.site_id].deadline).days) for a in known]
    usage = recompute_usage(scenario, known)
    available = sum(c.available_min for c in scenario.crew_days)
    used = sum(u.onsite_min + u.travel_min for u in usage)
    changed = sum(
        not p.locked
        and (
            p.site_id not in by_site
            or (by_site[p.site_id].crew_id, by_site[p.site_id].date) != (p.crew_id, p.date)
        )
        for p in scenario.current_plan
    )
    candidates = [
        values.get((s.site_id, c.date), 0.0)
        for s in scenario.sites
        for c in legal_slots(scenario, s)
    ]
    return ObjectiveComponents(
        jobs_on_time=sum(d == 0 for d in late),
        jobs_late=sum(d > 0 for d in late),
        jobs_unscheduled=len(set(sites) - set(by_site)),
        jobs_blocked=len(blocked - set(by_site)),
        total_delay_days=sum(late),
        operating_value_usd=sum(values.get((a.site_id, a.date), 0.0) for a in known),
        changed_installs=changed,
        travel_allowance_min=sum(u.travel_min for u in usage),
        crew_utilization=min(1.0, used / available) if available else 0.0,
        value_distinguishes_choices=bool(candidates and max(candidates) - min(candidates) > 1e-9),
    )


def validate_plan(scenario: Scenario, result: PlanResult) -> ValidationReport:
    issues = []

    def add(code, message, site_id=None, crew_id=None, date=None):
        issues.append(
            ValidationIssue(code=code, message=message, site_id=site_id, crew_id=crew_id, date=date)
        )

    if result.scenario_id != scenario.scenario_id:
        add("STATE_MISMATCH", "Result and scenario IDs differ")

    if result.status not in ("optimal", "feasible"):
        if result.assignments or result.crew_days:
            add("STATE_MISMATCH", "A response without an incumbent cannot contain a plan")
        if result.objective is not None:
            add("OBJECTIVE_MISMATCH", "A response without an incumbent has no objective")
        return ValidationReport(
            checked=True,
            valid=not issues,
            issues=issues,
            validator="independent-v1:no-incumbent-shape",
        )

    sites = {s.site_id: s for s in scenario.sites}
    crews = {(c.crew_id, c.date): c for c in scenario.crew_days}
    locks = {p.site_id: p for p in scenario.current_plan if p.locked}
    forced = {e.site_id for e in result.edits if e.kind == "force_include"}
    assigned = {a.site_id: a for a in result.assignments}
    unscheduled = {u.site_id: u for u in result.unscheduled}
    blocked = {s.site_id for s in scenario.sites if not legal_slots(scenario, s)}
    all_ids = [a.site_id for a in result.assignments] + [u.site_id for u in result.unscheduled]
    for sid, count in Counter(all_ids).items():
        if sid not in sites:
            add("UNKNOWN_SITE", f"Unknown site {sid}", sid)
        if count > 1:
            add("DUPLICATE_ASSIGNMENT", f"Site {sid} appears more than once", sid)
    for sid in sites:
        if sid not in assigned and sid not in unscheduled:
            add("MISSING_JOB", "Job is absent from assignments and unscheduled list", sid)
        if sid not in assigned and (
            (result.mode == "strict" and sid not in blocked) or sid in forced
        ):
            add("MISSING_JOB", "A required job is not assigned", sid)
    for u in result.unscheduled:
        expected = "blocked" if u.site_id in blocked else "unscheduled"
        if u.state != expected:
            add("STATE_MISMATCH", f"Expected {expected} state", u.site_id)
    groups = defaultdict(list)
    for a in result.assignments:
        site = sites.get(a.site_id)
        if site is None:
            continue
        cd = crews.get((a.crew_id, a.date))
        groups[a.crew_id, a.date].append(site)
        if (
            cd is None
            or not scenario.config.planning_start <= a.date <= scenario.config.planning_end
        ):
            add(
                "NO_CREW_DAY",
                "Assignment has no crew-day inside the planning horizon",
                a.site_id,
                a.crew_id,
                a.date,
            )
        else:
            if site.required_skill not in cd.skills:
                add("SKILL", "Crew lacks the required skill", a.site_id, a.crew_id, a.date)
            if site.cluster_id not in cd.allowed_clusters:
                add(
                    "CLUSTER_NOT_ALLOWED",
                    "Crew cannot serve this cluster",
                    a.site_id,
                    a.crew_id,
                    a.date,
                )
        if a.date < site.ready_date:
            add("BEFORE_READY", "Assignment precedes readiness", a.site_id)
        late = max(0, (a.date - site.deadline).days)
        if late and (result.mode == "strict" or a.site_id in forced):
            add("AFTER_DEADLINE", "A required deadline is missed", a.site_id)
        state = "locked" if a.site_id in locks else ("late" if late else "scheduled")
        if a.days_late != late or a.state != state:
            add("STATE_MISMATCH", "Assignment state or days_late does not match inputs", a.site_id)
    travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
    for key, jobs in groups.items():
        used_clusters = {s.cluster_id for s in jobs}
        if len(used_clusters) > 1:
            add(
                "MULTIPLE_CLUSTERS",
                "Crew-day serves multiple clusters",
                crew_id=key[0],
                date=key[1],
            )
        minutes = sum(s.duration_min for s in jobs) + sum(travel[k] for k in used_clusters)
        if key in crews and minutes > crews[key].available_min:
            add(
                "CAPACITY",
                "Onsite and travel minutes exceed availability",
                crew_id=key[0],
                date=key[1],
            )
    for battery in scenario.config.batteries:
        relevant = [
            a
            for a in result.assignments
            if a.site_id in sites and sites[a.site_id].configuration_id == battery.configuration_id
        ]
        for day in sorted({a.date for a in relevant}):
            used = sum(a.date <= day for a in relevant)
            received = sum(
                r.quantity
                for r in scenario.inventory
                if r.configuration_id == battery.configuration_id and r.available_date <= day
            )
            if used > received:
                add(
                    "INVENTORY",
                    f"{battery.configuration_id}: used {used}, received {received}",
                    date=day,
                )
    for sid, lock in locks.items():
        a = assigned.get(sid)
        if a is None or (a.crew_id, a.date) != (lock.crew_id, lock.date):
            add("LOCK_BROKEN", "Locked install was moved or omitted", sid)
    expected_usage = {(u.crew_id, u.date): u for u in recompute_usage(scenario, result.assignments)}
    actual_usage = {(u.crew_id, u.date): u for u in result.crew_days}
    if len(actual_usage) != len(result.crew_days) or actual_usage != expected_usage:
        add("OBJECTIVE_MISMATCH", "Crew-day usage does not match assignments")
    from app.valuation.value_table import value_table

    try:
        values = {(r.site_id, r.install_date): r.value_usd for r in value_table(scenario)}
        for a in result.assignments:
            if a.site_id in sites and not isclose(
                a.value_usd, values.get((a.site_id, a.date), 0.0), abs_tol=1e-6, rel_tol=1e-9
            ):
                add(
                    "OBJECTIVE_MISMATCH",
                    "Assignment value differs from source valuation",
                    a.site_id,
                )
        expected = recompute_objective(scenario, result.assignments, values=values)
        if result.objective is None:
            add("OBJECTIVE_MISMATCH", "An incumbent must include objective components")
        else:
            for field, value in expected.model_dump().items():
                actual = getattr(result.objective, field)
                # Frozen fixture utilization is rounded to four decimal places.
                tolerance = 0.000051 if field == "crew_utilization" else 1e-6
                same = (
                    isclose(actual, value, abs_tol=tolerance, rel_tol=1e-9)
                    if isinstance(value, float)
                    else actual == value
                )
                if not same:
                    add("OBJECTIVE_MISMATCH", f"{field}: expected {value}, got {actual}")
    except (ValueError, OSError) as exc:
        add("OBJECTIVE_MISMATCH", f"Cannot verify operating value: {exc}")
    return ValidationReport(
        checked=True, valid=not issues, issues=issues, validator="independent-v1"
    )
