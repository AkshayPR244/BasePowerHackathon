"""Every error response is an ApiError, and the OpenAPI spec says so."""

import pytest
from fastapi.testclient import TestClient

from app.api import warm
from app.api.main import app
from app.contracts.models import ApiError
from tests.lane_b.conftest import expected

client = TestClient(app)


def _is_api_error(r, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    err = ApiError.model_validate(r.json())
    assert err.code == code and err.message


def test_request_validation_is_api_error():
    r = client.post("/api/plans", json={"scenario_id": "tiny", "revision": -1})
    _is_api_error(r, 422, "invalid_request")
    assert "revision" in r.json()["message"]


def test_bad_edit_kind_is_api_error():
    body = {"scenario_id": "tiny", "revision": 0, "edits": [{"kind": "nope"}]}
    _is_api_error(client.post("/api/plans", json=body), 422, "invalid_request")


def test_unknown_scenario_is_api_error():
    _is_api_error(client.get("/api/scenarios/nope"), 404, "unknown_scenario")


def test_unknown_path_is_api_error():
    _is_api_error(client.get("/api/nope"), 404, "not_found")


def test_wrong_method_is_api_error():
    _is_api_error(client.get("/api/plans"), 405, "method_not_allowed")


def test_compare_mismatch_is_api_error():
    a = expected("plan_strict").model_dump(mode="json")
    b = {**a, "scenario_id": "other"}
    _is_api_error(
        client.post("/api/plans/compare", json={"before": a, "after": b}), 400, "scenario_mismatch"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/plans",
        "/api/plans/compare",
        "/api/plans/counterfactual",
        "/api/scenarios/{scenario_id}",
    ],
)
def test_openapi_documents_api_error_for_422(path):
    spec = app.openapi()["paths"][path]
    op = spec.get("post") or spec.get("get")
    ref = op["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ApiError")
    assert "HTTPValidationError" not in str(app.openapi()["components"]["schemas"])


def test_warm_cache_reaches_ready():
    warm.start().join(timeout=300)
    assert warm.status()["values"] == "ready"
