"""Shared greedy placement state for the baselines. Same rules as the CP-SAT model."""

import datetime as dt

from app.contracts.models import Scenario
from app.contracts.visits import Job, gap_ok, min_gap
from app.planning.model import Eligibility

Slot = tuple[str, dt.date]


class Board:
    def __init__(self, scenario: Scenario, elig: Eligibility):
        self.sites = {s.site_id: s for s in scenario.sites}
        self.jobs = elig.jobs
        self.travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
        self.avail = {(c.crew_id, c.date): c.available_min for c in scenario.crew_days}
        self.days = sorted({c.date for c in scenario.crew_days})
        self.gap, self.origin = min_gap(scenario), scenario.config.planning_start
        self.stock: dict[str, dict[dt.date, int]] = {}
        for cfg in {s.configuration_id for s in scenario.sites}:
            self.stock[cfg] = {
                d: sum(
                    r.quantity
                    for r in scenario.inventory
                    if r.configuration_id == cfg and r.available_date <= d
                )
                for d in self.days
            }
        self.used = {cfg: dict.fromkeys(self.days, 0) for cfg in self.stock}
        self.cluster: dict[Slot, str] = {}
        self.minutes: dict[Slot, int] = {}
        self.placed: dict[str, Slot] = {}  # job_id -> slot

    def predecessor(self, job: Job) -> Job | None:
        if not job.final or job.visit_type is None:
            return None
        return next(j for j in self.jobs.values() if j.site_id == job.site_id and not j.final)

    def ready(self, job: Job, day: dt.date) -> bool:
        """A battery day needs its install placed at least `gap` business days earlier."""
        first = self.predecessor(job)
        if first is None:
            return True
        slot = self.placed.get(first.job_id)
        return slot is not None and gap_ok(slot[1], day, self.gap, self.origin)

    def fits(self, jid: str, slot: Slot) -> bool:
        job = self.jobs[jid]
        s = self.sites[job.site_id]
        if not self.ready(job, slot[1]):
            return False
        k = self.cluster.get(slot)
        if k is not None and k != s.cluster_id:
            return False
        extra = job.duration_min + (0 if k else self.travel[s.cluster_id])
        if self.minutes.get(slot, 0) + extra > self.avail[slot]:
            return False
        if not job.final:
            return True
        cfg = s.configuration_id
        return all(self.used[cfg][d] + 1 <= self.stock[cfg][d] for d in self.days if d >= slot[1])

    def place(self, jid: str, slot: Slot) -> None:
        job = self.jobs[jid]
        s = self.sites[job.site_id]
        if slot not in self.cluster:
            self.cluster[slot] = s.cluster_id
            self.minutes[slot] = self.travel[s.cluster_id]
        self.minutes[slot] += job.duration_min
        if job.final:
            for d in self.days:
                if d >= slot[1]:
                    self.used[s.configuration_id][d] += 1
        self.placed[jid] = slot
