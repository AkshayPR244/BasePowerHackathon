import json
from pathlib import Path

import pytest

from app.contracts.models import CounterfactualResult, PlanDiff, PlanResult

EXPECTED = Path(__file__).resolve().parents[3] / "data" / "demo" / "tiny" / "expected"
MODEL_BY_PREFIX = {"plan_": PlanResult, "compare_": PlanDiff, "counterfactual_": CounterfactualResult}


@pytest.mark.parametrize("path", sorted(EXPECTED.glob("*.json")), ids=lambda p: p.stem)
def test_expected_roundtrip(path):
    model = next(m for p, m in MODEL_BY_PREFIX.items() if path.stem.startswith(p))
    obj = model.model_validate_json(path.read_text("utf-8"))
    assert json.loads(obj.model_dump_json()) == json.loads(path.read_text("utf-8"))
