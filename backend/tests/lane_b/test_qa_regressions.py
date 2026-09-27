"""Regressions from the QA sweep of the planner, baselines, and explanation text."""

import datetime as dt
import shutil

import pytest

from app.api.scenarios import load_scenario
from app.contracts.enums import Mode, PlanStatus
from app.contracts.models import ForceInclude, MoveVisit, PlanRequest, RemoveCrewDay
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
