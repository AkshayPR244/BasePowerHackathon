"""Frozen seams: every recovery and weather endpoint returns a schema-valid, marked payload."""

from fastapi.testclient import TestClient

from app.api.main import app
from app.contracts.models import (
    ApproveResult,
    Case,
    RecoveryOption,
    RecoveryOptionsResult,
    SeasonReplay,
    StormEvent,
)
from app.data import load_scenario
from app.recovery import service

client = TestClient(app)
STORM = [
    {"kind": "remove_crew_day", "crew_id": c, "date": "2018-06-14"} for c in ("IA", "IB", "BA")
]


def _ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def test_recovery_options_seam():
    body = {"scenario_id": "standard", "revision": 7, "disruption": STORM}
    r = client.post("/api/recovery/options", json=body)
    result = RecoveryOptionsResult.model_validate(_ok(r))
    assert result.revision == 7
    assert result.no_action.kind == "no_action"
    assert {o.kind for o in result.options} == {"rebalance", "overtime", "temporary_capacity"}
    assert sum(o.lowest_modeled_cost for o in result.options) == 1
    for o in [result.no_action, *result.options]:
        assert o.result.validation.checked and o.result.validation.valid
    if result.stub:
        assert r.headers["x-rollout-stub"] == "true"


def test_evaluate_and_approve_seam():
    body = {"scenario_id": "standard", "revision": 2, "disruption": STORM, "interventions": []}
    option = RecoveryOption.model_validate(_ok(client.post("/api/recovery/evaluate", json=body)))
    assert option.kind == "custom"
    approved = client.post(
        "/api/recovery/approve",
        json={"scenario_id": "standard", "revision": 2, "option": option.model_dump(mode="json")},
    )
    assert ApproveResult.model_validate(_ok(approved)).new_current_plan


def test_weather_seams():
    storms = [StormEvent.model_validate(x) for x in _ok(client.get("/api/storms"))]
    assert storms and all(s.source for s in storms)
    cases = [Case.model_validate(x) for x in _ok(client.get("/api/cases"))]
    assert all(c.modeled_rule for c in cases)
    SeasonReplay.model_validate(_ok(client.get("/api/season-replay")))


def test_python_seam_for_lane_w():
    result = service.recover(load_scenario("standard"), [])
    assert isinstance(result, RecoveryOptionsResult)


def test_unknown_scenario_is_404():
    r = client.post(
        "/api/recovery/options", json={"scenario_id": "nope", "revision": 0, "disruption": []}
    )
    assert r.status_code == 404


def test_new_edits_are_invalid_input_until_implemented():
    for edit in [
        {"kind": "reduce_crew_day", "crew_id": "A", "date": "2018-06-04", "available_min": 240},
        {"kind": "change_appointment", "job_id": "N-01", "available_from": "2018-06-05"},
        {"kind": "extend_crew_day", "crew_id": "A", "date": "2018-06-04", "extra_min": 60},
        {"kind": "pin_visit", "job_id": "N-01"},
        {"kind": "move_visit", "job_id": "N-01", "crew_id": "A", "date": "2018-06-05"},
    ]:
        r = client.post("/api/plans", json={"scenario_id": "tiny", "revision": 1, "edits": [edit]})
        assert r.json()["status"] == "invalid_input", edit
