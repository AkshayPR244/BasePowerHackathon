import json
from pathlib import Path

import pytest

from app.contracts.hashing import scenario_hash
from app.contracts.models import CrewDay, PlanResult
from app.data import load_scenario

EXPECTED = Path(__file__).resolve().parents[3] / "data/demo/tiny/expected"


def expected_plans():
    for path in sorted(EXPECTED.glob("*.json")):
        if path.name.startswith("compare"):
            continue
        payload = json.loads(path.read_text())
        yield path.stem, PlanResult.model_validate(payload.get("result", payload))


def edited_scenario(plan):
    s = load_scenario("tiny")
    if plan.edits:
        s.scenario_hash = scenario_hash(s, plan.edits)
    for e in plan.edits:
        if e.kind == "remove_crew_day":
            s.crew_days = [c for c in s.crew_days if (c.crew_id, c.date) != (e.crew_id, e.date)]
        elif e.kind == "add_crew_day":
            s.crew_days.append(CrewDay(**e.model_dump(exclude={"kind"})))
    return s


@pytest.fixture
def scenario():
    return load_scenario("tiny")


@pytest.fixture
def plan():
    return PlanResult.model_validate_json((EXPECTED / "plan_strict.json").read_text())
