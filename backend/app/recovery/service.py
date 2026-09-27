"""Live deterministic recovery orchestration. No network or autonomous approval."""

import datetime as dt
import hashlib
import json
import threading
from collections import OrderedDict

from app.contracts.hashing import scenario_hash
from app.contracts.models import (
    AddCrewDay,
    ApproveResult,
    Assumption,
    ExtendCrewDay,
    Parameter,
    PlannedInstall,
    PlanRequest,
    RecoveryOptionsResult,
)
from app.contracts.visits import all_jobs, job_of_row, jobs_of
from app.planning.edits import GRANTED, apply_edits, appointment_windows, granted_overtime
from app.planning.explain import day
from app.planning.lexicographic import Tuning, tuned
from app.planning.solve import InvalidPlanError, _validated, plan
from app.recovery.economics import DEFAULTS, assumptions
from app.recovery.impact import analyze
from app.recovery.options import FEASIBLE, dominated, solved, wrap
from app.recovery.repair import current_result, repair, result_for

DISRUPTIONS = {
    "remove_crew_day",
    "reduce_crew_day",
    "change_ready_date",
    "change_appointment",
    "delay_inventory",
}
# Solver budgets count deterministic time, so the same request returns the same plans.
INTERACTIVE_BUDGET = 1.2
EVALUATE_BUDGET = 0.8
CANDIDATES = {True: (1, 1), False: (4, 4)}  # (overtime, temporary) solves per request

_lock = threading.RLock()
_cache = OrderedDict()
_plans = OrderedDict()
_issued = OrderedDict()
_approved = OrderedDict()
_LIMIT = 128


def _remember(table, key, value, limit=_LIMIT):
    with _lock:
        table[key] = value
        table.move_to_end(key)
        while len(table) > limit:
            table.popitem(last=False)


def _recall(table, key):
    with _lock:
        hit = table.get(key)
        if hit is not None:
            table.move_to_end(key)
        return hit


def _key(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def disruption_start(scenario, disruption):
    """The earliest date a disruption changes, including bookings it breaks. Recovery treats it
    as now."""
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}
    booked = {job_of_row(p, by_site): p.date for p in scenario.current_plan}
    jobs = all_jobs(scenario)
    dates = []
    for e in disruption:
        if e.kind in {"remove_crew_day", "reduce_crew_day"}:
            dates.append(e.date)
        elif e.kind == "delay_inventory":
            dates.append(e.from_date)
        elif e.kind == "change_ready_date":
            dates.append(e.ready_date)
            dates += [
                d
                for j, d in booked.items()
                if j in jobs and jobs[j].site_id == e.site_id and d < e.ready_date
            ]
        elif e.kind == "change_appointment":
            dates.append(e.available_from)
            d = booked.get(e.job_id)
            if d is not None and (d < e.available_from or (e.available_to and d > e.available_to)):
                dates.append(d)
    return min(dates, default=None)


def _check_kinds(disruption, interventions=()):
    if any(e.kind not in DISRUPTIONS for e in disruption):
        raise ValueError(
            "Disruptions must describe lost resources or changed readiness/appointments."
        )
    wrong = sorted({e.kind for e in interventions if e.kind in DISRUPTIONS})
    if wrong:
        raise ValueError(
            f"{', '.join(wrong)} describes a disruption, not a recovery action. "
            "Add it to the disruption list."
        )


def _check_past(base, interventions, now):
    if now is None:
        return
    by_site = {s.site_id: jobs_of(s) for s in base.sites}
    booked = {job_of_row(p, by_site): p.date for p in base.current_plan}
    for e in interventions:
        if e.kind == "move_visit":
            if e.date < now:
                raise ValueError(f"Cannot move a visit into the past, before {day(now)}.")
            if booked.get(e.job_id, now) < now:
                raise ValueError(
                    f"Visit {e.job_id} was due on {day(booked[e.job_id])}, before "
                    f"{day(now)}. Past visits cannot move."
                )
        elif e.kind in {"extend_crew_day", "add_crew_day"} and e.date < now:
            raise ValueError(f"Cannot add capacity in the past, before {day(now)}.")


