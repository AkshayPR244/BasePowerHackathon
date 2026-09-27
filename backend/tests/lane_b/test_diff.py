"""B-12: the compare endpoint returns a changelog-style diff."""

from fastapi.testclient import TestClient

from app.api.main import app
from app.compare.diff import diff_plans
from tests.lane_b.conftest import expected, frozen

client = TestClient(app)


def _strip(changes):
    return [c.model_dump(exclude={"note"}) for c in changes]


def test_diff_matches_expected():
    before, after = expected("plan_strict"), expected("plan_recovery_remove_a_mon")
    d = diff_plans(before, after)
    e = expected("compare_strict_vs_recovery")
    assert _strip(d.changes) == _strip(e.changes)
    assert frozen(d.summary) == frozen(e.summary)
    assert d.headline == e.headline.replace("1 misses", "1 home misses")


def test_notes_read_like_a_changelog():
    d = diff_plans(expected("plan_strict"), expected("plan_recovery_remove_a_mon"))
    notes = [c.note for c in d.changes]
    assert notes[0] == "N-02 moves from Crew A Mon 4 Jun to Crew A Tue 5 Jun. 1 day late."
    assert notes[1] == "N-03 moves from Crew A Tue 5 Jun to Crew A Wed 6 Jun."


def test_same_plan_has_no_changes():
    p = expected("plan_strict")
    d = diff_plans(p, p)
    assert d.changes == [] and d.headline == "No jobs change."


def test_endpoint():
    body = {
        "before": expected("plan_strict").model_dump(mode="json"),
        "after": expected("plan_recovery_remove_a_mon").model_dump(mode="json"),
    }
    r = client.post("/api/plans/compare", json=body)
    assert r.status_code == 200
    assert r.json()["summary"]["newly_late"] == 1
