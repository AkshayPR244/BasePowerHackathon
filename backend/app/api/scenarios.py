"""Scenario source for the API: Lane A's loader, cached until a scenario file changes."""

import re
import threading

from app.contracts.models import Scenario
from app.data import ScenarioLoadError, scenario_ids, summarize
from app.data import load as loader
from app.data.load import load_scenario as _load

__all__ = ["ScenarioLoadError", "load_scenario", "scenario_ids", "summarize"]

_lock = threading.Lock()
_cache: dict[str, tuple[tuple, Scenario]] = {}


def _stamp(scenario_id: str) -> tuple:
    folder = loader.DATA_ROOT / scenario_id
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    return (str(folder),) + tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files)


def load_scenario(scenario_id: str) -> Scenario:
    """Return a private copy: callers may change the scenario they get."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", scenario_id):
        return _load(scenario_id)
    try:
        stamp = _stamp(scenario_id)
    except OSError:
        return _load(scenario_id)
    with _lock:
        hit = _cache.get(scenario_id)
    if hit is None or hit[0] != stamp:
        hit = (stamp, _load(scenario_id))
        with _lock:
            _cache[scenario_id] = hit
    return hit[1].model_copy(deep=True)
