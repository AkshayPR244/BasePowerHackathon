"""Scenario source for the API. Uses Lane A's loader when it exists."""

from app.contracts.models import Scenario, ScenarioSummary

try:
    from app.data.load import load_scenario, scenario_ids  # type: ignore[attr-defined]
except ImportError:
    from app.api.fixture_loader import load_scenario, scenario_ids

__all__ = ["load_scenario", "scenario_ids", "summarize"]


def summarize(s: Scenario) -> ScenarioSummary:
    return ScenarioSummary(
        scenario_id=s.scenario_id,
        name=s.config.name,
        scenario_hash=s.scenario_hash,
        planning_start=s.config.planning_start,
        planning_end=s.config.planning_end,
        n_sites=len(s.sites),
        n_crews=len({c.crew_id for c in s.crew_days}),
        n_crew_days=len(s.crew_days),
        synthetic=s.config.synthetic,
    )
