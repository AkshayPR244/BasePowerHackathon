"""CP-SAT variables, hard constraints, and objective expressions.

Constraints follow SPEC section 7. Stage order follows docs/DECISIONS.md, "Objective order".
Variables are per visit. A one-visit home has one visit keyed by its site_id. A two-visit home
has an install and a battery day; the battery day carries the deadline, the energy value, and
the battery, and must come at least `min_gap` business days after the install.
"""

import datetime as dt
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from app.contracts.calendar import business_ordinal
from app.contracts.enums import Mode, ReasonCode
from app.contracts.models import Scenario, Site
from app.contracts.visits import Job, gap_ok, job_of_row, jobs_of, min_gap

Slot = tuple[str, dt.date]  # (crew_id, date)


@dataclass
class Eligibility:
    """Legal (crew, day) options per visit, before and after the deadline filter."""

    any_option: dict[str, list[Slot]]  # job_id -> slots
    options: dict[str, list[Slot]]  # job_id -> slots after the deadline filter
    blocked: dict[str, list[ReasonCode]]  # site_id -> reasons
    jobs: dict[str, Job] = field(default_factory=dict)

    def jobs_of_site(self, site_id: str) -> list[Job]:
        return [j for j in self.jobs.values() if j.site_id == site_id]


@dataclass
class PlanModel:
    model: cp_model.CpModel
    x: dict[tuple[str, str, dt.date], cp_model.IntVar]  # (job_id, crew, date)
    y: dict[tuple[str, dt.date, str], cp_model.IntVar]
    assigned: dict[str, cp_model.IntVar | int]  # job_id
    exprs: dict[str, cp_model.LinearExpr] = field(default_factory=dict)
    lock_conflicts: list[str] = field(default_factory=list)  # site_ids


def _blocked_reasons(site: Site, job: Job, scenario: Scenario) -> list[ReasonCode]:
    days = scenario.crew_days
    reasons: list[ReasonCode] = []
    if site.ready_date > site.deadline:
        reasons.append(ReasonCode.DEADLINE_BEFORE_READY)
    skilled = [c for c in days if job.required_skill in c.skills]
    if not skilled:
        return reasons + [ReasonCode.SKILL_MISMATCH]
    allowed = [c for c in skilled if site.cluster_id in c.allowed_clusters]
    if not allowed:
        return reasons + [ReasonCode.CLUSTER_NOT_ALLOWED]
    if not any(c.date >= site.ready_date for c in allowed):
        return reasons + [ReasonCode.NOT_READY]
    return reasons + [ReasonCode.NO_LEGAL_DATE]


def _pair_filter(first, last, gap, origin):
    """Keep install slots that some battery slot can follow, and the reverse."""
    firsts = [i for i in first if any(gap_ok(i[1], b[1], gap, origin) for b in last)]
    lasts = [b for b in last if any(gap_ok(i[1], b[1], gap, origin) for i in first)]
    return firsts, lasts


def eligibility(scenario: Scenario, mode: Mode, forced: set[str]) -> Eligibility:
    total_stock: dict[str, int] = {}
    for r in scenario.inventory:
        total_stock[r.configuration_id] = total_stock.get(r.configuration_id, 0) + r.quantity
    gap, origin = min_gap(scenario), scenario.config.planning_start
    elig = Eligibility(any_option={}, options={}, blocked={})
    for s in scenario.sites:
        jobs = jobs_of(s)
        raw = {
            j.job_id: [
                (c.crew_id, c.date)
                for c in scenario.crew_days
                if scenario.config.planning_start <= c.date <= scenario.config.planning_end
                and j.required_skill in c.skills
                and s.cluster_id in c.allowed_clusters
                and c.date >= s.ready_date
            ]
            for j in jobs
        }
        empty = next((j for j in jobs if not raw[j.job_id]), None)
        if empty is not None:
            elig.blocked[s.site_id] = _blocked_reasons(s, empty, scenario)
            continue
        required = mode == Mode.strict or s.site_id in forced
        if len(jobs) == 2:
            first, last = jobs
            firsts, raw[last.job_id] = _pair_filter(
                raw[first.job_id], raw[last.job_id], gap, origin
            )
            if not raw[last.job_id]:
                elig.blocked[s.site_id] = [ReasonCode.NO_LEGAL_DATE]
                continue
            if required:
                raw[first.job_id] = firsts
            # Otherwise an install may stand alone when no battery day can follow it.
        opts = dict(raw)
        if required:
            final = jobs[-1]
            opts[final.job_id] = [o for o in opts[final.job_id] if o[1] <= s.deadline]
            if len(jobs) == 2:
                opts[jobs[0].job_id], opts[final.job_id] = _pair_filter(
                    opts[jobs[0].job_id], opts[final.job_id], gap, origin
                )
        for j in jobs:
            elig.jobs[j.job_id] = j
            elig.any_option[j.job_id] = raw[j.job_id]
            elig.options[j.job_id] = opts[j.job_id]
    return elig


