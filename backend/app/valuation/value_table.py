"""Source-derived valuation coefficients. Tiny deliberately has zero energy values."""

import datetime as dt
from zoneinfo import ZoneInfo

from app.contracts.models import ValueTableRow


def value_table(scenario):
    if scenario.scenario_id != "tiny":
        raise ValueError("Prepared prices are required for this scenario")
    return [
        ValueTableRow(
            site_id=s.site_id,
            install_date=day,
            commissioning_utc=dt.datetime.combine(
                day + dt.timedelta(days=1 + scenario.config.qualification_lag_days),
                dt.time(),
                ZoneInfo(scenario.config.timezone),
            ).astimezone(dt.UTC),
            value_usd=0,
            solver_status="assumed_zero",
            kind="assumed",
            input_hash=scenario.scenario_hash,
        )
        for s in scenario.sites
        for day in sorted({c.date for c in scenario.crew_days})
    ]
