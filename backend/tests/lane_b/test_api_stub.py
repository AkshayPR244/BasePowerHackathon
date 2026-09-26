"""B-01: every spec endpoint exists and answers on the tiny fixture."""

from fastapi.testclient import TestClient

from app.api.main import app
from tests.lane_b.conftest import REMOVE_A_MON

client = TestClient(app)
RECOVERY = {
    "scenario_id": "tiny",
    "revision": 1,
    "mode": "recovery",
    "edits": [REMOVE_A_MON.model_dump(mode="json")],
}


def test_every_spec_endpoint_is_routed():
    paths = {(m, r.path) for r in app.routes for m in getattr(r, "methods", [])}
    for want in [
        ("GET", "/api/scenarios"),
        ("GET", "/api/scenarios/{scenario_id}"),
        ("POST", "/api/plans"),
        ("POST", "/api/plans/compare"),
        ("POST", "/api/plans/counterfactual"),
    ]:
        assert want in paths


def test_scenarios():
    ids = [s["scenario_id"] for s in client.get("/api/scenarios").json()]
    assert "tiny" in ids
    assert len(client.get("/api/scenarios/tiny").json()["sites"]) == 6
    assert client.get("/api/scenarios/nope").status_code == 404


def test_compare_and_counterfactual():
    base = client.post("/api/plans", json={"scenario_id": "tiny", "revision": 0}).json()
    rec = client.post("/api/plans", json=RECOVERY).json()
    diff = client.post("/api/plans/compare", json={"before": base, "after": rec})
    assert diff.status_code == 200
    assert diff.json()["summary"]["moved"] == 2
    body = {
        "request": RECOVERY,
        "base": rec,
        "intervention": {"kind": "force_include", "site_id": "N-02"},
    }
    cf = client.post("/api/plans/counterfactual", json=body)
    assert cf.status_code == 200
    assert cf.json()["feasible"] is False


def test_bad_request_is_422():
    r = client.post("/api/plans", json={"scenario_id": "tiny", "revision": -1})
    assert r.status_code == 422
