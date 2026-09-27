"""API input bounds, error mapping, and no raw exception text in responses."""

import logging
import shutil

import pytest
from fastapi.testclient import TestClient

from app.api import main, scenarios, warm
from app.contracts.models import ApiError
from app.data import load as loader
from app.planning.solve import InvalidPlanError
from app.recovery import service
from tests.lane_b.conftest import expected

client = TestClient(main.app, raise_server_exceptions=False)
SECRET = "C:/secret/internal/path.csv"
REMOVE = {"kind": "remove_crew_day", "crew_id": "A", "date": "2018-06-04"}


def _error(r, status: int, code: str) -> ApiError:
    assert r.status_code == status, r.text
    err = ApiError.model_validate(r.json())
    assert err.code == code
    assert SECRET not in r.text
    return err


def test_counterfactual_rejects_base_from_another_scenario():
    base = expected("plan_strict").model_dump(mode="json")
    body = {
        "request": {"scenario_id": "tiny", "revision": 0},
        "base": {**base, "scenario_id": "tiny_two_visit"},
        "intervention": {"kind": "force_include", "site_id": "N-02"},
    }
    _error(client.post("/api/plans/counterfactual", json=body), 422, "scenario_mismatch")


def test_pydantic_error_in_recovery_is_500_with_request_id(monkeypatch):
    def broken(*args):
        ApiError.model_validate({"code": SECRET})

    monkeypatch.setattr(service, "recover", broken)
    r = client.post(
        "/api/recovery/options", json={"scenario_id": "tiny", "revision": 0, "disruption": []}
    )
    err = _error(r, 500, "internal_error")
    assert r.headers["x-request-id"] in err.message
    assert "validation error" not in r.text.lower()


def test_value_error_outside_recovery_is_500(monkeypatch):
    def broken(*args):
        raise ValueError(SECRET)

    monkeypatch.setattr(service, "evaluate", broken)
    body = {"scenario_id": "tiny", "revision": 0, "disruption": [], "interventions": []}
    _error(client.post("/api/recovery/evaluate", json=body), 500, "internal_error")


def test_recovery_input_error_stays_422():
    body = {"scenario_id": "tiny", "revision": 0, "disruption": [], "economics_overrides": {"x": 1}}
    err = _error(client.post("/api/recovery/options", json=body), 422, "invalid_recovery")
    assert "Unknown economic assumptions" in err.message


def test_stored_current_plan_failure_does_not_blame_the_client(monkeypatch):
    def infeasible(scenario):
        raise InvalidPlanError("CAPACITY on crew A")

    monkeypatch.setattr(service, "current_result", infeasible)
    body = {"scenario_id": "tiny", "revision": 0, "disruption": []}
    err = _error(client.post("/api/recovery/options", json=body), 422, "invalid_input")
    assert "stored in scenario tiny" in err.message
    assert "supplied" not in err.message and "CAPACITY" not in err.message

    plan = [p.model_dump(mode="json") for p in scenarios.load_scenario("tiny").current_plan]
    r = client.post("/api/recovery/options", json={**body, "current_plan": plan})
    err = _error(r, 422, "invalid_recovery")
    assert "supplied current plan" in err.message and "CAPACITY on crew A" in err.message


def test_scenario_load_error_hides_paths(monkeypatch, caplog):
    def broken(scenario_id):
        raise OSError(SECRET)

    monkeypatch.setattr(main, "load_scenario", broken)
    with caplog.at_level(logging.ERROR, logger="slackline.api"):
        r = client.get("/api/scenarios/tiny")
    err = _error(r, 422, "invalid_input")
    assert r.headers["x-request-id"] in err.message
    assert any(SECRET in str(rec.exc_info) for rec in caplog.records)


def test_scenario_list_skips_a_broken_scenario(monkeypatch):
    real = main.load_scenario

    def some_broken(scenario_id):
        if scenario_id == "tiny":
            raise OSError(SECRET)
        return real(scenario_id)

    monkeypatch.setattr(main, "load_scenario", some_broken)
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    ids = [s["scenario_id"] for s in r.json()]
    assert "tiny" not in ids and "standard" in ids
    assert r.headers["x-slackline-broken-scenarios"] == "tiny"
    assert SECRET not in r.text


def test_health_hides_warm_up_error_text(monkeypatch):
    monkeypatch.setattr(warm, "_state", {"values": "not_started"})

    def broken(scenario):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(warm.valuation, "value_table", broken)
    warm._run()
    body = client.get("/api/health").json()
    assert body["values"] == "failed"
    assert SECRET not in str(body)
    assert "standard" in body["values_error"]


def test_health_leaves_warming_when_listing_fails(monkeypatch):
    monkeypatch.setattr(warm, "_state", {"values": "not_started"})

    def broken():
        raise OSError(SECRET)

    monkeypatch.setattr(warm, "scenario_ids", broken)
    warm._run()
    state = warm.status()
    assert state["values"] == "failed"
    assert SECRET not in state["values_error"]


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/plans", {"scenario_id": "tiny", "revision": 0, "edits": [REMOVE] * 201}),
        (
            "/api/recovery/options",
            {"scenario_id": "tiny", "revision": 0, "disruption": [REMOVE] * 201},
        ),
        (
            "/api/recovery/evaluate",
            {
                "scenario_id": "tiny",
                "revision": 0,
                "disruption": [],
                "interventions": [REMOVE] * 201,
            },
        ),
        (
            "/api/plans/counterfactual",
            {
                "request": {"scenario_id": "tiny", "revision": 0, "edits": [REMOVE] * 201},
                "base": expected("plan_strict").model_dump(mode="json"),
                "intervention": REMOVE,
            },
        ),
        ("/api/plans", {"scenario_id": "tiny", "revision": 2**53}),
        ("/api/recovery/options", {"scenario_id": "tiny", "revision": 2**53, "disruption": []}),
    ],
)
def test_oversized_requests_are_422(path, body):
    err = _error(client.post(path, json=body), 422, "invalid_request")
    assert "limit is 200" in err.message or "revision must be at most" in err.message


def test_largest_safe_revision_is_accepted():
    r = client.post("/api/plans", json={"scenario_id": "tiny", "revision": 2**53 - 1})
    assert r.status_code == 200, r.text
    assert r.json()["revision"] == 2**53 - 1


def test_cors_allows_preview_and_exposes_headers():
    pre = client.options(
        "/api/plans",
        headers={"Origin": "http://localhost:4173", "Access-Control-Request-Method": "POST"},
    )
    assert pre.headers["access-control-allow-origin"] == "http://localhost:4173"
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    exposed = r.headers["access-control-expose-headers"].lower()
    assert "x-slackline-stub" in exposed and "x-request-id" in exposed


def test_scenario_cache_returns_private_copies_and_sees_file_changes(tmp_path, monkeypatch):
    shutil.copytree(loader.DATA_ROOT / "tiny", tmp_path / "tiny")
    monkeypatch.setattr(loader, "DATA_ROOT", tmp_path)
    first = scenarios.load_scenario("tiny")
    first.sites.clear()
    assert scenarios.load_scenario("tiny").sites
    yaml_path = tmp_path / "tiny" / "scenario.yaml"
    yaml_path.write_text(yaml_path.read_text().replace("Tiny hand-built check", "Renamed"))
    assert scenarios.load_scenario("tiny").config.name == "Renamed"
