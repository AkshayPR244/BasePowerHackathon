import hashlib
import json
from collections.abc import Sequence

from pydantic import TypeAdapter

from app.contracts.models import Edit, Scenario

_edits = TypeAdapter(list[Edit])


def scenario_hash(scenario: Scenario, edits: Sequence[Edit] = ()) -> str:
    """sha256 of the scenario inputs plus edits. Ignores scenario_hash and revision."""
    body = scenario.model_dump(mode="json", exclude={"scenario_hash", "revision"})
    payload = {"scenario": body, "edits": _edits.dump_python(list(edits), mode="json")}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()
