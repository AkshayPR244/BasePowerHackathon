"""Nearest-cluster-first: each crew-day stays in one cluster and fills it by deadline.

A crew keeps its previous cluster while work remains there. Otherwise it takes the cluster
with the most pending jobs it can serve that day.
"""

from app.baselines.greedy import Board, Slot
from app.contracts.models import Scenario
from app.planning.model import Eligibility


def nearest_cluster(
    scenario: Scenario, elig: Eligibility, locks: dict[str, Slot], forced: set[str]
) -> Board:
    board = Board(scenario)
    for sid, slot in locks.items():
        board.place(sid, slot)
    sites = board.sites
    last: dict[str, str] = {}
    for c in sorted(scenario.crew_days, key=lambda c: (c.date, c.crew_id)):
        slot = (c.crew_id, c.date)
        pending = [
            sid for sid, opts in elig.any_option.items() if sid not in board.placed and slot in opts
        ]
        if pending:
            counts: dict[str, int] = {}
            for sid in pending:
                k = sites[sid].cluster_id
                counts[k] = counts.get(k, 0) + 1
            k = board.cluster.get(slot)
            if k is None:
                prev = last.get(c.crew_id)
                k = prev if prev in counts else max(sorted(counts), key=lambda kk: counts[kk])
            chosen = sorted(
                (s for s in pending if sites[s].cluster_id == k),
                key=lambda s: (s not in forced, sites[s].deadline, s),
            )
            for sid in chosen:
                if board.fits(sid, slot):
                    board.place(sid, slot)
        if slot in board.cluster:
            last[c.crew_id] = board.cluster[slot]
    return board
