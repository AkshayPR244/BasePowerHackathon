"""Live deterministic recovery orchestration. No network or autonomous approval."""

import hashlib
import json
import threading
import time
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
from app.planning.edits import apply_edits
from app.planning.solve import InvalidPlanError, _validated, plan
from app.recovery.economics import DEFAULTS, assumptions
from app.recovery.impact import analyze
from app.recovery.options import FEASIBLE, rank, wrap
from app.recovery.repair import current_result, repair, result_for

_lock = threading.RLock()
_cache = OrderedDict()
_issued = OrderedDict()
_LIMIT = 128


def _remember(table, key, value):
    with _lock:
        table[key] = value
        table.move_to_end(key)
        while len(table) > _LIMIT:
            table.popitem(last=False)


def _prepare(scenario, current_plan, economics):
    configured = {p.name: float(p.value) for p in scenario.config.parameters if p.name in DEFAULTS}
    rates = assumptions({**configured, **(economics or {})})
    base = scenario.model_copy(deep=True)
    if current_plan is not None:
        base.current_plan = list(current_plan)
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
    except InvalidPlanError as exc:
        raise ValueError("The supplied current plan is not feasible: " + str(exc)) from exc
    return base, original, rates


def _check_edits(base, edits):
    applied = apply_edits(base, edits)
    if applied.issues:
        raise ValueError(" ".join(i.message for i in applied.issues))
    return applied.scenario


def _issue(base, option, source_hash):
    # Include the full supplied current plan and revision; never trust client approval payloads.
    _remember(
        _issued,
        option.option_id,
        (base.model_copy(deep=True), option.model_copy(deep=True), source_hash),
    )
    return option


def _solve(base, edits, budget):
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
        result.message = "Best found within the solve budget. " + result.message
    return result


def _candidates(base, disruption, cap):
    edited = _check_edits(base, disruption)
    changed = {
        (e.crew_id, e.date) for e in disruption if hasattr(e, "crew_id") and hasattr(e, "date")
    }
    affected_crews = {c for c, _ in changed}
    first = min((d for _, d in changed), default=base.config.planning_start)
    days = sorted(edited.crew_days, key=lambda c: (c.date, c.crew_id))
    # Bound the search; every candidate is explicit and the search is not claimed exhaustive.
    ot = (
        [
            [ExtendCrewDay(crew_id=c.crew_id, date=c.date, extra_min=int(cap))]
            for c in days
            if c.date >= first
            and (not affected_crews or c.crew_id in affected_crews)
            and c.available_min > 0
        ][:4]
        if cap
        else []
    )
    lost = [c for c in base.crew_days if (c.crew_id, c.date) in changed]
    templates = lost or list(base.crew_days[:1])
    temporary = []
    seen = set()
    ids = {c.crew_id for c in base.crew_days}
    for c in templates:
        for day in sorted({d.date for d in base.crew_days if d.date >= first}):
            key = (tuple(sorted(c.skills)), tuple(sorted(c.allowed_clusters)), day)
            if key in seen:
                continue
            seen.add(key)
            name = "TEMP-" + c.crew_id
            while name in ids:
                name += "-R"
            temporary.append(
                [
                    AddCrewDay(
                        crew_id=name,
                        date=day,
                        available_min=c.available_min,
                        skills=c.skills,
                        allowed_clusters=c.allowed_clusters,
                    )
                ]
            )
            if len(temporary) >= 4:
                return ot, temporary
    return ot, temporary


