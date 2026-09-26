"""Record API responses for MSW. Run from backend/ via `make mocks`.

Uses the in-process app, so it records whatever the planner returns today.
"""

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "src" / "mocks" / "recorded"
client = TestClient(app)

REMOVE_A_MON = {"kind": "remove_crew_day", "crew_id": "A", "date": "2018-06-04"}
ADD_C_MON = {
    "kind": "add_crew_day",
    "crew_id": "C",
    "date": "2018-06-04",
    "available_min": 480,
    "skills": ["install"],
    "allowed_clusters": ["N"],
}
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
PLANS = {
    "plan_tiny_strict": {"scenario_id": "tiny", "revision": 0, "mode": "strict", "edits": []},
    "plan_tiny_strict_remove_a_mon": {
        "scenario_id": "tiny",
        "revision": 1,
        "mode": "strict",
        "edits": [REMOVE_A_MON],
    },
    "plan_tiny_recovery_remove_a_mon": {
        "scenario_id": "tiny",
        "revision": 1,
        "mode": "recovery",
        "edits": [REMOVE_A_MON],
    },
    "plan_standard_strict": {"scenario_id": "standard", "revision": 0, "mode": "strict"},
    "plan_standard_edf": {"scenario_id": "standard", "revision": 0, "algorithm": "baseline_edf"},
    "plan_standard_recovery_late_shipment": STANDARD_RECOVERY,
}


def record(index: list, name: str, method: str, path: str, body: dict | None = None):
    r = client.request(method, path, json=body)
    if r.status_code != 200:
        print(f"skip {name}: {r.status_code} {r.text[:120]}")
        return None
    (OUT / f"{name}.json").write_text(json.dumps(r.json(), indent=2) + "\n", encoding="utf-8")
    index.append({"name": name, "method": method, "path": path, "request": body})
    print(f"recorded {name}")
    return r.json()


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    index: list = []
    scenarios = record(index, "scenarios", "GET", "/api/scenarios") or []
    for s in scenarios:
        record(index, f"scenario_{s['scenario_id']}", "GET", f"/api/scenarios/{s['scenario_id']}")
    plans = {name: record(index, name, "POST", "/api/plans", body) for name, body in PLANS.items()}

    base, rec = plans["plan_tiny_strict"], plans["plan_tiny_recovery_remove_a_mon"]
    if base and rec:
        record(
            index,
            "compare_tiny_strict_vs_recovery",
            "POST",
            "/api/plans/compare",
            {"before": base, "after": rec},
        )
        for name, edit in [
            ("cf_tiny_force_n02", {"kind": "force_include", "site_id": "N-02"}),
            ("cf_tiny_add_c_mon", ADD_C_MON),
        ]:
            body = {
                "request": PLANS["plan_tiny_recovery_remove_a_mon"],
                "base": rec,
                "intervention": edit,
            }
            record(index, name, "POST", "/api/plans/counterfactual", body)

    base, rec = plans["plan_standard_strict"], plans["plan_standard_recovery_late_shipment"]
    if base and rec:
        record(
            index,
            "compare_standard_strict_vs_late_shipment",
            "POST",
            "/api/plans/compare",
            {"before": base, "after": rec},
        )
        late = [a["site_id"] for a in rec["assignments"] if a["state"] == "late"]
        if late:
            body = {
                "request": STANDARD_RECOVERY,
                "base": rec,
                "intervention": {"kind": "force_include", "site_id": late[0]},
            }
            record(index, "cf_standard_force_first_late", "POST", "/api/plans/counterfactual", body)

    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
