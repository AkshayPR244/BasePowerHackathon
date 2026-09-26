"""Shared greedy placement state for the baselines. Same rules as the CP-SAT model."""

import datetime as dt

from app.contracts.models import Scenario

Slot = tuple[str, dt.date]


class Board:
    def __init__(self, scenario: Scenario):
        self.sites = {s.site_id: s for s in scenario.sites}
        self.travel = {c.cluster_id: c.travel_allowance_min for c in scenario.clusters}
        self.avail = {(c.crew_id, c.date): c.available_min for c in scenario.crew_days}
        self.days = sorted({c.date for c in scenario.crew_days})
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
        self.placed: dict[str, Slot] = {}

    def fits(self, sid: str, slot: Slot) -> bool:
        s = self.sites[sid]
        k = self.cluster.get(slot)
        if k is not None and k != s.cluster_id:
            return False
        extra = s.duration_min + (0 if k else self.travel[s.cluster_id])
        if self.minutes.get(slot, 0) + extra > self.avail[slot]:
            return False
        cfg = s.configuration_id
        return all(self.used[cfg][d] + 1 <= self.stock[cfg][d] for d in self.days if d >= slot[1])

    def place(self, sid: str, slot: Slot) -> None:
        s = self.sites[sid]
        if slot not in self.cluster:
            self.cluster[slot] = s.cluster_id
            self.minutes[slot] = self.travel[s.cluster_id]
        self.minutes[slot] += s.duration_min
        for d in self.days:
            if d >= slot[1]:
                self.used[s.configuration_id][d] += 1
        self.placed[sid] = slot
