import numpy as np
import pytest

from app.valuation.battery import dispatch


@pytest.fixture
def battery(scenario):
    return scenario.config.batteries[0]


def test_conservation_and_boundary(battery):
    hours = np.array([0.25, 0.5, 1.0, 0.25])
    out = dispatch([10, 0, 200, 100], hours, battery)
    assert out.solver_status == "optimal"
    expected = (
        out.energy_kwh[:-1]
        + battery.eta_charge * out.charge_kw * hours
        - out.discharge_kw * hours / battery.eta_discharge
    )
    np.testing.assert_allclose(out.energy_kwh[1:], expected, atol=1e-6)
    assert out.energy_kwh[0] == pytest.approx(battery.reserve_kwh)
    assert out.energy_kwh[-1] == pytest.approx(battery.reserve_kwh)
    assert out.value_usd > 0


def test_limits_and_no_simultaneous(battery):
    out = dispatch([-100, -50, 100, 200], 1.0, battery)
    assert np.all(out.charge_kw <= battery.charge_limit_kw + 1e-9)
    assert np.all(out.discharge_kw <= battery.discharge_limit_kw + 1e-9)
    assert np.all(out.energy_kwh >= battery.reserve_kwh - 1e-9)
    assert np.all(out.energy_kwh <= battery.capacity_kwh + 1e-9)
    assert np.all(np.minimum(out.charge_kw, out.discharge_kw) <= 1e-9)


def test_negative_prices_charge_then_discharge(battery):
    out = dispatch([-100, -100, 200, 200], 1.0, battery)
    assert sum(out.charge_kw[:2]) > 0
    assert sum(out.discharge_kw[:2]) == pytest.approx(0)
    assert sum(out.discharge_kw[2:]) > 0


def test_flat_prices_no_value(battery):
    assert dispatch([50] * 8, 0.25, battery).value_usd == pytest.approx(0)


def test_continuous_horizon_does_not_reset_energy(battery):
    out = dispatch([0, 0, 0, 100, 100, 100], 1.0, battery)
    assert out.energy_kwh[3] > battery.reserve_kwh
    assert out.value_usd > 0


def test_load_limited_sensitivity(battery):
    prices, loads = [0, 10, 200, 100], [0, 0, 0.2, 0.4]
    limited = dispatch(prices, 1.0, battery, load_kw=loads)
    unrestricted = dispatch(prices, 1.0, battery)
    assert np.all(limited.discharge_kw <= np.array(loads) + 1e-9)
    assert limited.value_usd < unrestricted.value_usd
    assert dispatch(prices, 1.0, battery, load_kw=[0] * 4).value_usd == pytest.approx(0)


@pytest.mark.parametrize(
    "prices,hours", [([np.nan], [1]), ([10], [0]), ([10], [-1]), ([10, 20], [1])]
)
def test_bad_arrays_rejected(battery, prices, hours):
    with pytest.raises(ValueError):
        dispatch(prices, hours, battery)
