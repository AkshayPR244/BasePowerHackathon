import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from functools import cache
from pathlib import Path

import pytest

from app.contracts.models import (
    AddCrewDay,
    ChangeAppointment,
    DelayInventory,
    ExtendCrewDay,
    MoveVisit,
    PinVisit,
    ReduceCrewDay,
    RemoveCrewDay,
)
from app.data import load_scenario
from app.planning.edits import apply_edits
from app.recovery import service
from app.recovery.economics import assumptions, compute
from app.recovery.impact import analyze
from app.recovery.options import dominated
from app.recovery.repair import repair

STORM_DAY = dt.date(2018, 6, 14)
BA_DAY = dt.date(2018, 6, 7)


def storm():
    return [RemoveCrewDay(crew_id=c, date=STORM_DAY) for c in ("IA", "IB", "BA")]


def ba_out():
    return [RemoveCrewDay(crew_id="BA", date=BA_DAY)]


def standard(revision=1):
    return load_scenario("standard").model_copy(update={"revision": revision})


@cache
def storm_options():
    return service.recover(standard(), storm(), interactive=True)


@cache
def ba_options():
    return service.recover(standard(), ba_out(), interactive=True)


def all_options(out):
    return [out.no_action, *out.options]


# R-19 freeze the past


@pytest.mark.parametrize(("case", "now"), [(storm_options, STORM_DAY), (ba_options, BA_DAY)])
def test_freeze_past_no_option_changes_a_visit_before_the_disruption(case, now):
    for option in all_options(case()):
        for change in option.diff_vs_original.changes:
            for slot in (change.before, change.after):
                assert slot is None or slot.date >= now, (option.kind, change.note)


def test_freeze_past_evaluate_keeps_the_past():
    option = service.evaluate(standard(), ba_out(), [])
    assert all(
        slot is None or slot.date >= BA_DAY
        for c in option.diff_vs_original.changes
        for slot in (c.before, c.after)
    )


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (MoveVisit(job_id="N-02-B", crew_id="BA", date=dt.date(2018, 6, 5)), "into the past"),
        (ExtendCrewDay(crew_id="BA", date=dt.date(2018, 6, 5), extra_min=60), "in the past"),
    ],
)
def test_freeze_past_rejects_changes_before_now(edit, message):
    with pytest.raises(ValueError, match=message) as err:
        service.evaluate(standard(), ba_out(), [edit])
    assert "Thu 7 Jun" in str(err.value)


def test_freeze_past_rejects_moving_a_past_visit():
    s = standard()
    past = next(p for p in s.current_plan if p.date < BA_DAY and p.crew_id == "BA")
    with pytest.raises(ValueError, match="Past visits cannot move"):
        service.evaluate(s, ba_out(), [MoveVisit(job_id=past.job_id, crew_id="BA", date=BA_DAY)])


def test_freeze_past_candidates_start_now_and_precede_displaced_dates():
    s = standard()
    edits = [
        RemoveCrewDay(crew_id="IA", date=BA_DAY),
        RemoveCrewDay(crew_id="BA", date=dt.date(2018, 6, 13)),
    ]
    base, original, _ = service._prepare(s, None, None, edits)
    ot, temp = service._candidates(base, edits, 120, original, repair(base, edits))
    dates = [e.date for group in [*ot, *temp] for e in group]
    assert dates and min(dates) >= BA_DAY
    battery = [e.date for group in ot for e in group if e.crew_id == "BA"] + [
        e.date for group in temp for e in group if "battery" in e.skills
    ]
    assert any(d < dt.date(2018, 6, 13) for d in battery)


# R-20 deadlines recovered


@pytest.mark.parametrize("case", [storm_options, ba_options])
def test_deadlines_recovered_is_no_action_misses_minus_option_misses(case):
    out = case()
    base = out.no_action.counts.deadlines_missed
    assert out.no_action.counts.deadlines_recovered == 0
    for option in out.options:
        expected = max(0, base - option.counts.deadlines_missed)
        assert option.counts.deadlines_recovered == expected <= base


