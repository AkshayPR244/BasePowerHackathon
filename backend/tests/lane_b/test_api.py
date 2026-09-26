import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.contracts.models import PlanResult
from tests.lane_b.conftest import REMOVE_A_MON, deferred, expected, slots

client = TestClient(app)


def _post(body: dict) -> PlanResult:
    r = client.post("/api/plans", json=body)
    assert r.status_code == 200, r.text
    return PlanResult.model_validate(r.json())


def _check(result: PlanResult, exp: PlanResult) -> None:
    assert result.status == exp.status
    assert result.scenario_hash == exp.scenario_hash
    assert result.objective == exp.objective
    assert slots(result) == slots(exp)
    assert deferred(result) == deferred(exp)


def test_tiny_strict():
    r = _post({"scenario_id": "tiny", "revision": 0, "mode": "strict"})
    _check(r, expected("plan_strict"))
    assert r.validation.validator  # validate_plan ran (a stub until Lane A lands)


def test_strict_infeasible():
    edit = REMOVE_A_MON.model_dump(mode="json")
    r = _post({"scenario_id": "tiny", "revision": 1, "mode": "strict", "edits": [edit]})
    _check(r, expected("plan_strict_remove_a_mon"))
    assert "recovery" in r.message


def test_tiny_recovery():
    edit = REMOVE_A_MON.model_dump(mode="json")
    r = _post({"scenario_id": "tiny", "revision": 1, "mode": "recovery", "edits": [edit]})
    exp = expected("plan_recovery_remove_a_mon")
    _check(r, exp)
    assert [(m.name, m.value) for m in r.stages] == [(m.name, m.value) for m in exp.stages]


def test_revision_is_echoed():
    assert _post({"scenario_id": "tiny", "revision": 42}).revision == 42


def test_unknown_scenario_is_404():
    r = client.post("/api/plans", json={"scenario_id": "nope", "revision": 0})
    assert r.status_code == 404
    assert r.json()["code"] == "unknown_scenario"


@pytest.mark.skip(reason="The standard fixture comes from Lane A. See lanes/A-data/NEEDS.md.")
def test_standard():
    pass