def _with_approved_capacity(scenario, base):
    """Accept a current plan approved here with overtime or a temporary crew."""
    try:
        current_result(base)
        return base
    except (InvalidPlanError, ValueError):
        pass
    with _lock:
        approvals = list(_approved.get(scenario_hash(scenario), []))
    for effective in reversed(approvals):
        candidate = base.model_copy(
            update={
                "crew_days": effective.crew_days,
                "config": base.config.model_copy(
                    update={"parameters": effective.config.parameters}
                ),
            }
        )
        try:
            current_result(candidate)
            return candidate
        except (InvalidPlanError, ValueError):
            continue
    return base


def _prepare(scenario, current_plan, economics, disruption=()):
    configured = {p.name: float(p.value) for p in scenario.config.parameters if p.name in DEFAULTS}
    rates = assumptions({**configured, **(economics or {})})
    base = scenario.model_copy(deep=True)
    if current_plan is not None:
        base.current_plan = list(current_plan)
        base = _with_approved_capacity(scenario, base)
    now = disruption_start(base, disruption)
    if now is not None:
        # The past already happened: no option may move a visit dated before the disruption.
        base.current_plan = [
            p.model_copy(update={"locked": True}) if p.date < now else p for p in base.current_plan
        ]
    # Same configured cap is used by edit validation and candidate generation.
    cap = next(a for a in rates if a.key == "max_overtime_min")
    base.config.parameters = [p for p in base.config.parameters if p.name != cap.key] + [
        Parameter(
            name=cap.key, value=cap.value, unit=cap.unit, kind=cap.kind, derivation=cap.source
        )
    ]
    base.scenario_hash = scenario_hash(base)
    try:
        original = current_result(base)
        if now is not None and any(c.date < now for c in base.crew_days):
            base = _close_past(base, original, now)
            original = current_result(base)
    except InvalidPlanError as exc:
        raise ValueError("The supplied current plan is not feasible: " + str(exc)) from exc
    return base, original, rates


def prepared_scenario(scenario, disruption, current_plan=None):
    """The scenario recovery solves on: the past frozen and the overtime cap set."""
    return _prepare(scenario, current_plan, None, disruption)[0]


def _close_past(base, original, now):
    """Past crew-days keep only the minutes their booked visits used, so nothing new lands there."""
    used = {(c.crew_id, c.date): c.onsite_min + c.travel_min for c in original.crew_days}
    days = [
        c.model_copy(update={"available_min": used.get((c.crew_id, c.date), 0)})
        if c.date < now
        else c
        for c in base.crew_days
    ]
    closed = base.model_copy(update={"crew_days": days})
    closed.scenario_hash = scenario_hash(closed)
    return closed


def _check_edits(base, edits):
    applied = apply_edits(base, edits)
    if applied.issues:
        raise ValueError(" ".join(i.message for i in applied.issues))
    return applied.scenario


def _digest(option):
    """Plan content without volatile fields, so a re-issued option still matches."""
    data = option.model_dump(
        mode="json",
        exclude={"lowest_modeled_cost": True, "result": {"solve_ms", "stages", "message"}},
    )
    return _key(_no_negative_zero(data))