def build(
    scenario: Scenario,
    elig: Eligibility,
    mode: Mode,
    forced: set[str],
    values: dict[tuple[str, dt.date], int],
) -> PlanModel:
    """values: integer cents per (site_id, battery-day date). Missing means 0."""
    m = cp_model.CpModel()
    sites = {s.site_id: s for s in scenario.sites}
    jobs = elig.jobs
    travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
    gap, origin = min_gap(scenario), scenario.config.planning_start

    x = {
        (jid, crew, d): m.new_bool_var(f"x_{jid}_{crew}_{d}")
        for jid, opts in elig.options.items()
        for crew, d in opts
    }
    by_job: dict[str, list] = {}
    by_slot: dict[Slot, list[tuple[str, cp_model.IntVar]]] = {}
    for (jid, crew, d), v in x.items():
        by_job.setdefault(jid, []).append(v)
        by_slot.setdefault((crew, d), []).append((jid, v))

    assigned: dict[str, cp_model.IntVar | int] = {}
    for jid, job in jobs.items():
        vs = by_job.get(jid, [])
        if mode == Mode.strict or job.site_id in forced:
            if not vs:
                m.add_bool_or([])  # no legal slot by the deadline: infeasible
                assigned[jid] = 0
                continue
            m.add_exactly_one(vs)
            assigned[jid] = 1
        else:
            a = m.new_bool_var(f"a_{jid}")
            m.add(sum(vs) == a)
            assigned[jid] = a

    for site_id in {j.site_id for j in jobs.values()}:
        pair = elig.jobs_of_site(site_id)
        if len(pair) != 2:
            continue
        first, last = sorted(pair, key=lambda j: j.final)
        a_i, a_b = assigned[first.job_id], assigned[last.job_id]
        if isinstance(a_b, int) and a_b == 0:
            continue
        day_i = sum(
            business_ordinal(d, origin) * v for (jid, _, d), v in x.items() if jid == first.job_id
        )
        day_b = sum(
            business_ordinal(d, origin) * v for (jid, _, d), v in x.items() if jid == last.job_id
        )
        m.add(a_b <= a_i)
        if isinstance(a_b, int):
            m.add(day_b - day_i >= gap)
        else:
            m.add(day_b - day_i >= gap).only_enforce_if(a_b)

    y: dict[tuple[str, dt.date, str], cp_model.IntVar] = {}
    for c in scenario.crew_days:
        here = by_slot.get((c.crew_id, c.date), [])
        ks = sorted({sites[jobs[jid].site_id].cluster_id for jid, _ in here})
        for k in ks:
            yk = m.new_bool_var(f"y_{c.crew_id}_{c.date}_{k}")
            y[c.crew_id, c.date, k] = yk
            in_k = [v for jid, v in here if sites[jobs[jid].site_id].cluster_id == k]
            m.add(sum(in_k) >= yk)  # travel only on active crew-days
            for v in in_k:
                m.add_implication(v, yk)
        if ks:
            m.add_at_most_one(y[c.crew_id, c.date, k] for k in ks)
            onsite = sum(jobs[jid].duration_min * v for jid, v in here)
            trav = sum(travel[k] * y[c.crew_id, c.date, k] for k in ks)
            m.add(onsite + trav <= c.available_min)

    # Redundant cuts, valid for every feasible plan: per skill and cluster, the active crew-days
    # of crews with that skill must hold all assigned minutes of visits needing it. Splitting by
    # skill keeps install-crew room from hiding a battery-crew shortage.
    avail = {(c.crew_id, c.date): c.available_min for c in scenario.crew_days}
    skills_of = {(c.crew_id, c.date): set(c.skills) for c in scenario.crew_days}
    for skill in sorted({j.required_skill for j in jobs.values()}):
        for k in sorted({sites[j.site_id].cluster_id for j in jobs.values()}):
            room = [
                (avail[r, d] - travel[kk]) * yk
                for (r, d, kk), yk in y.items()
                if kk == k and skill in skills_of[r, d]
            ]
            work = [
                j.duration_min * assigned[jid]
                for jid, j in jobs.items()
                if sites[j.site_id].cluster_id == k and j.required_skill == skill
            ]
            if room and work:
                m.add(sum(room) >= sum(work))

    days = sorted({c.date for c in scenario.crew_days})
    configs = sorted({s.configuration_id for s in scenario.sites})
    for cfg in configs:
        for day in days:
            used = [
                v
                for (jid, _, d), v in x.items()
                if d <= day and jobs[jid].final and sites[jobs[jid].site_id].configuration_id == cfg
            ]
            if not used:
                continue
            got = sum(
                r.quantity
                for r in scenario.inventory
                if r.configuration_id == cfg and r.available_date <= day
            )
            m.add(sum(used) <= got)

    pm = PlanModel(model=m, x=x, y=y, assigned=assigned)
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}

    for p in scenario.current_plan:
        if not p.locked:
            continue
        jid = job_of_row(p, by_site)
        v = x.get((jid, p.crew_id, p.date)) if jid else None
        if v is None:
            pm.lock_conflicts.append(p.site_id)
            m.add_bool_or([])
        else:
            m.add(v == 1)

    late, delay = [], []
    for (jid, _, d), v in x.items():
        job = jobs[jid]
        days_late = (d - sites[job.site_id].deadline).days
        if job.final and days_late > 0:
            late.append(v)
            delay.append(days_late * v)
    penalty = scenario.config.unscheduled_penalty_days
    unsched = [
        1 - assigned[jid]
        for jid, j in jobs.items()
        if j.final and not isinstance(assigned[jid], int)
    ]
    changes = []
    for p in scenario.current_plan:
        if p.locked:
            continue
        jid = job_of_row(p, by_site)
        v = x.get((jid, p.crew_id, p.date)) if jid else None
        changes.append(1 - v if v is not None else 1)

    pm.exprs = {
        "jobs_late_or_unscheduled": sum(late) + sum(unsched),
        "total_delay": sum(delay) + penalty * sum(unsched),
        "operating_value": sum(
            values.get((jobs[jid].site_id, d), 0) * v
            for (jid, _, d), v in x.items()
            if jobs[jid].final
        ),
        "changed_installs": sum(changes),
        "travel": sum(travel[k] * v for (_, _, k), v in y.items()),
        "canonical": _canonical(x),
    }
    return pm


def _canonical(x: dict) -> cp_model.LinearExpr:
    """Tie-break so parallel solves return one plan among equal optima.

    Weight (slot rank + 1) * (visit rank + 1): swapping two visits between two slots always
    changes the sum, so equal-objective plans rarely tie here.
    """
    slots = sorted({(d, crew) for (_, crew, d) in x})
    slot_rank = {s: i for i, s in enumerate(slots)}
    job_rank = {jid: i for i, jid in enumerate(sorted({jid for jid, _, _ in x}))}
    return sum(
        (slot_rank[d, crew] + 1) * (job_rank[jid] + 1) * v for (jid, crew, d), v in x.items()
    )
