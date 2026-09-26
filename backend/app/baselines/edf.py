"""Earliest-deadline-first: each visit takes its earliest feasible crew-day, install first."""

from app.baselines.greedy import Board, Slot
from app.contracts.models import Scenario
from app.planning.model import Eligibility


def edf(scenario: Scenario, elig: Eligibility, locks: dict[str, Slot], forced: set[str]) -> Board:
    board = Board(scenario, elig)
    for jid, slot in sorted(locks.items(), key=lambda kv: board.jobs[kv[0]].final):
        board.place(jid, slot)
    sites = board.sites
    order = sorted(
        (j for j in elig.jobs.values() if j.job_id not in board.placed),
        key=lambda j: (
            j.site_id not in forced,
            sites[j.site_id].deadline,
            sites[j.site_id].ready_date,
            j.site_id,
            j.final,
        ),
    )
    for job in order:
        for crew, d in sorted(elig.any_option[job.job_id], key=lambda o: (o[1], o[0])):
            if board.fits(job.job_id, (crew, d)):
                board.place(job.job_id, (crew, d))
                break
    return board
