import json
from pathlib import Path

import pytest

from app.contracts.models import CounterfactualResult, PlanDiff, PlanResult

EXPECTED = Path(__file__).resolve().parents[3] / "data" / "demo" / "tiny" / "expected"
MODEL_BY_PREFIX = {
    "plan_": PlanResult,
    "compare_": PlanDiff,
    "counterfactual_": CounterfactualResult,
}


@pytest.mark.parametrize("path", sorted(EXPECTED.glob("*.json")), ids=lambda p: p.stem)
def test_expected_roundtrip(path):
    model = next(m for p, m in MODEL_BY_PREFIX.items() if path.stem.startswith(p))
    obj = model.model_validate_json(path.read_text("utf-8"))
    assert json.loads(obj.model_dump_json()) == json.loads(path.read_text("utf-8"))


def test_scenario_roundtrip_and_expected_hashes():
    from app.contracts.hashing import scenario_hash
    from app.contracts.models import Scenario
    from app.data import load_scenario

    scenario = load_scenario("tiny")
    assert Scenario.model_validate_json(scenario.model_dump_json()) == scenario
    for path in EXPECTED.glob("*.json"):
        payload = json.loads(path.read_text())
        if path.stem.startswith("counterfactual_"):
            payload = payload["result"]
        if "edits" in payload:
            plan = PlanResult.model_validate(payload)
            assert plan.scenario_hash == scenario_hash(scenario, plan.edits), path.name
