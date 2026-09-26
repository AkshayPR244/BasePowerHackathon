"""Reproduce the standard recovery timings; run with PYTHONPATH=backend from the repo root."""

import datetime as dt
import json
import time
from pathlib import Path

from app.contracts.models import RemoveCrewDay
from app.data import load_scenario
from app.recovery.service import approve, evaluate, recover
from app.valuation.value_table import value_table


def main():
    scenario = load_scenario("standard")
    edits = [RemoveCrewDay(crew_id="BA", date=dt.date(2018, 6, 7))]
    start = time.monotonic()
    value_table(scenario)
    output = {"preparation_s": round(time.monotonic() - start, 3), "runs": []}
    for interactive in (True, False):
        start = time.monotonic()
        result = recover(scenario, edits, interactive=interactive)
        output["runs"].append(
            {
                "interactive": interactive,
                "elapsed_s": round(time.monotonic() - start, 3),
                "options": [
                    {
                        "kind": o.kind,
                        "action": o.action_label,
                        "status": o.status,
                        "validated": o.result.validation.valid,
                        "missed": o.counts.deadlines_missed,
                        "visits_moved": o.counts.visits_moved,
                        "customers": o.counts.customers_to_reschedule,
                        "cost": o.economics.net_impact_usd,
                        "advantage_vs_no_action": o.economics.advantage_vs_no_action_usd,
                    }
                    for o in [result.no_action, *result.options]
                ],
            }
        )
    start = time.monotonic()
    recover(scenario, edits, interactive=True)
    output["cache_hit_s"] = round(time.monotonic() - start, 3)
    start = time.monotonic()
    option = evaluate(scenario, edits, [], interactive=True)
    approved = approve(scenario, option)
    output["evaluate_approve"] = {
        "elapsed_s": round(time.monotonic() - start, 3),
        "status": option.status,
        "validated": option.result.validation.valid,
        "approved_visits": len(approved.new_current_plan),
    }
    Path("lanes/R-engine/evidence.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
