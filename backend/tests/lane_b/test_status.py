"""B-08: every PlanStatus is distinct and reachable. Solves run off the event loop."""

import asyncio
import threading

from ortools.sat.python import cp_model

from app.api import main
from app.contracts.enums import Mode, PlanStatus, StageStatus
from app.contracts.models import PlanRequest, RemoveCrewDay
from app.planning import lexicographic
from app.planning.solve import plan
from tests.lane_b.conftest import REMOVE_A_MON, make_scenario


def test_optimal(tiny):
    r = plan(tiny, PlanRequest(scenario_id="tiny", revision=0))
    assert r.status == PlanStatus.optimal
    assert all(m.status == StageStatus.optimal for m in r.stages)


def test_infeasible(tiny):
    r = plan(tiny, PlanRequest(scenario_id="tiny", revision=1, edits=[REMOVE_A_MON]))
    assert r.status == PlanStatus.infeasible
    assert r.objective is None and r.assignments == []


def test_invalid_input(tiny):
    bad = RemoveCrewDay(crew_id="Z", date="2018-06-04")
    r = plan(tiny, PlanRequest(scenario_id="tiny", revision=1, edits=[bad]))
    assert r.status == PlanStatus.invalid_input
    assert r.input_issues and r.assignments == []


def test_timeout_no_incumbent(monkeypatch, tiny):
    class NoAnswer(cp_model.CpSolver):
        def solve(self, model, *a, **k):
            return cp_model.UNKNOWN

    monkeypatch.setattr(lexicographic.cp_model, "CpSolver", NoAnswer)
    r = plan(tiny, PlanRequest(scenario_id="tiny", revision=0, mode=Mode.recovery))
    assert r.status == PlanStatus.timeout_no_incumbent
    assert r.stages[0].status == StageStatus.timeout_no_incumbent
    assert r.assignments == []
    assert "does not prove" in r.message


def test_feasible_when_a_stage_is_not_proven(monkeypatch, tiny):
    class NotProven(cp_model.CpSolver):
        def solve(self, model, *a, **k):
            code = super().solve(model, *a, **k)
            return cp_model.FEASIBLE if code == cp_model.OPTIMAL else code

    monkeypatch.setattr(lexicographic.cp_model, "CpSolver", NotProven)
    r = plan(tiny, PlanRequest(scenario_id="tiny", revision=0))
    assert r.status == PlanStatus.feasible
    assert r.assignments
    assert "time limit" in r.message


def test_budget_exhausted_before_first_stage_is_timeout(tiny):
    s = make_scenario(n_jobs=60, n_days=10, seed=3)
    r = plan(s, PlanRequest(scenario_id=s.scenario_id, revision=0, time_limit_s=0.001))
    assert r.status == PlanStatus.timeout_no_incumbent


def test_statuses_are_distinct():
    assert len({s.value for s in PlanStatus}) == 5


def test_solves_run_off_the_event_loop(monkeypatch, tiny):
    loop_thread = []

    def spy(scenario, req):
        loop_thread.append(threading.current_thread() is threading.main_thread())
        return plan(scenario, req)

    monkeypatch.setattr(main, "plan", spy)
    asyncio.run(main.create_plan(PlanRequest(scenario_id="tiny", revision=0)))
    assert loop_thread == [False]


def test_constant_first_stages_still_prove_infeasibility(tiny):
    """Empty current plan and equal values make the first strict stages constants."""
    from app.contracts.models import DelayInventory

    s = tiny.model_copy(update={"current_plan": []})
    short = DelayInventory(configuration_id="B13", from_date="2018-06-04", to_date="2018-06-06")
    r = plan(s, PlanRequest(scenario_id="tiny", revision=1, edits=[short]))
    assert r.status == PlanStatus.infeasible
