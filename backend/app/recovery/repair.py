"""Deterministic no-action repair: reserve bookings before placing displaced visits."""

from app.baselines.greedy import Board
from app.contracts.enums import Algorithm, Mode, PlanStatus
from app.contracts.models import PlanRequest, Scenario
from app.contracts.visits import gap_ok, job_of_row, jobs_of
from app.planning.edits import apply_edits, restrict_appointments
from app.planning.model import eligibility
from app.planning.result import build_result
from app.planning.solve import _validated, plan, site_values


def current_result(scenario: Scenario):
    """Represent the supplied current plan, never silently optimize it."""
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}
    placed = {job_of_row(p, by_site): (p.crew_id, p.date) for p in scenario.current_plan}
    if None in placed or len(placed) != len(scenario.current_plan):
        raise ValueError("Current plan contains an unknown or duplicate visit.")
    return result_for(scenario, placed, [], "Current plan before the disruption.")


def result_for(scenario, placed, edits, message, status=PlanStatus.feasible):
    values, _ = site_values(scenario)
    result = build_result(
        scenario=scenario,
        elig=eligibility(scenario, Mode.recovery, set()),
        placed=placed,
        status=status,
        stages=[],
        mode=Mode.recovery,
        algorithm=Algorithm.cpsat,
        policy=scenario.config.objective_policy,
        revision=scenario.revision,
        edits=list(edits),
        values=values,
        message=message,
    )
    return _validated(scenario, result)


def repair(base: Scenario, disruption):
    """No new bookings, crew transfers, or displacement of retained bookings.

    Ties after capacity loss use date, install-before-battery, then visit ID.
    A displaced visit can wait beyond its original date, never move earlier.
    Hard locks remain hard; an impossible locked booking yields no feasible plan.
    """
    current_result(base)  # Reject malformed or infeasible original bookings before repair.
    edited = apply_edits(base, disruption)
    if edited.issues:
        return plan(
            base,
            PlanRequest(
                scenario_id=base.scenario_id,
                revision=base.revision,
                edits=list(disruption),
                mode=Mode.recovery,
            ),
        )
    scenario = edited.scenario
    elig = restrict_appointments(eligibility(scenario, Mode.recovery, edited.forced), disruption)
    board = Board(scenario, elig)
    by_site = {s.site_id: jobs_of(s) for s in scenario.sites}
    rows = [(job_of_row(p, by_site), p) for p in scenario.current_plan]
    rows.sort(
        key=lambda pair: (
            pair[1].date,
            elig.jobs[pair[0]].final if pair[0] in elig.jobs else False,
            pair[0] or "",
        )
    )

    def impossible():
        return result_for(
            scenario,
            None,
            disruption,
            "No-action repair cannot preserve the locked commitments.",
            PlanStatus.infeasible,
        )

    # Reserve hard locks before any unlocked booking can consume their resources.
    for jid, row in rows:
        if not row.locked:
            continue
        slot = (row.crew_id, row.date)
        if jid not in elig.jobs or slot not in elig.any_option[jid]:
            return impossible()
        job = elig.jobs[jid]
        cluster = board.sites[job.site_id].cluster_id
        if slot in board.cluster and board.cluster[slot] != cluster:
            return impossible()
        board.place(jid, slot)
    if any(n > board.avail[slot] for slot, n in board.minutes.items()) or any(
        board.used[cfg][d] > stock for cfg in board.stock for d, stock in board.stock[cfg].items()
    ):
        return impossible()

    def fits(jid, slot, reserve=False):
        if not board.fits(jid, slot, check_ready=not reserve):
            return False
        job = elig.jobs[jid]
        if not job.final:
            successor = next(
                (j for j in elig.jobs.values() if j.site_id == job.site_id and j.final), None
            )
            if successor and successor.job_id in board.placed:
                return gap_ok(slot[1], board.placed[successor.job_id][1], board.gap, board.origin)
        return True

    displaced = []
    for jid, row in rows:
        if row.locked:
            continue
        slot = (row.crew_id, row.date)
        if jid in elig.jobs and slot in elig.any_option[jid] and fits(jid, slot, reserve=True):
            board.place(jid, slot)
        else:
            displaced.append((jid, row))
    # Install visits first, so dependent battery days see their repaired predecessors.
    displaced.sort(
        key=lambda pair: (
            elig.jobs[pair[0]].final if pair[0] in elig.jobs else False,
            pair[1].date,
            pair[0] or "",
        )
    )
    for jid, row in displaced:
        if jid not in elig.jobs:
            continue
        slots = sorted(
            (s for s in elig.any_option[jid] if s[0] == row.crew_id and s[1] >= row.date),
            key=lambda s: s[1],
        )
        for slot in slots:
            if fits(jid, slot):
                board.place(jid, slot)
                break
    orphaned = {
        jid for jid, slot in board.placed.items() if not board.ready(board.jobs[jid], slot[1])
    }
    if any(row.locked and jid in orphaned for jid, row in rows):
        return impossible()
    if orphaned:
        kept = {jid: slot for jid, slot in board.placed.items() if jid not in orphaned}
        board = Board(scenario, elig)
        for jid, slot in kept.items():
            board.place(jid, slot)
        # Once an impossible downstream reservation is released, retry the displaced
        # predecessor and then its battery day, still keeping all unaffected bookings.
        pending = [(jid, row) for jid, row in rows if jid not in board.placed and jid in elig.jobs]
        pending.sort(key=lambda pair: (elig.jobs[pair[0]].final, pair[1].date, pair[0]))
        for jid, row in pending:
            for slot in sorted(elig.any_option[jid], key=lambda s: s[1]):
                if slot[0] == row.crew_id and slot[1] >= row.date and fits(jid, slot):
                    board.place(jid, slot)
                    break
    return result_for(
        scenario,
        board.placed,
        disruption,
        "No action: displaced visits wait for their original crew's next open "
        "slot. Retained bookings do not move; visits without a slot stay unscheduled.",
    )
