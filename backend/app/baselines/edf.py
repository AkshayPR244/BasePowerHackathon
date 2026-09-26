"""Earliest-deadline-first: each job takes its earliest feasible crew-day."""

from app.baselines.greedy import Board, Slot
from app.contracts.models import Scenario
from app.planning.model import Eligibility


def edf(scenario: Scenario, elig: Eligibility, locks: dict[str, Slot], forced: set[str]) -> Board:
    board = Board(scenario)
    for sid, slot in locks.items():
        board.place(sid, slot)
    sites = board.sites
    order = sorted(
        (sid for sid in elig.any_option if sid not in board.placed),
        key=lambda sid: (sid not in forced, sites[sid].deadline, sites[sid].ready_date, sid),
    )
    for sid in order:
        for crew, d in sorted(elig.any_option[sid], key=lambda o: (o[1], o[0])):
            if board.fits(sid, (crew, d)):
                board.place(sid, (crew, d))
                break
    return board
