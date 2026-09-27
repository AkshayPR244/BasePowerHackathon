"""B-02: recorded MSW mocks exist, match index.json, and parse as contract models."""

import json
from pathlib import Path

import pytest

from app.contracts.models import (
    ApproveResult,
    Case,
    CounterfactualResult,
    PlanDiff,
    PlanResult,
    RecoveryOption,
    RecoveryOptionsResult,
    Scenario,
    ScenarioSummary,
    SeasonReplay,
    StormEvent,
)
from tests.lane_b.conftest import expected, frozen

RECORDED = Path(__file__).resolve().parents[3] / "frontend" / "src" / "mocks" / "recorded"
MODELS = {
    "plan_": PlanResult,
    "compare_": PlanDiff,
    "cf_": CounterfactualResult,
    "scenario_": Scenario,
    "recovery_options_": RecoveryOptionsResult,
    "recovery_evaluate_": RecoveryOption,
    "recovery_approve_": ApproveResult,
    "live_options_": RecoveryOptionsResult,
    "live_evaluate_": RecoveryOption,
    "live_approve_": ApproveResult,
    "season_replay": SeasonReplay,
}
LISTS = {"scenarios": ScenarioSummary, "storms": StormEvent, "cases": Case}
INDEX = json.loads((RECORDED / "index.json").read_text("utf-8"))


def test_index_covers_every_endpoint():
    routes = {
        (e["method"], e["path"].rsplit("/", 1)[0] if "scenarios/" in e["path"] else e["path"])
        for e in INDEX
    }
    assert ("GET", "/api/scenarios") in routes
    assert ("POST", "/api/plans") in routes
    assert ("POST", "/api/plans/compare") in routes
    assert ("POST", "/api/plans/counterfactual") in routes
    assert any(e["name"] == "scenario_tiny" for e in INDEX)


@pytest.mark.parametrize("entry", INDEX, ids=lambda e: e["name"])
def test_recording_parses(entry):
    text = (RECORDED / f"{entry['name']}.json").read_text("utf-8")
    if entry["name"] in LISTS:
        [LISTS[entry["name"]].model_validate(x) for x in json.loads(text)]
        return
    model = next(m for p, m in MODELS.items() if entry["name"].startswith(p))
    model.model_validate_json(text)


@pytest.mark.parametrize(
    "recorded,exp",
    [
        ("plan_tiny_strict", "plan_strict"),
        ("plan_tiny_strict_remove_a_mon", "plan_strict_remove_a_mon"),
        ("plan_tiny_recovery_remove_a_mon", "plan_recovery_remove_a_mon"),
    ],
)
def test_recorded_plans_match_expected(recorded, exp):
    r = PlanResult.model_validate_json((RECORDED / f"{recorded}.json").read_text("utf-8"))
    e = expected(exp)
    assert (r.status, frozen(r.objective), r.scenario_hash) == (
        e.status,
        frozen(e.objective),
        e.scenario_hash,
    )
