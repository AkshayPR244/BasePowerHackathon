"""Build the stub fixtures behind the recovery and weather seams.

Run from backend/: PYTHONPATH=. python ../scripts/build_stubs.py

Plans, counts, diffs, cascade IDs, and crew load come from the real planner on the standard
scenario with the 14 Jun 2018 storm case (all three crews lose the day). No-action uses
earliest-deadline-first as a stand-in. Economics and explanations are placeholders.
Storm events are real Houston Hobby observations. Every payload carries stub=true.
Lane R replaces backend/app/recovery/fixtures. Lane W replaces backend/app/replay/fixtures.
"""

import datetime as dt
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter

from app.compare.diff import diff_plans
from app.contracts.hashing import scenario_hash
from app.contracts.models import (
    AddCrewDay,
    ApproveResult,
    CascadeStep,
    Case,
    CrewLoad,
    EconomicAssumption,
    EconomicLine,
    Explanation,
    ImpactAnalysis,
    PlannedInstall,
    PlanRequest,
    ProvenanceNote,
    RecoveryCounts,
    RecoveryEconomics,
    RecoveryOption,
    RecoveryOptionsResult,
    RemoveCrewDay,
    SeasonReplay,
    SeasonReplayEvent,
    SeasonTotals,
    StormEvent,
)
from app.data import load_scenario
from app.planning.solve import plan

ROOT = Path(__file__).resolve().parents[1] / "backend" / "app"
STORM = dt.date(2018, 6, 14)
NEXT = dt.date(2018, 6, 15)
CREWS = ("IA", "IB", "BA")
IEM = (
    "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py (station HOU, Houston Hobby, "
    "routine METAR, 08:00-17:00 local, retrieved 2026-09-26)"
)
RULE = (
    "Modeled rule: a thunderstorm report, or at least 7.6 mm of rain in one hour, during "
    "08:00-17:00 stops electrical work, so every crew loses that day."
)
DISRUPTION = [RemoveCrewDay(crew_id=c, date=STORM) for c in CREWS]
STORMS = [  # routine METAR, weekdays, work hours
    ("2018-06-14", 25.9, 42.6, 2),
    ("2018-06-20", 1.0, 37.0, 1),
    ("2018-06-25", 4.3, 48.2, 1),
    ("2018-06-27", 1.8, 18.5, 1),
    ("2018-07-04", 145.0, 35.2, 1),
    ("2018-07-05", 14.7, 14.8, 1),
    ("2018-07-09", 14.5, 20.4, 1),
    ("2018-07-12", 0.0, 14.8, 1),
    ("2018-07-31", 1.0, 63.0, 2),
]


def counts(r, no_action_missed: int) -> RecoveryCounts:
    o = r.objective
    missed = o.jobs_late + o.jobs_unscheduled - o.jobs_blocked
    return RecoveryCounts(
        deadlines_missed=missed,
        deadlines_recovered=max(0, no_action_missed - missed),
        delay_days=o.total_delay_days,
        visits_moved=o.visits_moved or 0,
        customers_to_reschedule=o.customers_to_reschedule or 0,
        unscheduled=o.jobs_unscheduled - o.jobs_blocked,
    )


def crew_load(before, after) -> list[CrewLoad]:
    def per_day(r):
        return {
            (u.crew_id, u.date): (u.onsite_min + u.travel_min) / u.available_min
            for u in r.crew_days
            if u.available_min
        }

    b, a = per_day(before), per_day(after)
    return [
        CrewLoad(
            crew_id=c,
            date=d,
            before=round(b.get((c, d), 0.0), 4),
            after=round(a.get((c, d), 0.0), 4),
        )
        for c, d in sorted(set(b) | set(a))
    ]


def economics(labor: float, value_lost: float, recovered: int, no_action_net: float):
    lines = [
        EconomicLine(
            label="Energy value lost vs the original plan",
            amount_usd=round(value_lost, 2),
            kind="value",
            basis="Value table: ERCOT 2018 LZ_HOUSTON prices, modeled Powerwall 3. Real number.",
        )
    ]
    if labor:
        lines.insert(
            0,
            EconomicLine(
                label="Extra crew labor",
                amount_usd=labor,
                kind="labor",
                basis="STUB placeholder. Lane R computes it from the BLS Houston electrician wage.",
            ),
        )
    net = round(labor + value_lost, 2)
    return RecoveryEconomics(
        net_impact_usd=net,
        advantage_vs_no_action_usd=round(no_action_net - net, 2),
        cost_per_deadline_recovered_usd=round(labor / recovered, 2)
        if recovered and labor
        else None,
        lines=lines,
    )


