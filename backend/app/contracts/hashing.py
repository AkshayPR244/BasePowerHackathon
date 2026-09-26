import hashlib
import json
from collections.abc import Sequence

from pydantic import TypeAdapter

from app.contracts.models import Edit, Scenario

_edits = TypeAdapter(list[Edit])


# Fields added after contract 1.0.0 enter the hash only when set, so old hashes stay valid.
_ADDED_CONFIG_FIELDS = ("parameters", "weather_rule", "min_gap_business_days")


def scenario_hash(scenario: Scenario, edits: Sequence[Edit] = ()) -> str:
    """sha256 of the scenario inputs plus edits. Ignores scenario_hash and revision."""
    body = scenario.model_dump(mode="json", exclude={"scenario_hash", "revision"})
    for key in _ADDED_CONFIG_FIELDS:
        if body["config"].get(key) in (None, [], {}):
            body["config"].pop(key, None)
    for site in body["sites"]:
        if not site.get("visits"):
            site.pop("visits", None)
    for row in body["current_plan"]:
        if row.get("job_id") is None:
            row.pop("job_id", None)
    payload = {"scenario": body, "edits": _edits.dump_python(list(edits), mode="json")}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()
