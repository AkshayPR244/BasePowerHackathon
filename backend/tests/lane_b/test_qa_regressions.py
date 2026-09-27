"""Regressions from the QA sweep of the planner, baselines, and explanation text."""

import datetime as dt
import shutil

import pytest

from app.api.scenarios import load_scenario
from app.compare.diff import diff_plans
from app.contracts.enums import (
    Algorithm,
    JobState,
    Mode,
    ObjectivePolicy,
    PlanStatus,
    ReasonCode,
)
from app.contracts.models import (
    AddCrewDay,
    ChangeAppointment,
    ChangeReadyDate,
    CounterfactualRequest,
    DelayInventory,
    ExtendCrewDay,
    ForceInclude,
    MoveVisit,
    PinVisit,
    PlanRequest,
    ReduceCrewDay,
    RemoveCrewDay,
)
from app.planning import explain
from app.planning.counterfactual import counterfactual
from app.planning.solve import plan


def D(day: int) -> dt.date:
    return dt.date(2018, 6, day)


def run(scenario, edits=(), mode=Mode.recovery, **kw):
    req = PlanRequest(
        scenario_id=scenario.scenario_id, revision=0, mode=mode, edits=list(edits), **kw
    )
    return plan(scenario, req)


@pytest.mark.parametrize("mode", [Mode.strict, Mode.recovery])
def test_forcing_a_blocked_home_is_infeasible(tiny, mode):
    r = run(tiny, [ForceInclude(site_id="S-03")], mode)
    assert r.status == PlanStatus.infeasible
    assert r.message.startswith("S-03 cannot finish by its deadline.")
    assert "panel_upgrade" in r.message
    assert r.validation.valid


@pytest.fixture(scope="module")
def two_visit():
    return load_scenario("tiny_two_visit")


def unlocked(scenario):
    rows = [p.model_copy(update={"locked": False}) for p in scenario.current_plan]
    return scenario.model_copy(update={"current_plan": rows})


@pytest.mark.parametrize("days,unlock", [((4, 5), False), ((4, 6), False), ((4, 5, 6), True)])
def test_value_flag_matches_the_validator(two_visit, days, unlock):
    s = unlocked(two_visit) if unlock else two_visit
    r = run(s, [RemoveCrewDay(crew_id="B", date=D(d)) for d in days])
    assert r.validation.valid
    assert r.objective is not None


BASELINES = [Algorithm.baseline_edf, Algorithm.baseline_nearest_cluster]
BASELINE_CASES = {
    "locked crew-day removed": [RemoveCrewDay(crew_id="A", date=D(5))],
    "locked crew-day too short": [ReduceCrewDay(crew_id="A", date=D(5), available_min=60)],
    "forced home has no legal day": [
        ForceInclude(site_id="N-02"),
        RemoveCrewDay(crew_id="A", date=D(4)),
    ],
    "forced home is blocked": [ForceInclude(site_id="S-03")],
}


@pytest.mark.parametrize("alg", BASELINES)
@pytest.mark.parametrize("edits", BASELINE_CASES.values(), ids=BASELINE_CASES.keys())
def test_baselines_report_infeasible_instead_of_invalid_plans(tiny, alg, edits):
    r = run(tiny, edits, algorithm=alg)
    assert r.status == PlanStatus.infeasible
    assert r.assignments == [] and r.validation.valid
    assert r.message.startswith(("Earliest", "Nearest"))


@pytest.mark.parametrize("alg", BASELINES)
def test_baselines_place_an_install_before_a_locked_battery_day(two_visit, alg):
    r = run(two_visit, [PinVisit(job_id="H2-B")], algorithm=alg)
    assert r.status == PlanStatus.feasible and r.validation.valid


def test_unscheduled_visit_names_missing_inventory(tiny):
    r = run(tiny, [DelayInventory(configuration_id="B13", from_date=D(4), to_date=D(30))])
    out = [u for u in r.unscheduled if u.state == JobState.unscheduled]
    assert out and all(u.reasons == [ReasonCode.NO_INVENTORY] for u in out)
    assert all("B13 battery" in u.detail and "hard blocker" not in u.detail for u in out)


def test_unscheduled_visit_names_its_appointment_window(tiny):
    r = run(tiny, [ChangeAppointment(job_id="N-02", available_from=D(9))])
    n02 = next(u for u in r.unscheduled if u.site_id == "N-02")
    assert n02.reasons == [ReasonCode.NO_LEGAL_DATE]
    assert "appointment window from Sat 9 Jun" in n02.detail


def test_no_legal_date_names_the_install_gap(two_visit):
    sites = [
        s.model_copy(update={"deadline": D(4)}) if s.site_id == "H1" else s for s in two_visit.sites
    ]
    r = run(unlocked(two_visit).model_copy(update={"sites": sites}), mode=Mode.strict)
    assert r.status == PlanStatus.infeasible
    assert "Its install must come at least 1 business day before the battery day" in r.message
    assert "No crew that serves" not in r.message


def test_no_legal_date_names_the_appointment_window(tiny):
    r = run(tiny, [ChangeAppointment(job_id="N-02", available_from=D(5))], Mode.strict)
    assert r.status == PlanStatus.infeasible
    assert "N-02 is due Mon 4 Jun. Its visit has an appointment window from Tue 5 Jun." in r.message