def recover(scenario, disruption, current_plan=None, economics=None, interactive=False):
    source_hash = scenario_hash(scenario)
    base, original, rates = _prepare(scenario, current_plan, economics)
    if any(
        e.kind
        not in {
            "remove_crew_day",
            "reduce_crew_day",
            "change_ready_date",
            "change_appointment",
            "delay_inventory",
        }
        for e in disruption
    ):
        raise ValueError(
            "Disruptions must describe lost resources or changed readiness/appointments."
        )
    _check_edits(base, disruption)
    from app.valuation.value_table import value_table

    valuation_keys = sorted({row.input_hash for row in value_table(base)})
    key = hashlib.sha256(
        json.dumps(
            [
                base.model_dump(mode="json"),
                [e.model_dump(mode="json") for e in disruption],
                economics,
                interactive,
                valuation_keys,
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            for option in [hit.no_action, *hit.options]:
                _issue(base, option, source_hash)
            return hit.model_copy(deep=True)
    no_action = wrap(
        "no_action",
        "Keep original crews; wait for their next open slot",
        original,
        repair(base, disruption),
        [],
        rates,
    )
    t0 = time.monotonic()
    budget = 1.2 if interactive else base.config.solve_time_limit_s
    rebalance = wrap(
        "rebalance",
        "Rebalance existing crews",
        original,
        _solve(base, disruption, budget / 3),
        [],
        rates,
        no_action,
    )
    cap = next(a.value for a in rates if a.key == "max_overtime_min")
    ot, temporary = _candidates(base, disruption, cap)
    options = [rebalance]
    for kind, candidates in [("overtime", ot), ("temporary_capacity", temporary)]:
        best = None
        # Reserve at least one solve for each action kind in interactive mode.
        limit = 1 if interactive else len(candidates)
        for interventions in candidates[:limit]:
            left = max(0.02, budget - (time.monotonic() - t0))
            result = _solve(
                base, [*disruption, *interventions], min(left, budget / (3 * max(1, limit)))
            )
            e = interventions[0]
            label = (
                f"Crew {e.crew_id} +{e.extra_min / 60:g}h overtime on {e.date}"
                if kind == "overtime"
                else f"Add Crew {e.crew_id} on {e.date}"
            )
            candidate = wrap(kind, label, original, result, interventions, rates, no_action)
            if best is None or rank(candidate) < rank(best):
                best = candidate
        if best is not None:
            options.append(best)
    choices = [
        o for o in [no_action, *options] if o.status in FEASIBLE and o.result.validation.valid
    ]
    if choices:
        min(
            choices, key=lambda o: (o.economics.net_impact_usd, o.option_id)
        ).lowest_modeled_cost = True
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
                text="Deterministic bounded candidate search: up to four overtime and "
                "four temporary crew-days (one each in interactive mode). Lowest "
                "modeled cost applies only to returned feasible options, including "
                "no action. Cold valuation preparation is outside the solve budget.",
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
    base, original, rates = _prepare(scenario, current_plan, economics)
    if any(
        e.kind
        not in {
            "remove_crew_day",
            "reduce_crew_day",
            "change_ready_date",
            "change_appointment",
            "delay_inventory",
        }
        for e in disruption
    ):
        raise ValueError("Use intervention edits for added capacity and manual assignments.")
    _check_edits(base, [*disruption, *interventions])
    no_action = wrap(
        "no_action", "Keep original crews", original, repair(base, disruption), [], rates
    )
    result = _solve(
        base, [*disruption, *interventions], 2 if interactive else base.config.solve_time_limit_s
    )
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
            _solve(
                base, [*disruption, *unpinned], 2 if interactive else base.config.solve_time_limit_s
            ),
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
        saved = _issued.get(option.option_id)
    if saved is None:
        raise ValueError(
            "Option expired or was not issued by this server. Re-evaluate before approval."
        )
    base, issued, source_hash = saved
    if (
        source_hash != scenario_hash(scenario)
        or base.scenario_id != scenario.scenario_id
        or issued.result.revision != scenario.revision
        or option != issued
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
    approved_scenario = effective.model_copy(update={"current_plan": rows})
    approved_scenario.scenario_hash = scenario_hash(approved_scenario)
    current_result(approved_scenario)
    return ApproveResult(
        new_current_plan=rows,
        effective_scenario=approved_scenario,
        summary="Recovery approved for this analysis. "
        "The returned effective scenario preserves resource changes and bookings; "
        "no customers were contacted. API sessions do not persist approved scenarios.",
        stub=False,
    )