def _no_negative_zero(value):
    # JSON.stringify writes -0.0 as 0, so a browser round trip must still match.
    if isinstance(value, dict):
        return {k: _no_negative_zero(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_no_negative_zero(v) for v in value]
    if isinstance(value, float) and value == 0:
        return 0.0
    return value


def _issue(base, option, source_hash):
    # Include the full supplied current plan and revision; never trust client approval payloads.
    _remember(
        _issued,
        (option.option_id, _digest(option)),
        (base.model_copy(deep=True), option.model_copy(deep=True), source_hash),
        limit=4 * _LIMIT,
    )
    return option


def _hint(scenario, result):
    """Warm start from a known feasible plan, named like the planner's variables."""
    if not solved(result):
        return None
    cluster = {s.site_id: s.cluster_id for s in scenario.sites}
    hint = {}
    for a in result.assignments:
        jid = a.job_id or a.site_id
        hint[f"x_{jid}_{a.crew_id}_{a.date}"] = 1
        hint[f"a_{jid}"] = 1
        hint[f"y_{a.crew_id}_{a.date}_{cluster[a.site_id]}"] = 1
    return hint


def _solve(base, edits, budget, hint=None):
    with tuned(Tuning(hint=hint, deterministic=True)):
        result = plan(
            base,
            PlanRequest(
                scenario_id=base.scenario_id,
                revision=base.revision,
                edits=list(edits),
                mode="recovery",
                time_limit_s=max(0.02, budget),
            ),
        )
    if result.status == "timeout_no_incumbent":
        # A time limit is not a feasibility proof. Try a deterministic, independently
        # checked incumbent, first restoring original bookings onto like-for-like added capacity.
        effective = _check_edits(base, edits)
        jobs = all_jobs(base)
        by_site = {s.site_id: jobs_of(s) for s in base.sites}
        available = {(c.crew_id, c.date) for c in effective.crew_days}
        placed = {}
        for row in base.current_plan:
            jid = job_of_row(row, by_site)
            slot = (row.crew_id, row.date)
            if slot not in available:
                job = jobs[jid]
                site = next(s for s in base.sites if s.site_id == job.site_id)
                replacement = next(
                    (
                        e
                        for e in edits
                        if isinstance(e, AddCrewDay)
                        and e.date == row.date
                        and job.required_skill in e.skills
                        and site.cluster_id in e.allowed_clusters
                    ),
                    None,
                )
                if replacement is not None:
                    slot = (replacement.crew_id, replacement.date)
            placed[jid] = slot
        try:
            result = result_for(
                effective,
                placed,
                edits,
                "Deterministic capacity-restoration incumbent; not proven optimal.",
            )
        except InvalidPlanError:
            try:
                candidate = repair(base, edits)
                if candidate.status in FEASIBLE:
                    result = candidate
            except InvalidPlanError:
                pass  # Keep the truthful timeout when no checked incumbent is available.
    if result.status == "feasible":
        result.message = "Best found within the solve budget, not proven best. " + result.message
    return result


def _candidates(base, disruption, cap, original, no_action, limits=(4, 4)):
    """Overtime and temporary crew-days that could serve displaced visits, most useful first."""
    edited = _check_edits(base, disruption)
    now = disruption_start(base, disruption)
    jobs = all_jobs(base)
    sites = {s.site_id: s for s in edited.sites}
    by_site = {s.site_id: jobs_of(s) for s in base.sites}
    after = {job_of_row(a, by_site): (a.crew_id, a.date) for a in no_action.assignments}
    windows = appointment_windows(disruption)
    demands = []
    for row in original.assignments:
        jid = job_of_row(row, by_site)
        if after.get(jid) == (row.crew_id, row.date):
            continue
        job, site = jobs[jid], sites[row.site_id]
        first = max(now or row.date, site.ready_date)
        window = windows.get(jid)
        if window:
            first = max(first, window[0])
        # Capacity before the delayed receipt cannot serve the displaced battery visits.
        if job.final:
            for edit in disruption:
                if (
                    edit.kind == "delay_inventory"
                    and edit.configuration_id == site.configuration_id
                    and edit.from_date <= row.date < edit.to_date
                ):
                    first = max(first, edit.to_date)
        last = window[1] if window else None
        # An install must leave room for its battery day before the deadline.
        useful = site.deadline if job.final else site.deadline - dt.timedelta(days=1)
        demands.append((first, last, job.required_skill, site.cluster_id, useful))

    def score(day, skills, clusters):
        fits = [
            d
            for d in demands
            if d[2] in skills and d[3] in clusters and d[0] <= day and (d[1] is None or day <= d[1])
        ]
        return len(fits), sum(day <= d[4] for d in fits)

    hit = {
        (e.crew_id, e.date) for e in disruption if e.kind in {"remove_crew_day", "reduce_crew_day"}
    }
    granted = granted_overtime(base)
    working = {c.date for c in edited.crew_days if c.available_min > 0}
    ranked_ot, ranked_temp = [], []
    for c in edited.crew_days:
        extra = int(cap) - granted.get((c.crew_id, c.date), 0)
        # Overtime on a crew-day the disruption cut would pay premium for normal hours.
        if (c.crew_id, c.date) in hit or c.available_min <= 0 or extra <= 0:
            continue
        if now is not None and c.date < now:
            continue
        n, on_time = score(c.date, c.skills, c.allowed_clusters)
        if n:
            ranked_ot.append(
                (
                    (-on_time, -n, c.date, c.crew_id),
                    ExtendCrewDay(crew_id=c.crew_id, date=c.date, extra_min=extra),
                )
            )
    ids = {c.crew_id for c in base.crew_days}
    templates = {}
    for c in sorted(base.crew_days, key=lambda c: (c.date, c.crew_id)):
        # Past crew-days are closed down to the minutes they used, so they are not a full day.
        if c.available_min > 0 and (now is None or c.date >= now):
            templates.setdefault((tuple(sorted(c.skills)), tuple(sorted(c.allowed_clusters))), c)
    for d in sorted({c.date for c in base.crew_days}):
        # Never add a crew on a day the disruption closed for every crew, such as a storm day.
        if (now is not None and d < now) or d not in working:
            continue
        for c in templates.values():
            n, on_time = score(d, c.skills, c.allowed_clusters)
            if not n:
                continue
            name = "TEMP-" + c.crew_id
            while name in ids:
                name += "-R"
            ranked_temp.append(
                (
                    (-on_time, -n, d, name),
                    AddCrewDay(
                        crew_id=name,
                        date=d,
                        available_min=c.available_min,
                        skills=c.skills,
                        allowed_clusters=c.allowed_clusters,
                    ),
                )
            )
    # Bounded search, not an exhaustive intervention optimum.
    ot = [[e] for _, e in sorted(ranked_ot, key=lambda r: r[0])[: limits[0]]]
    temporary = [[e] for _, e in sorted(ranked_temp, key=lambda r: r[0])[: limits[1]]]
    return ot, temporary


def _label(kind, e):
    if kind == "overtime":
        return f"Crew {e.crew_id} +{e.extra_min / 60:g}h overtime on {day(e.date)}"
    return f"Add temporary crew {e.crew_id} on {day(e.date)}"


def _outcome(result):
    o = result.objective
    return (o.jobs_late + o.jobs_unscheduled, o.total_delay_days, o.changed_installs)


def _solve_all(base, disruption, rates, original, interactive):
    """Solved plans do not depend on prices, so price changes reuse them."""
    from app.valuation.value_table import value_table

    valuation_keys = sorted({row.input_hash for row in value_table(base)})
    key = _key(
        base.model_dump(mode="json"),
        [e.model_dump(mode="json") for e in disruption],
        interactive,
        valuation_keys,
    )
    hit = _recall(_plans, key)
    if hit is not None:
        return hit
    na = repair(base, disruption)
    hint = _hint(base, na)
    budget = INTERACTIVE_BUDGET if interactive else base.config.solve_time_limit_s
    rebalance = _solve(base, disruption, budget / 3, hint)
    # No action is feasible for rebalance too. Never show a rebalance that is worse than it.
    if solved(na) and (not solved(rebalance) or _outcome(rebalance) > _outcome(na)):
        rebalance = na.model_copy(
            update={
                "message": "Best found within the solve budget, not proven best. Rebalance "
                "found no plan better than no action, so it keeps the no-action plan."
            }
        )
    hint = _hint(base, rebalance) or hint
    cap = next(a.value for a in rates if a.key == "max_overtime_min")
    ot, temporary = _candidates(base, disruption, cap, original, na, CANDIDATES[interactive])
    n = max(1, len(ot) + len(temporary))
    solved_candidates = [
        (
            kind,
            interventions,
            _solve(base, [*disruption, *interventions], 2 * budget / (3 * n), hint),
        )
        for kind, group in [("overtime", ot), ("temporary_capacity", temporary)]
        for interventions in group
    ]
    out = {"no_action": na, "rebalance": rebalance, "candidates": solved_candidates}
    _remember(_plans, key, out)
    return out


def recover(scenario, disruption, current_plan=None, economics=None, interactive=False):
    source_hash = scenario_hash(scenario)
    _check_kinds(disruption)
    base, original, rates = _prepare(scenario, current_plan, economics, disruption)
    _check_edits(base, disruption)
    key = _key(
        base.model_dump(mode="json"),
        [e.model_dump(mode="json") for e in disruption],
        economics,
        interactive,
    )
    hit = _recall(_cache, key)
    if hit is not None:
        for option in [hit.no_action, *hit.options]:
            _issue(base, option, source_hash)
        return hit.model_copy(deep=True)
    solved_plans = _solve_all(base, disruption, rates, original, interactive)
    no_action = wrap(
        "no_action",
        "Keep original crews; wait for their next open slot",
        original,
        solved_plans["no_action"],
        [],
        rates,
    )
    rebalance_result = solved_plans["rebalance"]
    same = (
        solved(rebalance_result)
        and solved(no_action.result)
        and sorted((a.job_id or a.site_id, a.crew_id, a.date) for a in rebalance_result.assignments)
        == sorted((a.job_id or a.site_id, a.crew_id, a.date) for a in no_action.result.assignments)
    )
    rebalance = wrap(
        "rebalance",
        "Rebalance existing crews: same plan as no action" if same else "Rebalance existing crews",
        original,
        rebalance_result,
        [],
        rates,
        no_action,
    )
    options = [rebalance]
    for kind in ["overtime", "temporary_capacity"]:
        best = None
        for k, interventions, result in solved_plans["candidates"]:
            if k != kind:
                continue
            candidate = wrap(
                kind,
                _label(kind, interventions[0]),
                original,
                result,
                interventions,
                rates,
                no_action,
            )
            if candidate.status not in FEASIBLE or not candidate.result.validation.valid:
                continue
            if best is None or (
                candidate.counts.deadlines_missed,
                candidate.economics.net_impact_usd,
                candidate.option_id,
            ) < (best.counts.deadlines_missed, best.economics.net_impact_usd, best.option_id):
                best = candidate
        if best is not None:
            options.append(best)
    # Paid capacity stays unless another option misses no more deadlines at no more cost.
    feasible = [
        o for o in [no_action, *options] if o.status in FEASIBLE and o.result.validation.valid
    ]
    options = [
        o
        for o in options
        if o.kind == "rebalance" or not dominated(o, [p for p in feasible if p is not o])
    ]
    choices = [o for o in [no_action, *options] if o in feasible]
    if choices:
        min(
            choices,
            key=lambda o: (o.economics.net_impact_usd, o.kind != "no_action", o.option_id),
        ).lowest_modeled_cost = True
    n_ot, n_temp = CANDIDATES[interactive]
    out = RecoveryOptionsResult(
        revision=base.revision,
        scenario_hash=base.scenario_hash,
        impact=analyze(base, disruption, original, no_action.result),
        no_action=no_action,
        options=options,
        economic_assumptions=rates,
        assumptions=[
            Assumption(
                key="candidate_search",
                kind="assumed",
                text=f"Deterministic bounded candidate search: up to {n_ot} overtime and "
                f"{n_temp} temporary crew-days from the disruption date on. Visits and idle "
                "capacity before the disruption are fixed. Lowest modeled cost applies "
                "only to returned feasible options, including no action. Cold valuation "
                "preparation is outside the solve budget.",
            )
        ],
        stub=False,
    )
    for option in [no_action, *options]:
        _issue(base, option, source_hash)
    _remember(_cache, key, out.model_copy(deep=True))
    return out


def evaluate(
    scenario, disruption, interventions, current_plan=None, economics=None, interactive=True
):
    source_hash = scenario_hash(scenario)
    _check_kinds(disruption, interventions)
    base, original, rates = _prepare(scenario, current_plan, economics, disruption)
    _check_past(base, interventions, disruption_start(base, disruption))
    _check_edits(base, [*disruption, *interventions])
    na = repair(base, disruption)
    hint = _hint(base, na)
    no_action = wrap("no_action", "Keep original crews", original, na, [], rates)
    budget = EVALUATE_BUDGET if interactive else base.config.solve_time_limit_s
    result = _solve(base, [*disruption, *interventions], budget, hint)
    option = wrap(
        "custom",
        "Evaluate manual recovery changes",
        original,
        result,
        interventions,
        rates,
        no_action,
    )
    pins = [e for e in interventions if e.kind == "pin_visit"]
    if pins and option.status in FEASIBLE:
        unpinned = [e for e in interventions if e.kind != "pin_visit"]
        alternate = wrap(
            "custom",
            "Without new pins",
            original,
            _solve(base, [*disruption, *unpinned], budget, hint),
            unpinned,
            rates,
            no_action,
        )
        if alternate.status in FEASIBLE:
            from app.contracts.models import Explanation

            delta = round(option.economics.net_impact_usd - alternate.economics.net_impact_usd, 2)
            option.explanations.extend(
                Explanation(
                    job_id=e.job_id,
                    constraint="pin_visit",
                    text=f"Protecting this set of visits changes modeled cost by ${delta:.2f} "
                    f"vs the computed unpinned option; this is not a proven minimum "
                    f"protection cost.",
                )
                for e in pins
            )
    return _issue(base, option, source_hash)


def approve(scenario, option):
    with _lock:
        saved = _issued.get((option.option_id, _digest(option)))
        known = saved is not None or any(k[0] == option.option_id for k in _issued)
    if not known:
        raise ValueError(
            "Option expired or was not issued by this server. Re-evaluate before approval."
        )
    if saved is None:
        raise ValueError("Option or revision does not match the evaluated recovery. Re-evaluate.")
    base, issued, source_hash = saved
    if (
        source_hash != scenario_hash(scenario)
        or base.scenario_id != scenario.scenario_id
        or issued.result.revision != scenario.revision
    ):
        raise ValueError("Option or revision does not match the evaluated recovery. Re-evaluate.")
    if issued.stub or issued.status not in FEASIBLE or not issued.result.validation.valid:
        raise ValueError("Only a feasible, independently validated live option can be approved.")
    # Reapply authoritative edits and revalidate rather than trusting validation flags.
    effective = _check_edits(base, issued.result.edits)
    _validated(effective, issued.result)
    by_site = {s.site_id: jobs_of(s) for s in effective.sites}
    locks = {job_of_row(p, by_site) for p in effective.current_plan if p.locked}
    rows = [
        PlannedInstall(
            site_id=a.site_id,
            job_id=a.job_id,
            crew_id=a.crew_id,
            date=a.date,
            locked=(a.job_id or a.site_id) in locks,
        )
        for a in issued.result.assignments
    ]
    # Record approved overtime so the per-crew-day cap holds on the next recovery.
    granted = granted_overtime(base)
    for e in issued.result.edits:
        if e.kind == "extend_crew_day":
            granted[e.crew_id, e.date] = granted.get((e.crew_id, e.date), 0) + e.extra_min
    parameters = [p for p in effective.config.parameters if not p.name.startswith(GRANTED + ":")]
    parameters += [
        Parameter(
            name=f"{GRANTED}:{crew}:{d}",
            value=minutes,
            unit="min",
            kind="derived",
            derivation="Overtime approved in an earlier recovery on this crew-day.",
        )
        for (crew, d), minutes in sorted(granted.items())
    ]
    approved_scenario = effective.model_copy(
        update={
            "current_plan": rows,
            "config": effective.config.model_copy(update={"parameters": parameters}),
        }
    )
    approved_scenario.scenario_hash = scenario_hash(approved_scenario)
    current_result(approved_scenario)
    with _lock:
        history = _approved.get(source_hash, [])
        _remember(_approved, source_hash, [*history, approved_scenario][-8:])
    return ApproveResult(
        new_current_plan=rows,
        effective_scenario=approved_scenario,
        summary="Recovery approved for this analysis. "
        "The returned effective scenario preserves resource changes and bookings; "
        "no customers were contacted. This server accepts the new current plan, "
        "including its added capacity, until it restarts.",
        stub=False,
    )
