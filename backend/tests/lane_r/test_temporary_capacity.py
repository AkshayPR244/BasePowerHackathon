import datetime as dt

import pytest

from app.contracts.models import AddCrewDay, RemoveCrewDay
from app.data import load_scenario
from app.recovery.service import recover


@pytest.mark.parametrize(
    "sid, disruption",
    [
        (
            "standard",
            [RemoveCrewDay(crew_id=c, date=dt.date(2018, 6, 14)) for c in ("IA", "IB", "BA")],
        ),
        ("value_sensitive", [RemoveCrewDay(crew_id="BA", date=dt.date(2018, 6, 13))]),
    ],
)
def test_temporary_crew_gets_a_full_day_after_the_past_is_frozen(sid, disruption):
    scenario = load_scenario(sid)
    out = recover(scenario, disruption, interactive=True)
    added = [
        e
        for o in out.options
        if o.kind == "temporary_capacity"
        for e in o.result.edits
        if isinstance(e, AddCrewDay)
    ]
    assert added
    for e in added:
        full = max(c.available_min for c in scenario.crew_days if set(c.skills) == set(e.skills))
        assert e.available_min == full