def test_headline_uses_the_newly_late_visit(tiny):
    edits = [RemoveCrewDay(crew_id="B", date=D(4)), RemoveCrewDay(crew_id="A", date=D(4))]
    before = run(tiny, edits)
    after = run(tiny, [*edits, RemoveCrewDay(crew_id="B", date=D(5))])

    def n02_three_days_late(r):
        rows = [
            a.model_copy(update={"days_late": 3}) if a.site_id == "N-02" else a
            for a in r.assignments
        ]
        return r.model_copy(update={"assignments": rows})

    d = diff_plans(n02_three_days_late(before), n02_three_days_late(after))
    assert d.headline.endswith("1 home misses its deadline by 1 day.")


def test_counterfactual_with_bad_input_is_not_called_infeasible(tiny):
    req = PlanRequest(scenario_id="tiny", revision=0, mode=Mode.recovery)
    extra = AddCrewDay(
        crew_id="A", date=D(4), available_min=60, skills=["install"], allowed_clusters=["N"]
    )
    cf = counterfactual(
        tiny, CounterfactualRequest(request=req, base=plan(tiny, req), intervention=extra)
    )
    assert cf.result.status == PlanStatus.invalid_input and not cf.feasible
    assert "infeasible" not in cf.summary and "infeasible" not in cf.diff.headline
    assert "cannot be tested" in cf.summary


def test_every_edit_kind_has_a_description(two_visit):
    edits = [
        ReduceCrewDay(crew_id="I", date=D(5), available_min=200),
        ExtendCrewDay(crew_id="B", date=D(5), extra_min=60),
        ChangeAppointment(job_id="H3-B", available_from=D(5), available_to=D(6)),
        PinVisit(job_id="H1-B"),
        MoveVisit(job_id="H3-I", crew_id="I", date=D(4)),
    ]
    texts = [explain.describe_edit(e, two_visit) for e in edits]
    assert texts == [
        "Crew I has only 200 min on Tue 5 Jun.",
        "Crew B works 60 min overtime on Tue 5 Jun.",
        "H3 battery day now has an appointment window from Tue 5 Jun to Wed 6 Jun.",
        "H1 battery day stays on its current crew-day.",
        "H3 install moves to Crew I on Mon 4 Jun.",
    ]
    r = run(two_visit, edits[1:4])
    assert r.message.startswith(" ".join(texts[1:4])) and "  " not in r.message


def test_plan_text_handles_plural_and_zero_cases(tiny, two_visit):
    two_forced = [
        RemoveCrewDay(crew_id="A", date=D(4)),
        ForceInclude(site_id="N-02"),
        ChangeReadyDate(site_id="S-02", ready_date=D(6)),
        ForceInclude(site_id="S-02"),
    ]
    r = run(tiny, two_forced)
    assert r.message.startswith("N-02 and S-02 cannot finish by their deadlines.")
    none_left = run(unlocked(two_visit), [RemoveCrewDay(crew_id="B", date=D(d)) for d in (4, 5, 6)])
    assert "No home can be scheduled." in none_left.message
    assert "All 0" not in none_left.message and "3 homes are blocked" in none_left.message
    moved = run(two_visit, [MoveVisit(job_id="H3-I", crew_id="I", date=D(6))])
    assert "1 visit moves, so 1 customer needs a new date." in moved.message
    assert "1 home is not scheduled." in moved.message


def test_plan_id_names_a_non_default_policy(tiny):
    default = run(tiny)
    other = run(tiny, objective_policy=ObjectivePolicy.deadline_travel_only)
    assert default.plan_id != other.plan_id
    assert "deadline_travel_only" in other.plan_id
    assert default.plan_id == f"tiny-r0-recovery-{tiny.scenario_hash[:8]}"


def test_install_may_stand_alone_in_recovery():
    s = load_scenario("standard")
    r = run(s, [MoveVisit(job_id="W-03-I", crew_id="IA", date=D(15))])
    assert r.status in (PlanStatus.optimal, PlanStatus.feasible) and r.validation.valid
    install = next(a for a in r.assignments if a.job_id == "W-03-I")
    assert (install.crew_id, install.date) == ("IA", D(15))
    assert "W-03-B" not in {a.job_id for a in r.assignments}


def test_missing_prices_give_a_valid_zero_value_plan(tmp_path, monkeypatch):
    from app.data import load as loader
    from app.valuation import value_table as vt

    shutil.copytree(loader.DATA_ROOT / "tiny_two_visit", tmp_path / "tiny_two_visit")
    (tmp_path / "tiny_two_visit" / "prices.parquet").unlink()
    monkeypatch.setattr(loader, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(vt, "CACHE_ROOT", tmp_path / "cache")
    s = loader.load_scenario("tiny_two_visit")
    r = run(s, mode=Mode.strict)
    assert r.status == PlanStatus.optimal and r.validation.valid
    assert r.objective.value_distinguishes_choices is False
    assert r.objective.operating_value_usd == 0
    assert "Energy values are unavailable" in r.message
