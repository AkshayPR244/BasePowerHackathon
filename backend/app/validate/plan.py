"""Independent plan validator. Lane A owns it.

Recompute every constraint from assignments and scenario inputs.
Never import app.planning or app.baselines (tests/contract/test_boundaries.py checks this).
"""

from app.contracts.models import PlanResult, Scenario, ValidationReport


def validate_plan(scenario: Scenario, result: PlanResult) -> ValidationReport:
    # TODO(lane-a): replace the stub. Scenario must already have the result's edits applied.
    return ValidationReport(checked=False, valid=False, issues=[], validator="stub")
