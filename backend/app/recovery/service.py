"""Recovery engine seam. Lane R owns it. Lane W calls recover() for the season replay.

STUB: returns fixture output built by scripts/build_stubs.py until lane R implements these.
Every stub payload carries stub=true.
"""

from pathlib import Path

from app.contracts.models import (
    ApproveResult,
    Edit,
    PlannedInstall,
    RecoveryOption,
    RecoveryOptionsResult,
    Scenario,
)

FIXTURES = Path(__file__).parent / "fixtures"


def recover(
    scenario: Scenario,
    disruption: list[Edit],
    current_plan: list[PlannedInstall] | None = None,
    economics: dict[str, float] | None = None,
    interactive: bool = False,
) -> RecoveryOptionsResult:
    """Impact, no action, and the recovery options for one disruption."""
    # TODO(lane-r): replace the stub.
    return RecoveryOptionsResult.model_validate_json((FIXTURES / "options.json").read_text("utf-8"))


def evaluate(
    scenario: Scenario,
    disruption: list[Edit],
    interventions: list[Edit],
    current_plan: list[PlannedInstall] | None = None,
    economics: dict[str, float] | None = None,
    interactive: bool = True,
) -> RecoveryOption:
    """One manual change, as a RecoveryOption of kind custom."""
    # TODO(lane-r): replace the stub.
    return RecoveryOption.model_validate_json((FIXTURES / "evaluate.json").read_text("utf-8"))


def approve(scenario: Scenario, option: RecoveryOption) -> ApproveResult:
    """The chosen option becomes the new current plan."""
    # TODO(lane-r): replace the stub.
    return ApproveResult.model_validate_json((FIXTURES / "approve.json").read_text("utf-8"))
