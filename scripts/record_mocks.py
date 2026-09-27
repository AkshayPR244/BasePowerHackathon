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
BATTERY_CREW_OUT = {"kind": "remove_crew_day", "crew_id": "BA", "date": "2018-06-07"}
STANDARD_RECOVERY = {
    "scenario_id": "standard",
    "revision": 1,
    "mode": "recovery",
    "edits": [BATTERY_CREW_OUT],
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
    "plan_standard_recovery_install_crew_out": {
        "scenario_id": "standard",
        "revision": 1,
        "mode": "recovery",
        "edits": [{"kind": "remove_crew_day", "crew_id": "IA", "date": "2018-06-07"}],
    },
    "plan_standard_recovery_battery_crew_out": STANDARD_RECOVERY,
    "plan_tiny_two_visit_strict": {"scenario_id": "tiny_two_visit", "revision": 0},
}


def record(index: list, name: str, method: str, path: str, body: dict | None = None):
    r = client.request(method, path, json=body)
    if r.status_code != 200:
        print(f"skip {name}: {r.status_code} {r.text[:120]}")
        return None
    text = json.dumps(r.json(), indent=2) + "\n"
    (OUT / f"{name}.json").write_text(text, encoding="utf-8", newline="\n")
    index.append({"name": name, "method": method, "path": path, "request": body})
    print(f"recorded {name}")
    return r.json()


def record_canvas_defaults(index: list, storm: list, options: dict):
    """Record approve for every option and the canvas test buttons at their default inputs.

    Mirrors the defaults in frontend/src/components/EvaluationControls.tsx.
    """
    every = [options["no_action"], *options["options"]]
    for o in every:
        suffix = "" if o is options["options"][0] else f"_{o['kind']}"
        record(
            index,
            f"recovery_approve_standard_storm{suffix}",
            "POST",
            "/api/recovery/approve",
            {"scenario_id": "standard", "revision": 1, "option": o},
        )
    scenario = client.get("/api/scenarios/standard").json()
    first_open = min(d["date"] for d in storm)
    crew, date = "IA", "2018-06-15"
    skill = {v["job_id"]: v["required_skill"] for s in scenario["sites"] for v in s["visits"]}
    crew_skills = {k for c in scenario["crew_days"] if c["crew_id"] == crew for k in c["skills"]}
    base = {"scenario_id": "standard", "revision": 1, "interactive": True}
    bodies = {
        "knockout": {**base, "disruption": [*storm, _remove(crew, date)], "interventions": []},
        "overtime": {
            **base,
            "disruption": storm,
            "interventions": [
                {"kind": "extend_crew_day", "crew_id": crew, "date": date, "extra_min": 120}
            ],
        },
    }
    for o in every:
        visits = sorted(
            a["job_id"]
            for a in o["result"]["assignments"]
            if a["date"] >= first_open and a["job_id"]
        )
        movable = [v for v in visits if skill.get(v) in crew_skills]
        if visits:
            bodies[f"pin_{visits[0]}"] = {
                **base,
                "disruption": storm,
                "interventions": [{"kind": "pin_visit", "job_id": visits[0]}],
            }
        if movable:
            bodies[f"move_{movable[0]}"] = {
                **base,
                "disruption": storm,
                "interventions": [
                    {"kind": "move_visit", "job_id": movable[0], "crew_id": crew, "date": date}
                ],
            }
    for name, body in bodies.items():
        record(index, f"recovery_evaluate_storm_{name}", "POST", "/api/recovery/evaluate", body)


def record_live_canvas(index: list):
    """Record the live canvas baseline, its approvals, and one crew-day knockout.

    Mirrors the requests in frontend/src/views/LiveRecoveryCanvas.tsx.
    """
    plan = client.get("/api/scenarios/standard").json()["current_plan"]
    base = {"scenario_id": "standard", "current_plan": plan, "interactive": True}
    options = record(
        index,
        "live_options_standard_baseline",
        "POST",
        "/api/recovery/options",
        {**base, "revision": 0, "disruption": []},
    )
    for o in [options["no_action"], *options["options"]] if options else []:
        record(
            index,
            f"live_approve_standard_{o['kind']}",
            "POST",
            "/api/recovery/approve",
            {"scenario_id": "standard", "revision": 0, "option": o},
        )
    knockout = {**base, "revision": 1, "disruption": [_remove("BA", "2018-06-14")]}
    record(index, "live_options_standard_knockout_ba", "POST", "/api/recovery/options", knockout)
    record(
        index,
        "live_evaluate_standard_knockout_ba",
        "POST",
        "/api/recovery/evaluate",
        {**knockout, "interventions": []},
    )


def _remove(crew: str, date: str) -> dict:
    return {"kind": "remove_crew_day", "crew_id": crew, "date": date}


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

    base, rec = plans["plan_standard_strict"], plans["plan_standard_recovery_battery_crew_out"]
    if base and rec:
        record(
            index,
            "compare_standard_strict_vs_battery_crew_out",
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

    storm = [
        {"kind": "remove_crew_day", "crew_id": c, "date": "2018-06-14"} for c in ("IA", "IB", "BA")
    ]
    options = record(
        index,
        "recovery_options_standard_storm",
        "POST",
        "/api/recovery/options",
        {"scenario_id": "standard", "revision": 1, "disruption": storm, "interactive": False},
    )
    record(
        index,
        "recovery_evaluate_standard_storm",
        "POST",
        "/api/recovery/evaluate",
        {"scenario_id": "standard", "revision": 2, "disruption": storm, "interventions": []},
    )
    if options:
        record_canvas_defaults(index, storm, options)
    record_live_canvas(index)
    record(index, "storms", "GET", "/api/storms")
    record(index, "cases", "GET", "/api/cases")
    record(index, "season_replay", "GET", "/api/season-replay")

    (OUT / "index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
