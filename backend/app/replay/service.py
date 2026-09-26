"""Weather evidence seam. Lane W owns it.

STUB: returns fixture output built by scripts/build_stubs.py until lane W implements these.
Storm events are real Houston Hobby observations. Cases and the season replay are stubs.
"""

from pathlib import Path

from pydantic import TypeAdapter

from app.contracts.models import Case, SeasonReplay, StormEvent

FIXTURES = Path(__file__).parent / "fixtures"


def storms() -> list[StormEvent]:
    return TypeAdapter(list[StormEvent]).validate_json((FIXTURES / "storms.json").read_text())


def cases() -> list[Case]:
    return TypeAdapter(list[Case]).validate_json((FIXTURES / "cases.json").read_text())


def season_replay() -> SeasonReplay:
    # TODO(lane-w): replay every storm event through app.recovery.service.recover().
    return SeasonReplay.model_validate_json((FIXTURES / "season_replay.json").read_text())
