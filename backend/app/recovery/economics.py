"""Explicit illustrative costs; positive dollars mean cost relative to the original plan."""

import math

from app.contracts.models import EconomicAssumption, EconomicLine, RecoveryEconomics

BLS = "https://www.bls.gov/oes/2023/may/oes_26420.htm"
DEFAULTS = {
    "hourly_wage": (
        28.33,
        "USD/person-hour",
        "observed",
        "BLS OEWS May 2023 Houston, SOC 47-2111 mean wage. " + BLS,
    ),
    "crew_size": (
        2,
        "people/crew",
        "assumed",
        "Two paid workers per crew; illustrative, not company staffing data.",
    ),
    "overtime_multiplier": (
        1.5,
        "multiplier",
        "assumed",
        "Illustrative overtime premium; not a determination of payroll eligibility.",
    ),
    "temporary_crew_day": (
        453.28,
        "USD/crew-day",
        "assumed",
        "8 hours × 2 people × $28.33; no agency markup or benefits, editable.",
    ),
    "max_overtime_min": (
        120,
        "minutes/crew-day",
        "assumed",
        "Demo limits added capacity to two hours per crew-day.",
    ),
    "travel_cost_per_min": (
        0,
        "USD/minute",
        "assumed",
        "Disabled: no defensible incremental travel cost supplied.",
    ),
    "deadline_penalty": (
        0,
        "USD/missed home",
        "assumed",
        "Disabled: no contractual penalty supplied.",
    ),
    "reschedule_cost": (
        0,
        "USD/customer",
        "assumed",
        "Disabled: no measured customer-contact cost supplied.",
    ),
}


def assumptions(overrides=None):
    overrides = overrides or {}
    unknown = set(overrides) - DEFAULTS.keys()
    if unknown:
        raise ValueError("Unknown economic assumptions: " + ", ".join(sorted(unknown)))
    for key, v in overrides.items():
        if not math.isfinite(v) or v < 0:
            raise ValueError(f"{key} must be finite and nonnegative.")
    cap = overrides.get("max_overtime_min", 120)
    if cap != int(cap):
        raise ValueError("max_overtime_min must be whole minutes.")
    if cap > 120:
        raise ValueError("The demo overtime cap is 120 minutes per crew-day.")
    return [
        EconomicAssumption(
            key=k,
            value=overrides.get(k, v),
            unit=unit,
            kind="assumed" if k in overrides else kind,
            source=("Operator override. " if k in overrides else "") + source,
            editable=True,
        )
        for k, (v, unit, kind, source) in DEFAULTS.items()
    ]


def compute(original, result, interventions, counts, rates, no_action_cost=None):
    values = {a.key: a.value for a in rates}
    if result.objective is None:
        return RecoveryEconomics(
            net_impact_usd=0,
            advantage_vs_no_action_usd=0,
            lines=[
                EconomicLine(
                    label="Not evaluated",
                    amount_usd=0,
                    kind="other",
                    basis="No feasible schedule; not eligible for cost ranking.",
                )
            ],
        )
    ot = sum(e.extra_min for e in interventions if e.kind == "extend_crew_day")
    added = sum(1 for e in interventions if e.kind == "add_crew_day")
    before, after = original.objective, result.objective
    entries = [
        (
            "Existing crew labor",
            0,
            "labor",
            "Existing roster is paid regardless of utilization; no claimed "
            "savings from uncompleted visits.",
        ),
        (
            "Overtime",
            ot / 60 * values["hourly_wage"] * values["crew_size"] * values["overtime_multiplier"],
            "labor",
            f"{ot} authorized minutes / 60 × "
            f"${values['hourly_wage']}/person-hour × {values['crew_size']} "
            f"people × {values['overtime_multiplier']}. Charged for authorized "
            f"capacity, including idle minutes.",
        ),
        (
            "Temporary capacity",
            added * values["temporary_crew_day"],
            "labor",
            f"{added} added crew-days × ${values['temporary_crew_day']}/day; full day charged.",
        ),
        (
            "Lost modeled operating value",
            before.operating_value_usd - after.operating_value_usd,
            "value",
            "Original minus option gross operating margin over the same "
            "evaluation horizon; 2018 hindsight prices, not forecast profit. "
            "Wage inputs are 2023 dollars without inflation conversion; "
            "illustrative comparison.",
        ),
        (
            "Incremental travel",
            (after.travel_allowance_min - before.travel_allowance_min)
            * values["travel_cost_per_min"],
            "other",
            f"Difference in fixed travel allowance minutes × "
            f"${values['travel_cost_per_min']}/min; no route mileage.",
        ),
        (
            "Deadline penalty",
            (counts.deadlines_missed - (before.jobs_late + before.jobs_unscheduled))
            * values["deadline_penalty"],
            "penalty",
            f"Additional missed homes vs original × "
            f"${values['deadline_penalty']}; default disabled.",
        ),
        (
            "Customer rescheduling",
            counts.customers_to_reschedule * values["reschedule_cost"],
            "other",
            f"{counts.customers_to_reschedule} distinct customers × "
            f"${values['reschedule_cost']}; default disabled.",
        ),
    ]
    lines = [
        EconomicLine(label=label, amount_usd=round(amount, 2), kind=kind, basis=basis)
        for label, amount, kind, basis in entries
    ]
    cost = round(sum(x.amount_usd for x in lines), 2)
    direct = sum(x.amount_usd for x in lines if x.kind != "value")
    return RecoveryEconomics(
        net_impact_usd=cost,
        advantage_vs_no_action_usd=round(no_action_cost - cost, 2)
        if no_action_cost is not None
        else 0,
        cost_per_deadline_recovered_usd=round(direct / counts.deadlines_recovered, 2)
        if counts.deadlines_recovered > 0
        else None,
        lines=lines,
    )
