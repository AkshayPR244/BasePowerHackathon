from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_live_options_evaluate_and_approve():
    request = {
        "scenario_id": "tiny_two_visit",
        "revision": 3,
        "disruption": [],
        "interactive": True,
    }
    response = client.post("/api/recovery/options", json=request)
    assert response.status_code == 200, response.text
    out = response.json()
    assert not out["stub"] and "x-rollout-stub" not in response.headers
    assert out["revision"] == 3
    manual = client.post(
        "/api/recovery/evaluate",
        json={**request, "interventions": [], "economics_overrides": {"hourly_wage": 40}},
    )
    assert manual.status_code == 200, manual.text
    option = manual.json()
    assert option["result"]["revision"] == 3
    assert any("40" in line["basis"] for line in option["economics"]["lines"])
    approved = client.post(
        "/api/recovery/approve",
        json={"scenario_id": "tiny_two_visit", "revision": 3, "option": option},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["new_current_plan"]


def test_recovery_bad_edit_is_422():
    response = client.post(
        "/api/recovery/options",
        json={
            "scenario_id": "tiny",
            "revision": 1,
            "disruption": [{"kind": "remove_crew_day", "crew_id": "missing", "date": "2018-06-04"}],
        },
    )
    assert response.status_code == 422
