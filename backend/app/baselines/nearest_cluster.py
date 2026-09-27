"""Nearest-cluster-first: each crew-day stays in one cluster and fills it by deadline.

A crew keeps its previous cluster while work remains there. Otherwise it takes the cluster
with the most pending visits it can serve that day.
"""

from app.baselines.greedy import Board
from app.contracts.models import Scenario
from app.planning.model import Eligibility


def nearest_cluster(scenario: Scenario, elig: Eligibility, board: Board, forced: set[str]) -> Board:
    sites, jobs = board.sites, board.jobs
    last: dict[str, str] = {}
    for c in sorted(scenario.crew_days, key=lambda c: (c.date, c.crew_id)):
        slot = (c.crew_id, c.date)
        pending = [
            jid
            for jid, opts in elig.options.items()
            if jid not in board.placed and slot in opts and board.ready(jobs[jid], c.date)
        ]
        if pending:
            counts: dict[str, int] = {}
            for jid in pending:
                k = sites[jobs[jid].site_id].cluster_id
                counts[k] = counts.get(k, 0) + 1
            k = board.cluster.get(slot)
            if k is None:
                prev = last.get(c.crew_id)
                k = prev if prev in counts else max(sorted(counts), key=lambda kk: counts[kk])
            chosen = sorted(
                (j for j in pending if sites[jobs[j].site_id].cluster_id == k),
                key=lambda j: (jobs[j].site_id not in forced, sites[jobs[j].site_id].deadline, j),
            )
            for jid in chosen:
                if board.fits(jid, slot):
                    board.place(jid, slot)
        if slot in board.cluster:
            last[c.crew_id] = board.cluster[slot]
    return board
