import pytest

from app.data import load_scenario
from app.recovery.service import approve, evaluate


def test_approve_revalidates_and_rejects_tampered_or_stale():
    scenario = load_scenario("tiny_two_visit").model_copy(update={"revision": 8})
    option = evaluate(scenario, [], [])
    result = approve(scenario, option)
    assert not result.stub
    assert len(result.new_current_plan) == 6
    tampered = option.model_copy(deep=True)
    tampered.result.assignments[0].date = scenario.config.planning_end
    with pytest.raises(ValueError):
        approve(scenario, tampered)
    with pytest.raises(ValueError):
        approve(scenario.model_copy(update={"revision": 9}), option)
    with pytest.raises(ValueError):
        approve(load_scenario("tiny"), option)


def test_approval_rejects_changed_source_inputs():
    scenario = load_scenario("tiny")
    option = evaluate(scenario, [], [])
    with pytest.raises(ValueError):
        approve(scenario.model_copy(update={"inventory": []}), option)


def test_approved_temporary_crew_snapshot_reloads():
    import datetime as dt

    from app.contracts.models import AddCrewDay, MoveVisit
    from app.recovery.repair import current_result

    scenario = load_scenario("tiny")
    day = dt.date(2018, 6, 4)
    option = evaluate(
        scenario,
        [],
        [
            AddCrewDay(
                crew_id="TEMP",
                date=day,
                available_min=480,
                skills=["install"],
                allowed_clusters=["S"],
            ),
            MoveVisit(job_id="S-01", crew_id="TEMP", date=day),
        ],
    )
    approved = approve(scenario, option)
    assert current_result(approved.effective_scenario).validation.valid
    assert any(c.crew_id == "TEMP" for c in approved.effective_scenario.crew_days)
