"""Build every scenario's value table in the background at startup.

A request that arrives during warm-up waits for the same build and then reads the cache.
"""

import logging
import threading
import time

from app.api.scenarios import load_scenario, scenario_ids
from app.valuation import value_table as valuation

_state: dict[str, str] = {"values": "not_started"}
_lock = threading.Lock()
log = logging.getLogger("slackline.api")


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
    try:
        ids = scenario_ids()
    except Exception:  # noqa: BLE001 - health must leave "warming" even when the data folder fails
        log.exception("value warm-up could not list scenarios")
        _set(values="failed", values_error="Could not list scenarios. See the server log.")
        return
    for sid in ids:
        try:
            valuation.value_table(load_scenario(sid))
        except Exception:  # noqa: BLE001 - one bad scenario must not stop the others
            log.exception("value warm-up failed for scenario %s", sid)
            failed.append(sid)
    elapsed = f"{time.monotonic() - t0:.1f}"
    if failed:
        error = "Value tables failed for " + ", ".join(failed) + ". See the server log."
        _set(values="failed", values_error=error, values_seconds=elapsed)
    else:
        _set(values="ready", values_seconds=elapsed)


def start() -> threading.Thread:
    thread = threading.Thread(target=_run, name="warm-values", daemon=True)
    thread.start()
    return thread
