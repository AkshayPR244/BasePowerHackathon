from fastapi.testclient import TestClient

from app.api.main import app
from app.contracts.enums import JobState, PlanStatus
from app.contracts.models import PlanResult
from tests.lane_b.conftest import REMOVE_A_MON, deferred, expected, frozen, slots

client = TestClient(app)


def _post(body: dict) -> PlanResult:
    r = client.post("/api/plans", json=body)
    assert r.status_code == 200, r.text
    return PlanResult.model_validate(r.json())


def _check(result: PlanResult, exp: PlanResult) -> None:
    assert result.status == exp.status
    assert result.scenario_hash == exp.scenario_hash
    assert frozen(result.objective) == frozen(exp.objective)
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


LATE_SHIPMENT = {
    "kind": "delay_inventory",
    "configuration_id": "B13",
    "from_date": "2018-06-07",
    "to_date": "2018-06-11",
}
STANDARD_RECOVERY = {
    "scenario_id": "standard",
    "revision": 1,
    "mode": "recovery",
    "edits": [LATE_SHIPMENT],
}


def test_standard_every_endpoint():
    assert client.get("/api/scenarios/standard").status_code == 200
    base = _post({"scenario_id": "standard", "revision": 0})
    assert base.status == PlanStatus.optimal
    assert base.validation.checked and base.validation.valid
    assert base.objective.value_distinguishes_choices

    rec = _post(STANDARD_RECOVERY)
    assert rec.status in (PlanStatus.optimal, PlanStatus.feasible)
    assert rec.validation.checked and rec.validation.valid

    edf = _post({"scenario_id": "standard", "revision": 0, "algorithm": "baseline_edf"})
    assert edf.validation.valid

    diff = client.post(
        "/api/plans/compare",
        json={"before": base.model_dump(mode="json"), "after": rec.model_dump(mode="json")},
    )
    assert diff.status_code == 200
    assert diff.json()["summary"]["newly_late"] == rec.objective.jobs_late

    target = next(
        (a.site_id for a in rec.assignments if a.state == JobState.late),
        rec.assignments[-1].site_id,
    )
    for intervention in [
        {"kind": "force_include", "site_id": target},
        {
            "kind": "add_crew_day",
            "crew_id": "D",
            "date": "2018-06-11",
            "available_min": 480,
            "skills": ["install"],
            "allowed_clusters": ["N", "S", "W"],
        },
    ]:
        body = {
            "request": STANDARD_RECOVERY,
            "base": rec.model_dump(mode="json"),
            "intervention": intervention,
        }
        cf = client.post("/api/plans/counterfactual", json=body)
        assert cf.status_code == 200
        assert cf.json()["result"]["validation"]["valid"] is True
