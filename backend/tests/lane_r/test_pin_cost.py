from app.contracts.models import PinVisit
from app.data import load_scenario
from app.recovery.service import evaluate


def test_pin_cost_is_comparison_not_claim_of_optimum():
    s = load_scenario("tiny_two_visit")
    option = evaluate(s, [], [PinVisit(job_id="H3-B")])
    assert option.result.validation.valid
    assert any(
        e.constraint == "pin_visit" and "computed unpinned" in e.text for e in option.explanations
    )
