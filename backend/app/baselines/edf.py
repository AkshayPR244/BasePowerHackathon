"""Earliest-deadline-first: each visit takes its earliest feasible crew-day, install first."""

from app.baselines.greedy import Board
from app.contracts.models import Scenario
from app.planning.model import Eligibility


def edf(scenario: Scenario, elig: Eligibility, board: Board, forced: set[str]) -> Board:
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
        for crew, d in sorted(elig.options[job.job_id], key=lambda o: (o[1], o[0])):
            if board.fits(job.job_id, (crew, d)):
                board.place(job.job_id, (crew, d))
                break
    return board
