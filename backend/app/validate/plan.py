"""Independently recompute plan constraints; no scheduling-model helpers are used.

Checks run per visit. A one-visit home has a single visit named by its site_id. A two-visit
home has an install, then a battery day at least `min_gap` business days later. The deadline,
the energy value, and the battery itself belong to the battery day.

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
from app.contracts.visits import Job, gap_ok, job_of_row, jobs_of, min_gap

ADDED_OBJECTIVE_FIELDS = ("visits_moved", "customers_to_reschedule")


def _jobs(scenario: Scenario) -> dict[str, Job]:
    return {j.job_id: j for s in scenario.sites for j in jobs_of(s)}


def _key(a) -> str:
    return a.job_id or a.site_id


def legal_slots(scenario: Scenario, site, job: Job | None = None) -> list:
    """Eligibility before deadline filtering, independent of competing jobs."""
    job = job or jobs_of(site)[-1]
    return [
        c
        for c in scenario.crew_days
        if scenario.config.planning_start <= c.date <= scenario.config.planning_end
        and c.date >= site.ready_date
        and job.required_skill in c.skills
        and site.cluster_id in c.allowed_clusters
    ]


def _blocked(scenario: Scenario) -> set[str]:
    """Homes where some visit has no legal slot, or no battery day can follow any install."""
    gap, origin = min_gap(scenario), scenario.config.planning_start
    out = set()
    for s in scenario.sites:
        slots = {j.job_id: legal_slots(scenario, s, j) for j in jobs_of(s)}
        if any(not v for v in slots.values()):
            out.add(s.site_id)
        elif s.visits:
            first, last = jobs_of(s)
            if not any(
                gap_ok(i.date, b.date, gap, origin)
                for i in slots[first.job_id]
                for b in slots[last.job_id]
            ):
                out.add(s.site_id)
    return out


def value_distinguishes_choices(scenario: Scenario, values: dict) -> bool:
    """True when two legal battery-day slots carry different values."""
    candidates = [
        values.get((s.site_id, c.date), 0.0)
        for s in scenario.sites
        for c in legal_slots(scenario, s)
    ]
    return bool(candidates and max(candidates) - min(candidates) > 1e-9)


def recompute_usage(scenario: Scenario, assignments: list[Assignment]) -> list[CrewDayUsage]:
    sites = {s.site_id: s for s in scenario.sites}
    jobs = _jobs(scenario)
    clusters = {c.cluster_id: c for c in scenario.clusters}
    result = []
    for cd in scenario.crew_days:
        here = [
            a
            for a in assignments
            if _key(a) in jobs and (a.crew_id, a.date) == (cd.crew_id, cd.date)
        ]
        used = {sites[a.site_id].cluster_id for a in here}
        result.append(
            CrewDayUsage(
                crew_id=cd.crew_id,
                date=cd.date,
                cluster_id=next(iter(used)) if len(used) == 1 else None,
                onsite_min=sum(jobs[_key(a)].duration_min for a in here),
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
    jobs = _jobs(scenario)
    known = [a for a in assignments if _key(a) in jobs]
    at = {_key(a): a for a in known}
    finals = [a for a in known if jobs[_key(a)].final]
    final_sites = {a.site_id for a in finals}
    blocked = _blocked(scenario)
    late = [max(0, (a.date - sites[a.site_id].deadline).days) for a in finals]
    usage = recompute_usage(scenario, known)
    available = sum(c.available_min for c in scenario.crew_days)
    used = sum(u.onsite_min + u.travel_min for u in usage)
    by_site = defaultdict(list)
    for s in scenario.sites:
        by_site[s.site_id] = jobs_of(s)
    moved_homes = set()
    moved = 0
    for p in scenario.current_plan:
        if p.locked:
            continue
        job = job_of_row(p, by_site)
        a = at.get(job) if job else None
        if a is None or (a.crew_id, a.date) != (p.crew_id, p.date):
            moved += 1
            moved_homes.add(p.site_id)
    return ObjectiveComponents(
        jobs_on_time=sum(d == 0 for d in late),
        jobs_late=sum(d > 0 for d in late),
        jobs_unscheduled=len(set(sites) - final_sites),
        jobs_blocked=len(blocked - final_sites),
        total_delay_days=sum(late),
        operating_value_usd=sum(values.get((a.site_id, a.date), 0.0) for a in finals),
        changed_installs=moved,
        travel_allowance_min=sum(u.travel_min for u in usage),
        crew_utilization=min(1.0, used / available) if available else 0.0,
        value_distinguishes_choices=value_distinguishes_choices(scenario, values),
        visits_moved=moved,
        customers_to_reschedule=len(moved_homes),
    )


def validate_plan(scenario: Scenario, result: PlanResult) -> ValidationReport:
    issues = []

    def add(code, message, site_id=None, crew_id=None, date=None, job_id=None):
        issues.append(
            ValidationIssue(
                code=code,
                message=message,
                site_id=site_id,
                crew_id=crew_id,
                date=date,
                job_id=job_id,
            )
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
    jobs = _jobs(scenario)
    crews = {(c.crew_id, c.date): c for c in scenario.crew_days}
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}
    locks = {}
    for p in scenario.current_plan:
        if p.locked and (job := job_of_row(p, by_site)):
            locks[job] = p
    forced = {e.site_id for e in result.edits if e.kind == "force_include"}
    assigned = {_key(a): a for a in result.assignments}
    blocked = _blocked(scenario)
    gap, origin = min_gap(scenario), scenario.config.planning_start

    covered = set()
    for u in result.unscheduled:
        if u.job_id is None:
            covered |= {j.job_id for j in by_site.get(u.site_id, [])}
        else:
            covered.add(u.job_id)
        expected = "blocked" if u.site_id in blocked else "unscheduled"
        if u.state != expected:
            add("STATE_MISMATCH", f"Expected {expected} state", u.site_id, job_id=u.job_id)
    for key, count in Counter(_key(a) for a in result.assignments).items():
        if key not in jobs:
            add("UNKNOWN_SITE", f"Unknown site or visit {key}", key)
        if count > 1:
            add("DUPLICATE_ASSIGNMENT", f"Visit {key} appears more than once", key, job_id=key)
    for key in assigned:
        if key in covered:
            add("DUPLICATE_ASSIGNMENT", f"Visit {key} is both assigned and unscheduled", key)
    for j in jobs.values():
        if j.job_id not in assigned and j.job_id not in covered:
            add("MISSING_JOB", "Visit is absent from assignments and unscheduled list", j.site_id)
        required = (result.mode == "strict" and j.site_id not in blocked) or j.site_id in forced
        if j.job_id not in assigned and required:
            add("MISSING_JOB", "A required visit is not assigned", j.site_id, job_id=j.job_id)

    groups = defaultdict(list)
    for a in result.assignments:
        job = jobs.get(_key(a))
        if job is None or job.site_id != a.site_id:
            if job is not None:
                add("UNKNOWN_SITE", f"Visit {a.job_id} is not part of {a.site_id}", a.site_id)
            continue
        site = sites[a.site_id]
        if a.visit_type != job.visit_type:
            add("STATE_MISMATCH", "Visit type does not match the visit", a.site_id, job_id=a.job_id)
        cd = crews.get((a.crew_id, a.date))
        groups[a.crew_id, a.date].append((site, job))
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
                a.job_id,
            )
        else:
            if job.required_skill not in cd.skills:
                add(
                    "SKILL",
                    "Crew lacks the skill for this visit type",
                    a.site_id,
                    a.crew_id,
                    a.date,
                    a.job_id,
                )
            if site.cluster_id not in cd.allowed_clusters:
                add(
                    "CLUSTER_NOT_ALLOWED",
                    "Crew cannot serve this cluster",
                    a.site_id,
                    a.crew_id,
                    a.date,
                    a.job_id,
                )
        if a.date < site.ready_date:
            add("BEFORE_READY", "Assignment precedes readiness", a.site_id, job_id=a.job_id)
        late = max(0, (a.date - site.deadline).days) if job.final else 0
        if late and (result.mode == "strict" or a.site_id in forced):
            add("AFTER_DEADLINE", "A required deadline is missed", a.site_id, job_id=a.job_id)
        state = "locked" if job.job_id in locks else ("late" if late else "scheduled")
        if a.days_late != late or a.state != state:
            add(
                "STATE_MISMATCH",
                "Assignment state or days_late does not match inputs",
                a.site_id,
                job_id=a.job_id,
            )
        if not job.final and a.value_usd != 0:
            add(
                "OBJECTIVE_MISMATCH",
                "Energy value belongs to the battery day, not the install",
                a.site_id,
                job_id=a.job_id,
            )
    for s in scenario.sites:
        if not s.visits:
            continue
        first, last = jobs_of(s)
        i, b = assigned.get(first.job_id), assigned.get(last.job_id)
        if b is not None and (i is None or not gap_ok(i.date, b.date, gap, origin)):
            add(
                "PRECEDENCE",
                f"Battery day needs an install at least {gap} business day(s) earlier",
                s.site_id,
                job_id=last.job_id,
            )
    travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
    for key, here in groups.items():
        used_clusters = {s.cluster_id for s, _ in here}
        if len(used_clusters) > 1:
            add(
                "MULTIPLE_CLUSTERS",
                "Crew-day serves multiple clusters",
                crew_id=key[0],
                date=key[1],
            )
        minutes = sum(j.duration_min for _, j in here) + sum(travel[k] for k in used_clusters)
        if key in crews and minutes > crews[key].available_min:
            add(
                "CAPACITY",
                "Onsite and travel minutes exceed availability",
                crew_id=key[0],
                date=key[1],
            )
    finals = [a for a in result.assignments if _key(a) in jobs and jobs[_key(a)].final]
    for battery in scenario.config.batteries:
        relevant = [
            a for a in finals if sites[a.site_id].configuration_id == battery.configuration_id
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
    for key, lock in locks.items():
        a = assigned.get(key)
        if a is None or (a.crew_id, a.date) != (lock.crew_id, lock.date):
            add("LOCK_BROKEN", "Locked visit was moved or omitted", lock.site_id, job_id=key)
    expected_usage = {(u.crew_id, u.date): u for u in recompute_usage(scenario, result.assignments)}
    actual_usage = {(u.crew_id, u.date): u for u in result.crew_days}
    if len(actual_usage) != len(result.crew_days) or actual_usage != expected_usage:
        add("OBJECTIVE_MISMATCH", "Crew-day usage does not match assignments")
    from app.valuation.value_table import value_table

    try:
        values = {(r.site_id, r.install_date): r.value_usd for r in value_table(scenario)}
        for a in finals:
            if not isclose(
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
                if field in ADDED_OBJECTIVE_FIELDS and actual is None:
                    continue  # results from before contract 1.1 do not carry these fields
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
