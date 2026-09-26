"""Expand homes into crew visits. Shared by the planner and the independent validator."""

import datetime as dt
from dataclasses import dataclass

from app.contracts.calendar import business_ordinal
from app.contracts.enums import VisitType
from app.contracts.models import PlannedInstall, Scenario, Site


@dataclass(frozen=True)
class Job:
    job_id: str
    site_id: str
    visit_type: VisitType | None
    duration_min: int
    required_skill: str
    final: bool  # carries the deadline, the energy value, and the battery

    @property
    def assignment_job_id(self) -> str | None:
        return None if self.visit_type is None else self.job_id


def jobs_of(site: Site) -> list[Job]:
    if not site.visits:
        return [Job(site.site_id, site.site_id, None, site.duration_min, site.required_skill, True)]
    order = {VisitType.install: 0, VisitType.battery_day: 1}
    return [
        Job(
            v.job_id,
            site.site_id,
            v.visit_type,
            v.duration_min,
            v.required_skill,
            v.visit_type == VisitType.battery_day,
        )
        for v in sorted(site.visits, key=lambda v: order[v.visit_type])
    ]


def all_jobs(scenario: Scenario) -> dict[str, Job]:
    return {j.job_id: j for s in scenario.sites for j in jobs_of(s)}


def job_of_row(row: PlannedInstall, jobs_by_site: dict[str, list[Job]]) -> str | None:
    """The job a current-plan row refers to. One-visit rows name the home only."""
    jobs = jobs_by_site.get(row.site_id)
    if not jobs:
        return None
    if row.job_id is None:
        return next(j.job_id for j in jobs if j.final)
    return row.job_id if any(j.job_id == row.job_id for j in jobs) else None


def min_gap(scenario: Scenario) -> int:
    gap = scenario.config.min_gap_business_days
    return 1 if gap is None else gap


def gap_ok(install: dt.date, battery_day: dt.date, gap: int, origin: dt.date) -> bool:
    return business_ordinal(battery_day, origin) - business_ordinal(install, origin) >= gap
