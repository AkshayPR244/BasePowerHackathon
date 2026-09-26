import datetime as dt

import pandas as pd
import pytest

from app.data import load as loader
from app.valuation import value_table as module


@pytest.fixture
def valued(scenario, tmp_path, monkeypatch):
    scenario.scenario_id = "valuation_test"
    scenario.config.planning_end = dt.date(2018, 6, 5)
    scenario.config.evaluation_end = dt.date(2018, 6, 6)
    scenario.sites = scenario.sites[:2]
    folder = tmp_path / scenario.scenario_id
    folder.mkdir()
    # Three complete Chicago calendar days.
    timestamps = pd.date_range("2018-06-04T05:00:00Z", periods=72, freq="h")
    frame = pd.DataFrame(
        {
            "timestamp_utc": timestamps,
            "interval_hours": 1.0,
            "load_zone": "LZ_HOUSTON",
            "price_usd_mwh": [0, 100] * 36,
        }
    )
    frame.to_parquet(folder / "prices.parquet", index=False)
    monkeypatch.setattr(loader, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(module, "CACHE_ROOT", tmp_path / "cache")
    return scenario, folder


def test_value_table_identical_sites_and_later_commissioning(valued):
    scenario, _ = valued
    rows = module.value_table(scenario)
    assert len(rows) == 4
    assert rows[0].value_usd == rows[2].value_usd
    assert rows[1].value_usd == rows[3].value_usd
    assert rows[0].value_usd >= rows[1].value_usd > 0
    assert all(r.solver_status == "optimal" and r.kind == "modeled" for r in rows)
    assert rows[0].commissioning_utc == dt.datetime(2018, 6, 5, 5, tzinfo=dt.UTC)


def test_cache_second_call_no_solves_and_price_invalidation(valued, monkeypatch):
    scenario, folder = valued
    original = module.dispatch
    calls = []

    def tracked(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "dispatch", tracked)
    first = module.value_table(scenario)
    assert len(calls) == 2  # Identical sites share each commissioning solve.
    assert module.value_table(scenario) == first
    assert len(calls) == 2
    p = folder / "prices.parquet"
    frame = pd.read_parquet(p)
    frame["price_usd_mwh"] *= 2
    frame.to_parquet(p, index=False)
    second = module.value_table(scenario)
    assert len(calls) == 4
    assert second[0].input_hash != first[0].input_hash
    assert second[0].value_usd == pytest.approx(2 * first[0].value_usd)


def test_qualification_lag_and_empty_horizon(valued):
    scenario, _ = valued
    scenario.config.qualification_lag_days = 1
    delayed = module.value_table(scenario)
    assert delayed[0].commissioning_utc.day == 6
    assert delayed[1].value_usd == 0
    assert delayed[1].solver_status == "optimal"


@pytest.mark.parametrize("mutation", ["gap", "naive", "duplicate"])
def test_bad_prices_fail_closed(valued, mutation):
    scenario, folder = valued
    p = folder / "prices.parquet"
    frame = pd.read_parquet(p)
    if mutation == "gap":
        frame = frame.drop(30)
    elif mutation == "naive":
        frame["timestamp_utc"] = frame.timestamp_utc.dt.tz_localize(None)
    else:
        frame = pd.concat([frame, frame.iloc[:1]])
    frame.to_parquet(p, index=False)
    with pytest.raises(ValueError):
        module.value_table(scenario)


def test_nonoptimal_solve_not_used(valued, monkeypatch):
    from types import SimpleNamespace

    scenario, _ = valued
    monkeypatch.setattr(
        module, "dispatch", lambda *a, **k: SimpleNamespace(solver_status="limit", value_usd=123)
    )
    with pytest.raises(ValueError, match="exact coefficients unavailable"):
        module.value_table(scenario)
    assert not list(module.CACHE_ROOT.glob("*.json"))


def test_load_limited_table_requires_aligned_modeled_profiles(valued):
    scenario, folder = valued
    for s in scenario.sites:
        s.profile_id = "archetype"
    frame = pd.read_parquet(folder / "prices.parquet")
    frame = frame.drop(columns=["price_usd_mwh", "load_zone"])
    frame["profile_id"], frame["load_kw"] = "archetype", 0.1
    frame.to_parquet(folder / "loads.parquet", index=False)
    limited = module.value_table(scenario, load_limited=True)
    unrestricted = module.value_table(scenario)
    assert limited[0].value_usd < unrestricted[0].value_usd
    assert limited[0].input_hash != unrestricted[0].input_hash
