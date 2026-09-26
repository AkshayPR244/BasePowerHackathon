import pytest

from app.validate.enumerate_tiny import enumerate_tiny
from tests.lane_a.conftest import edited_scenario, expected_plans


@pytest.mark.parametrize("name,plan", list(expected_plans()))
def test_enumerator_expected(name, plan):
    actual = enumerate_tiny(
        edited_scenario(plan),
        plan.mode,
        [e.site_id for e in plan.edits if e.kind == "force_include"],
    )
    if plan.status == "infeasible":
        assert actual is None
    else:
        assert actual is not None
        assert actual.optimal_count == 1
        for field, value in plan.objective.model_dump().items():
            assert getattr(actual.objective, field) == pytest.approx(value, abs=0.000051)
        assert actual.assignments == plan.assignments


def test_enumerator_rejects_large_search(scenario):
    with pytest.raises(ValueError, match="combination budget"):
        enumerate_tiny(scenario, max_combinations=1)