def test_recovered_cost_per_deadline_uses_no_action_baseline():
    out = ba_options()
    na = out.no_action
    for option in out.options:
        eco, n = option.economics, option.counts.deadlines_recovered
        if n:
            expected = round((eco.net_impact_usd - na.economics.net_impact_usd) / n, 2)
            assert eco.cost_per_deadline_recovered_usd == pytest.approx(expected, abs=0.01)
        else:
            assert eco.cost_per_deadline_recovered_usd is None


# R-21 temporary capacity after a storm day


def test_temporary_after_storm_uses_next_business_day():
    out = storm_options()
    temps = [e for o in out.options for e in o.intervention_edits if e.kind == "add_crew_day"]
    assert temps
    assert all(e.date != STORM_DAY for e in temps)
    base, original, _ = service._prepare(standard(), None, None, storm())
    _, candidates = service._candidates(base, storm(), 120, original, repair(base, storm()))
    assert candidates
    assert {e.date for group in candidates for e in group} == {dt.date(2018, 6, 15)}


# R-22 interactive budget


def test_interactive_budget_options_and_evaluate():
    s = standard(revision=4242)
    service.recover(load_scenario("tiny_two_visit"), [], interactive=True)  # warm imports
    for disruption in (storm(), ba_out()):
        t0 = time.monotonic()
        out = service.recover(s, disruption, interactive=True)
        assert time.monotonic() - t0 < 3.5
        for option in out.options:
            if option.status == "feasible":
                assert not option.proven_optimal
                assert "not proven" in option.result.message
    t0 = time.monotonic()
    edit = ExtendCrewDay(crew_id="BA", date=dt.date(2018, 6, 11), extra_min=120)
    service.evaluate(s, ba_out(), [edit])
    assert time.monotonic() - t0 < 3.5


def test_interactive_budget_price_change_reuses_solved_plans(monkeypatch):
    s = standard(revision=4243)
    first = service.recover(s, ba_out(), interactive=True)

    def fail(*a, **kw):
        raise AssertionError("A price change must not re-solve")

    monkeypatch.setattr(service, "_solve", fail)
    second = service.recover(s, ba_out(), economics={"hourly_wage": 40}, interactive=True)
    plans = {o.kind: o.result.assignments for o in all_options(first)}
    for option in all_options(second):
        if option.kind in plans:
            assert option.result.assignments == plans[option.kind]


# R-23 reproducible


SCRIPT = """
import datetime as dt, hashlib, json
from app.contracts.models import RemoveCrewDay
from app.data import load_scenario
from app.recovery.service import recover
s = load_scenario("standard").model_copy(update={"revision": 1})
out = recover(s, [RemoveCrewDay(crew_id="BA", date=dt.date(2018, 6, 7))], interactive=True)
rows = [(o.option_id, sorted((a.job_id or a.site_id, a.crew_id, str(a.date))
        for a in o.result.assignments)) for o in [out.no_action, *out.options]]
print(json.dumps(rows))
"""


