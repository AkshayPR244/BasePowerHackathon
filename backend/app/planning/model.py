"""CP-SAT variables, hard constraints, and objective expressions (SPEC section 7)."""

import datetime as dt
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from app.contracts.enums import Mode, ReasonCode
from app.contracts.models import Scenario, Site

Slot = tuple[str, dt.date]  # (crew_id, date)


@dataclass
class Eligibility:
    """Legal (crew, day) options per site, before and after the deadline filter."""

    any_option: dict[str, list[Slot]]
    options: dict[str, list[Slot]]
    blocked: dict[str, list[ReasonCode]]


@dataclass
class PlanModel:
    model: cp_model.CpModel
    x: dict[tuple[str, str, dt.date], cp_model.IntVar]
    y: dict[tuple[str, dt.date, str], cp_model.IntVar]
    assigned: dict[str, cp_model.IntVar | int]
    exprs: dict[str, cp_model.LinearExpr] = field(default_factory=dict)
    lock_conflicts: list[str] = field(default_factory=list)


def _blocked_reasons(site: Site, scenario: Scenario) -> list[ReasonCode]:
    days = scenario.crew_days
    reasons: list[ReasonCode] = []
    if site.ready_date > site.deadline:
        reasons.append(ReasonCode.DEADLINE_BEFORE_READY)
    skilled = [c for c in days if site.required_skill in c.skills]
    if not skilled:
        return reasons + [ReasonCode.SKILL_MISMATCH]
    allowed = [c for c in skilled if site.cluster_id in c.allowed_clusters]
    if not allowed:
        return reasons + [ReasonCode.CLUSTER_NOT_ALLOWED]
    if not any(c.date >= site.ready_date for c in allowed):
        return reasons + [ReasonCode.NOT_READY]
    return reasons + [ReasonCode.NO_LEGAL_DATE]


def eligibility(scenario: Scenario, mode: Mode, forced: set[str]) -> Eligibility:
    total_stock: dict[str, int] = {}
    for r in scenario.inventory:
        total_stock[r.configuration_id] = total_stock.get(r.configuration_id, 0) + r.quantity
    any_option: dict[str, list[Slot]] = {}
    options: dict[str, list[Slot]] = {}
    blocked: dict[str, list[ReasonCode]] = {}
    for s in scenario.sites:
        opts = [
            (c.crew_id, c.date)
            for c in scenario.crew_days
            if s.required_skill in c.skills
            and s.cluster_id in c.allowed_clusters
            and c.date >= s.ready_date
        ]
        if not opts:
            blocked[s.site_id] = _blocked_reasons(s, scenario)
            continue
        if total_stock.get(s.configuration_id, 0) == 0:
            blocked[s.site_id] = [ReasonCode.NO_INVENTORY]
            continue
        any_option[s.site_id] = opts
        if mode == Mode.strict or s.site_id in forced:
            opts = [o for o in opts if o[1] <= s.deadline]
        options[s.site_id] = opts
    return Eligibility(any_option=any_option, options=options, blocked=blocked)


def build(
    scenario: Scenario,
    elig: Eligibility,
    mode: Mode,
    forced: set[str],
    values: dict[tuple[str, dt.date], int],
) -> PlanModel:
    """values: integer cents per (site_id, install date). Missing means 0."""
    m = cp_model.CpModel()
    sites = {s.site_id: s for s in scenario.sites}
    travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
    must_assign = mode == Mode.strict

    x = {
        (sid, crew, d): m.new_bool_var(f"x_{sid}_{crew}_{d}")
        for sid, opts in elig.options.items()
        for crew, d in opts
    }
    by_site: dict[str, list] = {}
    by_slot: dict[Slot, list[tuple[str, cp_model.IntVar]]] = {}
    for (sid, crew, d), v in x.items():
        by_site.setdefault(sid, []).append(v)
        by_slot.setdefault((crew, d), []).append((sid, v))

    assigned: dict[str, cp_model.IntVar | int] = {}
    for sid in elig.options:
        vs = by_site.get(sid, [])
        if must_assign or sid in forced:
            if not vs:
                m.add_bool_or([])  # no legal slot by the deadline: infeasible
                assigned[sid] = 0
                continue
            m.add_exactly_one(vs)
            assigned[sid] = 1
        else:
            a = m.new_bool_var(f"a_{sid}")
            m.add(sum(vs) == a)
            assigned[sid] = a

    y: dict[tuple[str, dt.date, str], cp_model.IntVar] = {}
    for c in scenario.crew_days:
        jobs = by_slot.get((c.crew_id, c.date), [])
        ks = sorted({sites[sid].cluster_id for sid, _ in jobs})
        for k in ks:
            yk = m.new_bool_var(f"y_{c.crew_id}_{c.date}_{k}")
            y[c.crew_id, c.date, k] = yk
            in_k = [v for sid, v in jobs if sites[sid].cluster_id == k]
            m.add(sum(in_k) >= yk)  # travel only on active crew-days
            for v in in_k:
                m.add_implication(v, yk)
        if ks:
            m.add_at_most_one(y[c.crew_id, c.date, k] for k in ks)
            onsite = sum(sites[sid].duration_min * v for sid, v in jobs)
            trav = sum(travel[k] * y[c.crew_id, c.date, k] for k in ks)
            m.add(onsite + trav <= c.available_min)

    # Redundant cut: active crew-days in a cluster must hold all its assigned minutes.
    # It tightens the travel bound a lot. Every feasible plan satisfies it.
    avail = {(c.crew_id, c.date): c.available_min for c in scenario.crew_days}
    for k in sorted({sites[sid].cluster_id for sid in elig.options}):
        room = [(avail[r, d] - travel[kk]) * yk for (r, d, kk), yk in y.items() if kk == k]
        work = [
            sites[sid].duration_min * a for sid, a in assigned.items() if sites[sid].cluster_id == k
        ]
        if room and work:
            m.add(sum(room) >= sum(work))

    days = sorted({c.date for c in scenario.crew_days})
    configs = sorted({s.configuration_id for s in scenario.sites})
    for cfg in configs:
        for day in days:
            used = [
                v for (sid, _, d), v in x.items() if d <= day and sites[sid].configuration_id == cfg
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

    for p in scenario.current_plan:
        if not p.locked:
            continue
        v = x.get((p.site_id, p.crew_id, p.date))
        if v is None:
            pm.lock_conflicts.append(p.site_id)
            m.add_bool_or([])
        else:
            m.add(v == 1)

    late = []
    delay = []
    for (sid, _, d), v in x.items():
        days_late = (d - sites[sid].deadline).days
        if days_late > 0:
            late.append(v)
            delay.append(days_late * v)
    penalty = scenario.config.unscheduled_penalty_days
    unsched = [1 - a for a in assigned.values() if not isinstance(a, int)]
    changes = []
    for p in scenario.current_plan:
        if p.locked or p.site_id not in elig.options:
            continue
        v = x.get((p.site_id, p.crew_id, p.date))
        changes.append(1 - v if v is not None else 1)

    pm.exprs = {
        "jobs_late_or_unscheduled": sum(late) + sum(unsched),
        "total_delay": sum(delay) + penalty * sum(unsched),
        "operating_value": sum(values.get((sid, d), 0) * v for (sid, _, d), v in x.items()),
        "changed_installs": sum(changes),
        "travel": sum(travel[k] * v for (_, _, k), v in y.items()),
    }
    return pm
