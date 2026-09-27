"""Typed operational specifications and disruption recipes; no UI narrative metadata."""

import datetime as dt
from dataclasses import dataclass

from app.contracts.calendar import business_days
from app.contracts.models import ChangeAppointment, ChangeReadyDate, DelayInventory, RemoveCrewDay
from app.data.generate_standard import CrewSpec, Spec


@dataclass
class SuiteSpec:
    seed: int
    spec: Spec
    disruption: str
    recovery_class: str = "recoverable"
    description: str = ""


def _spec(name, **kwargs):
    defaults = dict(
        scenario_id=name,
        n_homes=12,
        window_days=8,
        overflow_days=2,
        ready_window_days=2,
        deadline_business_days=5,
        install_durations_min=(90, 120),
        battery_durations_min=(60, 75),
        lock_policy="none",
        num_workers=1,
        solve_time_limit_s=12,
        plan_work_limit=5,
        evaluation_end=dt.date(2018, 6, 24),
    )
    return Spec(**(defaults | kwargs))


SUITE = {
    "balanced_small": SuiteSpec(
        101,
        _spec("balanced_small"),
        "none",
        description="12 homes; spare capacity and on-time commitments.",
    ),
    "tight_feasible": SuiteSpec(
        102,
        _spec(
            "tight_feasible",
            n_homes=30,
            window_days=7,
            ready_window_days=1,
            deadline_business_days=6,
            install_durations_min=(120,),
            battery_durations_min=(75,),
            overflow_days=2,
        ),
        "battery_out",
        description="30 homes; battery capacity has little slack.",
    ),
    "crew_out_recoverable": SuiteSpec(
        103,
        _spec("crew_out_recoverable", n_homes=24),
        "install_out",
        description="A busy install crew-day is lost.",
    ),
    "inventory_delay_recoverable": SuiteSpec(
        104,
        _spec("inventory_delay_recoverable", n_homes=18),
        "receipt",
        description="A scheduled battery receipt slips one business day.",
    ),
    "readiness_appointment": SuiteSpec(
        105,
        _spec("readiness_appointment"),
        "readiness",
        description="One home's readiness and battery appointment shift.",
    ),
    "skill_cluster_bottleneck": SuiteSpec(
        106,
        _spec(
            "skill_cluster_bottleneck",
            centers={"N": (-95.4, 29.81), "S": (-95.37, 29.68)},
            crew_specs=(
                CrewSpec("IN", ("install",), ("N",)),
                CrewSpec("IS", ("install",), ("S",)),
                CrewSpec("BN", ("battery",), ("N",), 1),
                CrewSpec("BS", ("battery",), ("S",), 1),
            ),
        ),
        "battery_out",
        description="Territory-specific crews cannot substitute across clusters.",
    ),
    "two_visit_cascade": SuiteSpec(
        107,
        _spec("two_visit_cascade", min_gap_business_days=2),
        "cascade",
        description="A moved install pushes its dependent battery visit.",
    ),
    "locked_infeasible": SuiteSpec(
        108,
        _spec("locked_infeasible", lock_policy="all"),
        "install_out",
        "locked-infeasible",
        "A disrupted locked visit cannot move.",
    ),
    "late_overflow": SuiteSpec(
        109,
        _spec(
            "late_overflow",
            window_days=5,
            overflow_days=4,
            ready_window_days=1,
            deadline_business_days=4,
            inventory_receipts=((0, 12),),
        ),
        "overflow",
        "late-but-feasible",
        "A delivery after deadlines requires overflow workdays.",
    ),
    "value_sensitive": SuiteSpec(
        110,
        _spec(
            "value_sensitive",
            centers={"N": (-95.4, 29.81)},
            ready_window_days=1,
            deadline_business_days=7,
            inventory_receipts=((0, 12),),
        ),
        "battery_out",
        description="Compare commissioning order under two objective policies.",
    ),
}


def primary_disruption(scenario):
    """Choose explicit stable edits from a solved healthy schedule, never from prose."""
    recipe = SUITE[scenario.scenario_id].disruption
    days = business_days(scenario.config.planning_start, 30)

    def next_day(day, n=1):
        return days[days.index(day) + n]

    if recipe == "none":
        return []
    if recipe in {"install_out", "battery_out"}:
        suffix = "-I" if recipe == "install_out" else "-B"
        counts = {}
        for row in scenario.current_plan:
            if row.job_id.endswith(suffix):
                key = (row.date, row.crew_id)
                counts[key] = counts.get(key, 0) + 1
        day, crew = min(counts, key=lambda k: (-counts[k], k))
        return [RemoveCrewDay(crew_id=crew, date=day)]
    if recipe in {"receipt", "overflow"}:
        receipt = sorted(scenario.inventory, key=lambda r: r.available_date)[0]
        first_battery = min(r.date for r in scenario.current_plan if r.job_id.endswith("-B"))
        target = next_day(first_battery) if recipe == "receipt" else days[5]
        return [
            DelayInventory(
                configuration_id=receipt.configuration_id,
                from_date=receipt.available_date,
                to_date=target,
            )
        ]
    installs = sorted(
        (r for r in scenario.current_plan if r.job_id.endswith("-I")),
        key=lambda r: (r.date, r.job_id),
    )
    row = installs[0]
    battery = next(
        r for r in scenario.current_plan if r.site_id == row.site_id and r.job_id.endswith("-B")
    )
    target = next_day(battery.date)
    if recipe == "cascade":
        return [ChangeAppointment(job_id=row.job_id, available_from=target, available_to=target)]
    return [
        ChangeReadyDate(site_id=row.site_id, ready_date=next_day(row.date)),
        ChangeAppointment(job_id=battery.job_id, available_from=target, available_to=target),
    ]