def test_reproducible_options_in_fresh_processes():
    backend = Path(__file__).resolve().parents[2]
    runs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(backend)}
        done = subprocess.run(
            [sys.executable, "-c", SCRIPT],
            cwd=backend,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
        runs.append(json.loads(done.stdout.strip().splitlines()[-1]))
    assert runs[0] == runs[1]


# R-24 labels


@pytest.mark.parametrize("case", [storm_options, ba_options])
def test_labels_use_human_dates(case):
    for option in all_options(case()):
        assert not re.search(r"\d{4}-\d{2}-\d{2}", option.action_label)
        if option.kind in {"overtime", "temporary_capacity"}:
            assert re.search(
                r"on (Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2} [A-Z][a-z]{2}$", option.action_label
            )
        assert "Recommended" not in option.action_label


# QA fixes


def test_approve_accepts_an_older_issue_of_the_same_option():
    s = standard(revision=31)
    first = next(o for o in service.recover(s, ba_out(), interactive=True).options)
    service._cache.clear()
    service._plans.clear()
    again = next(o for o in service.recover(s, ba_out(), interactive=True).options)
    assert again.option_id == first.option_id
    stale = first.model_copy(deep=True)
    stale.result.solve_ms += 1234
    stale.result.message = "Older issue"
    stale.lowest_modeled_cost = not stale.lowest_modeled_cost
    assert service.approve(s, stale).new_current_plan


@pytest.mark.parametrize("field", ["label", "economics", "assignments"])
def test_approve_rejects_tampering(field):
    s = standard(revision=32)
    option = service.evaluate(s, ba_out(), [])
    bad = option.model_copy(deep=True)
    if field == "label":
        bad.action_label = "Something else"
    elif field == "economics":
        bad.economics.net_impact_usd -= 100
    else:
        bad.result.assignments[0].date = dt.date(2018, 6, 15)
    with pytest.raises(ValueError, match="does not match"):
        service.approve(s, bad)
    with pytest.raises(ValueError):
        service.approve(s.model_copy(update={"revision": 33}), option)


def test_paid_option_kept_unless_dominated():
    out = ba_options()
    feasible = all_options(out)
    for option in out.options:
        if option.kind != "rebalance":
            assert not dominated(option, feasible)
    cheap, dear = out.no_action.model_copy(deep=True), out.no_action.model_copy(deep=True)
    dear.economics.net_impact_usd += 10
    assert dominated(dear, [cheap]) and not dominated(cheap, [dear])
    fewer = dear.model_copy(deep=True)
    fewer.counts.deadlines_missed -= 1
    assert not dominated(fewer, [cheap])
    assert sum(o.lowest_modeled_cost for o in feasible) == 1
    lowest = next(o for o in feasible if o.lowest_modeled_cost)
    assert lowest.economics.net_impact_usd == min(o.economics.net_impact_usd for o in feasible)


def test_overtime_skips_crew_days_the_disruption_cut():
    s = standard()
    cut = [ReduceCrewDay(crew_id="BA", date=dt.date(2018, 6, 8), available_min=240)]
    base, original, _ = service._prepare(s, None, None, cut)
    ot, _ = service._candidates(base, cut, 120, original, repair(base, cut))
    assert all((e.crew_id, e.date) != ("BA", dt.date(2018, 6, 8)) for g in ot for e in g)


def test_add_crew_day_is_capped_and_cannot_readd_the_missing_crew():
    s = standard()
    big = AddCrewDay(
        crew_id="TEMP", date=BA_DAY, available_min=5000, skills=["battery"], allowed_clusters=["N"]
    )
    assert "at most 480 minutes" in apply_edits(s, [big]).issues[0].message
    same = AddCrewDay(
        crew_id="BA", date=BA_DAY, available_min=480, skills=["battery"], allowed_clusters=["N"]
    )
    issues = apply_edits(s, [*ba_out(), same]).issues
    assert issues and "BA is out" in issues[0].message


def test_temporary_crew_day_follows_wage_and_crew_size():
    rates = {a.key: a.value for a in assumptions({"hourly_wage": 40, "crew_size": 3})}
    assert rates["temporary_crew_day"] == 960
    assert {a.key: a.value for a in assumptions({"temporary_crew_day": 500})}[
        "temporary_crew_day"
    ] == 500


@pytest.mark.parametrize(
    "overrides",
    [
        {"crew_size": 2.5},
        {"crew_size": 0},
        {"overtime_multiplier": 0.5},
        {"hourly_wage": 1e308},
        {"temporary_crew_day": 1e308},
    ],
)
def test_bad_economics_overrides_are_clean_input_issues(overrides):
    with pytest.raises(ValueError) as err:
        assumptions(overrides)
    assert "validation error" not in str(err.value).lower()
    assert next(iter(overrides)) in str(err.value)


def test_infeasible_custom_option_shows_no_changes():
    s = load_scenario("tiny_two_visit")
    # A battery day on the first day has no install before it.
    moves = [MoveVisit(job_id="H1-B", crew_id="B", date=dt.date(2018, 6, 4))]
    option = service.evaluate(s, [], moves)
    assert option.status == "infeasible"
    assert option.diff_vs_original.changes == []
    assert option.explanations == [] and option.crew_load == []
    assert option.counts.visits_moved == option.counts.customers_to_reschedule == 0


def test_move_visit_checks_crew_skill():
    with pytest.raises(ValueError, match="Crew IA does not do battery days"):
        service.evaluate(
            standard(),
            ba_out(),
            [MoveVisit(job_id="N-02-B", crew_id="IA", date=dt.date(2018, 6, 12))],
        )


@pytest.mark.parametrize(
    "edit",
    [
        RemoveCrewDay(crew_id="IA", date=dt.date(2018, 6, 12)),
        ReduceCrewDay(crew_id="IA", date=dt.date(2018, 6, 12), available_min=10),
        ChangeAppointment(job_id="N-02-B", available_from=dt.date(2018, 6, 12)),
        DelayInventory(configuration_id="B13", from_date=BA_DAY, to_date=dt.date(2018, 6, 8)),
    ],
)
def test_evaluate_rejects_disruptions_as_interventions(edit):
    with pytest.raises(ValueError, match="disruption"):
        service.evaluate(standard(), ba_out(), [edit])


def test_cache_is_least_recently_used():
    table = service.OrderedDict()
    for k in "abc":
        service._remember(table, k, k, limit=3)
    assert service._recall(table, "a") == "a"
    service._remember(table, "d", "d", limit=3)
    assert list(table) == ["c", "a", "d"]


def test_rebalance_same_as_no_action_is_marked():
    out = storm_options()
    rebalance = next(o for o in out.options if o.kind == "rebalance")
    same = sorted((a.job_id, a.crew_id, a.date) for a in rebalance.result.assignments) == sorted(
        (a.job_id, a.crew_id, a.date) for a in out.no_action.result.assignments
    )
    assert same == ("same plan as no action" in rebalance.action_label)
    assert not (same and rebalance.lowest_modeled_cost)


def test_impact_pushed_excludes_direct_and_delay_without_repair():
    out = storm_options()
    steps = {c.kind: set(c.job_ids) for c in out.impact.cascade}
    assert not steps["direct"] & steps["pushed"]
    s = standard()
    delay = [DelayInventory(configuration_id="B13", from_date=BA_DAY, to_date=dt.date(2018, 6, 8))]
    base, original, _ = service._prepare(s, None, None, delay)
    failed = original.model_copy(update={"objective": None, "assignments": []})
    impact = analyze(base, delay, original, failed)
    window = {
        a.job_id
        for a in original.assignments
        if a.visit_type == "battery_day" and BA_DAY <= a.date < dt.date(2018, 6, 8)
    }
    assert set(impact.affected_job_ids) == window


def test_deadline_penalty_never_negative():
    s = load_scenario("tiny_two_visit")
    out = service.recover(s, [RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5))])
    option = out.no_action
    worse = option.result.model_copy(deep=True)
    better_counts = option.counts.model_copy(update={"deadlines_missed": 0})
    original = worse.model_copy(deep=True)
    original.objective = original.objective.model_copy(update={"jobs_late": 3})
    eco = compute(original, worse, [], better_counts, assumptions({"deadline_penalty": 100}))
    line = next(x for x in eco.lines if x.label == "Deadline penalty")
    assert line.amount_usd == 0