def option(option_id, kind, label, edits, r, original, no_action, labor, na_missed, na_net):
    c = counts(r, na_missed)
    value_lost = original.objective.operating_value_usd - r.objective.operating_value_usd
    return RecoveryOption(
        option_id=option_id,
        kind=kind,
        action_label=label,
        intervention_edits=edits,
        status=r.status,
        proven_optimal=r.status == "optimal",
        result=r,
        diff_vs_original=diff_plans(original, r),
        diff_vs_no_action=None if no_action is None else diff_plans(no_action, r),
        counts=c,
        economics=economics(labor, value_lost, c.deadlines_recovered, na_net),
        overtime_min=120 if kind == "overtime" else 0,
        explanations=[
            Explanation(
                job_id=ch.job_id or ch.site_id,
                text=f"STUB: {ch.note} Lane R names the constraint.",
                constraint="stub",
            )
            for ch in diff_plans(original, r).changes[:3]
        ],
        crew_load=crew_load(original, r),
        stub=True,
    )


def dump(path: Path, value, many=False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if many:
        text = TypeAdapter(list[type(value[0])]).dump_json(value, indent=2).decode()
    else:
        text = value.model_dump_json(indent=2)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT.parent))


def main():
    s = load_scenario("standard")
    original = plan(s, PlanRequest(scenario_id="standard", revision=0))
    base = dict(scenario_id="standard", revision=1, mode="recovery", edits=DISRUPTION)
    no_action = plan(s, PlanRequest(**base, algorithm="baseline_edf"))
    rebalance = plan(s, PlanRequest(**base))
    temp = AddCrewDay(
        crew_id="BT",
        date=NEXT,
        available_min=480,
        skills=["battery"],
        allowed_clusters=["N", "S", "W"],
    )
    temporary = plan(s, PlanRequest(**{**base, "edits": [*DISRUPTION, temp]}))

    na_value_lost = original.objective.operating_value_usd - no_action.objective.operating_value_usd
    na_missed = counts(no_action, 0).deadlines_missed
    na = option(
        "no_action",
        "no_action",
        "No action (STUB: earliest-deadline-first stand-in)",
        [],
        no_action,
        original,
        None,
        0.0,
        na_missed,
        round(na_value_lost, 2),
    )
    na_net = na.economics.net_impact_usd
    options = [
        option(
            "rebalance",
            "rebalance",
            "Rebalance existing crews",
            [],
            rebalance,
            original,
            no_action,
            0.0,
            na_missed,
            na_net,
        ),
        option(
            "overtime",
            "overtime",
            "Crew BA +2h overtime Fri 15 Jun (STUB: not modeled yet)",
            [],
            rebalance,
            original,
            no_action,
            180.0,
            na_missed,
            na_net,
        ),
        option(
            "temporary_capacity",
            "temporary_capacity",
            "Temporary battery crew BT Fri 15 Jun",
            [temp],
            temporary,
            original,
            no_action,
            950.0,
            na_missed,
            na_net,
        ),
    ]
    cheapest = min(options, key=lambda o: o.economics.net_impact_usd)
    options = [o.model_copy(update={"lowest_modeled_cost": o is cheapest}) for o in options]

    affected = [p.job_id for p in s.current_plan if p.date == STORM]
    pushed = [c.job_id for c in diff_plans(original, rebalance).changes if c.job_id]
    at_risk = sorted(
        {a.site_id for a in no_action.assignments if a.days_late}
        | {u.site_id for u in no_action.unscheduled}
    )
    batteries = sum(1 for j in affected if j.endswith("-B"))
    result = RecoveryOptionsResult(
        revision=1,
        scenario_hash=scenario_hash(s, DISRUPTION),
        impact=ImpactAnalysis(
            headline=(
                f"Storm on Thu 14 Jun stops all 3 crews. {len(affected)} visits lose their day, "
                f"{batteries} of them battery days. {len(at_risk)} deadlines at risk if nothing "
                "changes."
            ),
            affected_job_ids=affected,
            lost_capacity_min=sum(c.available_min for c in s.crew_days if c.date == STORM),
            cascade=[
                CascadeStep(
                    kind="disruption", label="Storm: every crew out Thu 14 Jun", job_ids=[]
                ),
                CascadeStep(kind="direct", label="Visits planned on Thu 14 Jun", job_ids=affected),
                CascadeStep(kind="pushed", label="Visits moved to recover", job_ids=pushed),
                CascadeStep(
                    kind="commitment", label="Deadlines at risk with no action", job_ids=at_risk
                ),
            ],
            deadlines_at_risk=len(at_risk),
        ),
        no_action=na,
        options=options,
        economic_assumptions=[
            EconomicAssumption(
                key="electrician_wage_usd_per_h",
                value=0.0,
                unit="USD/h",
                kind="assumed",
                source="STUB. Lane R cites BLS OEWS Houston.",
                editable=True,
            ),
            EconomicAssumption(
                key="overtime_multiplier",
                value=1.5,
                unit="x",
                kind="assumed",
                source="Time and a half for hours over 40 (FLSA).",
                editable=True,
            ),
            EconomicAssumption(
                key="temporary_crew_day_usd",
                value=0.0,
                unit="USD",
                kind="assumed",
                source="STUB. Lane R tags it.",
                editable=True,
            ),
            EconomicAssumption(
                key="deadline_penalty_usd",
                value=0.0,
                unit="USD",
                kind="assumed",
                source="Off by default.",
                editable=True,
            ),
        ],
        assumptions=list(rebalance.assumptions),
        stub=True,
    )
    fixtures = ROOT / "recovery" / "fixtures"
    dump(fixtures / "options.json", result)
    custom = option(
        "custom",
        "custom",
        "Temporary battery crew BT Fri 15 Jun",
        [temp],
        temporary,
        original,
        no_action,
        950.0,
        na_missed,
        na_net,
    )
    dump(fixtures / "evaluate.json", custom)
    dump(
        fixtures / "approve.json",
        ApproveResult(
            new_current_plan=[
                PlannedInstall(
                    site_id=a.site_id,
                    job_id=a.job_id,
                    crew_id=a.crew_id,
                    date=a.date,
                    locked=a.date <= STORM,
                )
                for a in rebalance.assignments
            ],
            summary="STUB: Rebalance existing crews approved. Past days are locked.",
            stub=True,
        ),
    )

    replay = ROOT / "replay" / "fixtures"
    storms = [
        StormEvent(
            event_id=f"hou-{d}",
            date=d,
            rainfall_mm=rain,
            max_wind_kmh=wind,
            thunder_hours=hours,
            source=IEM,
            stub=True,
        )
        for d, rain, wind, hours in STORMS
    ]
    dump(replay / "storms.json", storms, many=True)
    case = Case(
        case_id="storm-2018-06-14",
        name="Thunderstorm, Thu 14 Jun 2018",
        date=STORM,
        summary=(
            "This replay applies a modeled operational disruption to a real historical storm. "
            "Hobby observed thunder in 2 work hours and 25.9 mm of rain."
        ),
        storm_event_id="hou-2018-06-14",
        disruption=DISRUPTION,
        modeled_rule=RULE,
        provenance=[
            ProvenanceNote(input="weather", kind="observed", source=IEM),
            ProvenanceNote(input="lost crew-days", kind="modeled", source=RULE),
        ],
        stub=True,
    )
    dump(replay / "cases.json", [case], many=True)
    best = next(o for o in options if o.lowest_modeled_cost)
    event = SeasonReplayEvent(
        case_id=case.case_id,
        no_action=na.counts,
        no_action_net_impact_usd=na.economics.net_impact_usd,
        recovery=best.counts,
        recovery_net_impact_usd=best.economics.net_impact_usd,
        chosen_option_kind=best.kind,
        solve_ms=best.result.solve_ms,
    )
    dump(
        replay / "season_replay.json",
        SeasonReplay(
            replay_id="season-2018-jun-jul",
            events=[event],
            totals=SeasonTotals(
                events_replayed=1,
                deadline_misses_no_action=na.counts.deadlines_missed,
                deadline_misses_recovery=best.counts.deadlines_missed,
                deadlines_recovered=best.counts.deadlines_recovered,
                modeled_cost_no_action_usd=na.economics.net_impact_usd,
                modeled_cost_recovery_usd=best.economics.net_impact_usd,
                median_solve_ms=best.result.solve_ms,
            ),
            stress_tests=None,
            stub=True,
        ),
    )
    print("counts:", {o.option_id: o.counts.model_dump() for o in [na, *options]})
    print(Counter(o.status for o in [na, *options]))


if __name__ == "__main__":
    main()
