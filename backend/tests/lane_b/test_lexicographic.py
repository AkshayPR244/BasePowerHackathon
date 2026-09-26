"""B-09: recovery runs five stages in order under one budget and keeps earlier optima."""

from app.contracts.enums import Mode, StageStatus
from app.contracts.models import PlanRequest
from app.planning.solve import RECOVERY_STAGES, plan
from tests.lane_b.conftest import REMOVE_A_MON, make_scenario


def test_recovery_reports_five_stages(tiny):
    r = plan(
        tiny, PlanRequest(scenario_id="tiny", revision=1, mode=Mode.recovery, edits=[REMOVE_A_MON])
    )
    assert [m.name for m in r.stages] == [s.name for s in RECOVERY_STAGES if s.name != "canonical"]
    for m in r.stages:
        assert m.status == StageStatus.optimal
        assert m.value is not None and m.bound is not None and m.gap == 0.0
        assert m.elapsed_ms >= 0


def test_later_stages_keep_earlier_optima():
    s = make_scenario(n_jobs=30, seed=11)
    r = plan(s, PlanRequest(scenario_id=s.scenario_id, revision=0, mode=Mode.recovery))
    stages = {m.name: m.value for m in r.stages}
    o = r.objective
    late_or_unscheduled = o.jobs_late + o.jobs_unscheduled - o.jobs_blocked
    assert stages["jobs_late_or_unscheduled"] == late_or_unscheduled
    penalty = s.config.unscheduled_penalty_days * (o.jobs_unscheduled - o.jobs_blocked)
    assert stages["total_delay"] == o.total_delay_days + penalty
    assert stages["travel"] == o.travel_allowance_min


def test_one_total_budget_skips_remaining_stages(monkeypatch, tiny):
    import app.planning.lexicographic as lex

    clock = iter([0.0, 0.0, 0.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr(lex.time, "monotonic", lambda: next(clock, 100.0))
    r = plan(
        tiny, PlanRequest(scenario_id="tiny", revision=1, mode=Mode.recovery, edits=[REMOVE_A_MON])
    )
    statuses = [m.status for m in r.stages]
    assert statuses[0] == StageStatus.optimal
    assert StageStatus.skipped in statuses
    assert r.status.value == "feasible"


def test_parallel_solves_are_reproducible():
    """8 workers are non-deterministic alone. The canonical tie-break stage fixes the plan."""
    from app.api.scenarios import load_scenario
    from app.contracts.models import DelayInventory

    s = load_scenario("standard")
    assert s.config.num_workers > 1
    late = DelayInventory(configuration_id="B13", from_date="2018-06-07", to_date="2018-06-11")
    req = PlanRequest(scenario_id="standard", revision=1, mode=Mode.recovery, edits=[late])
    runs = {
        tuple((a.site_id, a.crew_id, a.date) for a in plan(s, req).assignments) for _ in range(3)
    }
    assert len(runs) == 1


def test_changed_installs_outrank_value_on_standard():
    """Locks the objective order: no disruption means no customer is moved for value."""
    from app.api.scenarios import load_scenario

    s = load_scenario("standard")
    r = plan(s, PlanRequest(scenario_id="standard", revision=0))
    assert [m.name for m in r.stages][:2] == ["changed_installs", "operating_value"]
    assert r.objective.changed_installs == 0