def test_overtime_cap_holds_across_approvals():
    s = standard(revision=51)
    day = dt.date(2018, 6, 8)
    option = service.evaluate(s, ba_out(), [ExtendCrewDay(crew_id="BA", date=day, extra_min=120)])
    approved = service.approve(s, option)
    more = [ExtendCrewDay(crew_id="BA", date=day, extra_min=60)]
    with pytest.raises(ValueError, match="Overtime exceeds"):
        service.evaluate(approved.effective_scenario, [], more)
    with pytest.raises(ValueError, match="Overtime exceeds"):
        service.evaluate(s, [], more, current_plan=approved.new_current_plan)


def test_approved_plan_with_temporary_crew_loads_as_current_plan():
    s = standard(revision=52)
    out = service.recover(s, ba_out(), interactive=True)
    temp = next(o for o in out.options if o.kind == "temporary_capacity")
    approved = service.approve(s, temp)
    later = [RemoveCrewDay(crew_id="IA", date=dt.date(2018, 6, 11))]
    again = service.recover(s, later, current_plan=approved.new_current_plan, interactive=True)
    assert again.no_action.result.validation.valid


def test_pin_still_reports_cost():
    s = load_scenario("tiny_two_visit")
    option = service.evaluate(s, [], [PinVisit(job_id="H3-B")])
    assert any(e.constraint == "pin_visit" for e in option.explanations)
