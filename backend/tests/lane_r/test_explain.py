import datetime as dt

from app.contracts.models import RemoveCrewDay
from app.data import load_scenario
from app.recovery.service import recover


def test_changed_visits_have_honest_constraint_explanations():
    s = load_scenario("tiny_two_visit")
    out = recover(s, [RemoveCrewDay(crew_id="B", date=dt.date(2018, 6, 5))], interactive=True)
    for option in [out.no_action, *out.options]:
        changed = {
            c.job_id or c.site_id
            for c in option.diff_vs_original.changes
            if c.kind in {"moved", "added", "removed"}
        }
        assert changed <= {e.job_id for e in option.explanations}
        assert all(e.constraint and e.text for e in option.explanations)
