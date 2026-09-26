"""B-14: counterfactuals match the tiny expected results."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.contracts.enums import Mode
from app.contracts.models import (
    AddCrewDay,
    CounterfactualRequest,
    CounterfactualResult,
    ForceInclude,
    PlanRequest,
)
from app.planning.counterfactual import counterfactual
from app.planning.solve import plan
from tests.lane_b.conftest import REMOVE_A_MON, deferred, expected, frozen, slots

client = TestClient(app)
REQ = PlanRequest(scenario_id="tiny", revision=1, mode=Mode.recovery, edits=[REMOVE_A_MON])
ADD_C = AddCrewDay(
    crew_id="C", date="2018-06-04", available_min=480, skills=["install"], allowed_clusters=["N"]
)


@pytest.mark.parametrize(
    "name,intervention",
    [
        ("counterfactual_force_n02", ForceInclude(site_id="N-02")),
        ("counterfactual_add_c_mon", ADD_C),
    ],
)
def test_matches_expected(tiny, name, intervention):
    base = plan(tiny, REQ)
    cf = counterfactual(
        tiny, CounterfactualRequest(request=REQ, base=base, intervention=intervention)
    )
    e = expected(name)
    assert cf.feasible == e.feasible
    assert cf.result.status == e.result.status
    assert frozen(cf.result.objective) == frozen(e.result.objective)
    assert slots(cf.result) == slots(e.result)
    assert deferred(cf.result) == deferred(e.result)
    assert frozen(cf.diff.summary) == frozen(e.diff.summary)


def test_summaries_name_the_cause(tiny):
    base = plan(tiny, REQ)
    force = counterfactual(
        tiny,
        CounterfactualRequest(request=REQ, base=base, intervention=ForceInclude(site_id="N-02")),
    )
    assert force.summary.startswith("Including N-02 by its deadline is infeasible.")
    add = counterfactual(tiny, CounterfactualRequest(request=REQ, base=base, intervention=ADD_C))
    assert "N-02 is back on time" in add.summary


def test_endpoint(tiny):
    base = plan(tiny, REQ)
    body = {
        "request": REQ.model_dump(mode="json"),
        "base": base.model_dump(mode="json"),
        "intervention": ADD_C.model_dump(mode="json"),
    }
    r = client.post("/api/plans/counterfactual", json=body)
    assert r.status_code == 200
    assert CounterfactualResult.model_validate(r.json()).feasible
