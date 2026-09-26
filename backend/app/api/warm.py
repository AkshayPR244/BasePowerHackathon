"""Build every scenario's value table in the background so no request pays for it."""

import threading
import time

from app.api.scenarios import load_scenario, scenario_ids
from app.valuation import value_table as valuation

_state: dict[str, str] = {"values": "not_started"}
_lock = threading.Lock()


def status() -> dict[str, str]:
    with _lock:
        return dict(_state)


def _set(**kw: str) -> None:
    with _lock:
        _state.update(kw)


def _run() -> None:
    _set(values="warming")
    t0 = time.monotonic()
    failed = []
    for sid in scenario_ids():
        try:
            valuation.value_table(load_scenario(sid))
        except Exception as e:  # noqa: BLE001 - one bad scenario must not stop the others
            failed.append(f"{sid}: {e}")
    elapsed = f"{time.monotonic() - t0:.1f}"
    if failed:
        _set(values="failed", values_error="; ".join(failed), values_seconds=elapsed)
    else:
        _set(values="ready", values_seconds=elapsed)


def start() -> threading.Thread:
    thread = threading.Thread(target=_run, name="warm-values", daemon=True)
    thread.start()
    return thread
