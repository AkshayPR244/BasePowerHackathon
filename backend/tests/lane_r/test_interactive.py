import datetime as dt

from app.contracts.models import RemoveCrewDay
from app.data import load_scenario
from app.recovery import service


def test_identical_request_cached_but_result_not_shared(monkeypatch):
    s = load_scenario("tiny_two_visit").model_copy(update={"revision": 913})
    edits = [RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5))]
    first = service.recover(s, edits, interactive=True)

    def fail(*a, **kw):
        raise AssertionError("Unexpected solve on cache hit")

    monkeypatch.setattr(service, "_solve", fail)
    second = service.recover(s, edits, interactive=True)
    assert first == second
    second.options.clear()
    assert service.recover(s, edits, interactive=True).options


def test_timeout_retains_only_independently_checked_incumbent(monkeypatch):
    from app.contracts.models import AddCrewDay, PlanRequest
    from app.planning.solve import plan

    scenario = load_scenario("tiny_two_visit")
    timeout = plan(
        scenario,
        PlanRequest(
            scenario_id=scenario.scenario_id, revision=0, time_limit_s=0.000001, mode="recovery"
        ),
    )
    monkeypatch.setattr(service, "plan", lambda *a, **kw: timeout)
    edits = [
        RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5)),
        AddCrewDay(
            crew_id="TEMP",
            date=dt.date(2018, 6, 5),
            available_min=480,
            skills=["battery"],
            allowed_clusters=["N", "S"],
        ),
    ]
    result = service._solve(scenario, edits, 0.02)
    assert result.status == "feasible"
    assert result.validation.valid
    assert result.objective.jobs_unscheduled == 0


def test_timeout_fallback_resolves_legacy_final_visit_rows(monkeypatch):
    from app.contracts.models import AddCrewDay, PlanRequest
    from app.planning.solve import plan

    scenario = load_scenario("tiny_two_visit").model_copy(deep=True)
    for row in scenario.current_plan:
        if row.job_id.endswith("-B"):
            row.job_id = None
    timeout = plan(
        scenario,
        PlanRequest(
            scenario_id=scenario.scenario_id, revision=0, time_limit_s=0.000001, mode="recovery"
        ),
    )
    monkeypatch.setattr(service, "plan", lambda *a, **kw: timeout)
    edits = [
        RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5)),
        AddCrewDay(
            crew_id="TEMP",
            date=dt.date(2018, 6, 5),
            available_min=480,
            skills=["battery"],
            allowed_clusters=["N", "S"],
        ),
    ]
    result = service._solve(scenario, edits, 0.02)
    assert result.status == "feasible"
    assert result.validation.valid
