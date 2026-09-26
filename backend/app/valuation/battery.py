"""Continuous-horizon battery MILP with explicit exclusive charging/discharging."""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from app.contracts.models import BatteryConfig


@dataclass(frozen=True)
class DispatchResult:
    solver_status: str
    value_usd: float | None
    charge_kw: np.ndarray
    discharge_kw: np.ndarray
    energy_kwh: np.ndarray
    gap: float | None
    message: str


def dispatch(
    price,
    interval_hours,
    battery: BatteryConfig,
    *,
    time_limit=30.0,
    load_kw=None,
    export_allowance_kw=0.0,
) -> DispatchResult:
    """Gross operating margin; reserve energy is identical at both boundaries.

    Optional load_kw is a modeled demand series limiting discharge, not a bill
    model. Non-optimal results carry status and may not become exact coefficients.
    """
    price = np.asarray(price, dtype=float)
    hours = np.asarray(interval_hours, dtype=float)
    if hours.ndim == 0:
        hours = np.full(len(price), float(hours))
    if price.ndim != 1 or hours.shape != price.shape:
        raise ValueError("Prices and interval_hours must be aligned one-dimensional arrays")
    if not np.isfinite(price).all() or not np.isfinite(hours).all() or (hours <= 0).any():
        raise ValueError("Prices must be finite and interval hours must be positive and finite")
    b = battery
    if not (
        0 <= b.reserve_kwh <= b.capacity_kwh
        and b.capacity_kwh > 0
        and 0 < b.eta_charge <= 1
        and 0 < b.eta_discharge <= 1
    ):
        raise ValueError("Invalid battery capacity, reserve or efficiency")
    if not np.isfinite(time_limit) or time_limit <= 0:
        raise ValueError("time_limit must be positive and finite")
    discharge_limit = np.full(len(price), b.discharge_limit_kw)
    if not np.isfinite(export_allowance_kw) or export_allowance_kw < 0:
        raise ValueError("Export allowance must be nonnegative and finite")
    if load_kw is not None:
        load = np.asarray(load_kw, dtype=float)
        if load.shape != price.shape or not np.isfinite(load).all() or (load < 0).any():
            raise ValueError("Loads must be aligned, finite and nonnegative")
        discharge_limit = np.minimum(discharge_limit, load + export_allowance_kw)
    elif export_allowance_kw:
        raise ValueError("An export allowance requires a load series")
    t_count = len(price)
    if not t_count:
        return DispatchResult(
            "optimal",
            0.0,
            np.array([]),
            np.array([]),
            np.array([b.reserve_kwh]),
            0.0,
            "Empty operating horizon",
        )
    ic, id_, ie, im = 0, t_count, 2 * t_count, 3 * t_count + 1
    n = 4 * t_count + 1
    cost = np.zeros(n)
    cost[ic : ic + t_count] = price / 1000 * hours
    cost[id_ : id_ + t_count] = -price / 1000 * hours
    matrix = lil_matrix((3 * t_count, n))
    lo, hi = np.zeros(3 * t_count), np.zeros(3 * t_count)
    for t in range(t_count):
        matrix[t, ie + t + 1] = 1
        matrix[t, ie + t] = -1
        matrix[t, ic + t] = -b.eta_charge * hours[t]
        matrix[t, id_ + t] = hours[t] / b.eta_discharge
        matrix[t_count + t, ic + t] = 1
        matrix[t_count + t, im + t] = -b.charge_limit_kw
        lo[t_count + t] = -np.inf
        matrix[2 * t_count + t, id_ + t] = 1
        matrix[2 * t_count + t, im + t] = discharge_limit[t]
        lo[2 * t_count + t] = -np.inf
        hi[2 * t_count + t] = discharge_limit[t]
    lower, upper = np.zeros(n), np.full(n, np.inf)
    upper[ic : ic + t_count] = b.charge_limit_kw
    upper[id_ : id_ + t_count] = discharge_limit
    lower[ie : ie + t_count + 1] = b.reserve_kwh
    upper[ie : ie + t_count + 1] = b.capacity_kwh
    lower[ie] = upper[ie] = lower[ie + t_count] = upper[ie + t_count] = b.reserve_kwh
    upper[im : im + t_count] = 1
    integrality = np.zeros(n)
    integrality[im : im + t_count] = 1
    result = milp(
        cost,
        constraints=LinearConstraint(matrix.tocsr(), lo, hi),
        bounds=Bounds(lower, upper),
        integrality=integrality,
        options={"time_limit": float(time_limit), "mip_rel_gap": 0.0},
    )
    status = {0: "optimal", 1: "limit", 2: "infeasible", 3: "unbounded", 4: "error"}.get(
        result.status, "error"
    )
    if result.x is None:
        return DispatchResult(
            status, None, np.array([]), np.array([]), np.array([]), None, result.message
        )
    charge = result.x[ic : ic + t_count]
    discharge = result.x[id_ : id_ + t_count]
    energy = result.x[ie : ie + t_count + 1]
    # Check physical residuals before exposing even an incumbent.
    residual = np.diff(energy) - b.eta_charge * charge * hours + discharge * hours / b.eta_discharge
    valid = (
        np.max(np.abs(residual)) <= 1e-6
        and np.min(energy) >= b.reserve_kwh - 1e-6
        and np.max(energy) <= b.capacity_kwh + 1e-6
        and np.max(np.minimum(charge, discharge)) <= 1e-7
        and np.all(charge >= -1e-7)
        and np.all(charge <= b.charge_limit_kw + 1e-7)
        and np.all(discharge >= -1e-7)
        and np.all(discharge <= discharge_limit + 1e-7)
        and abs(energy[0] - b.reserve_kwh) <= 1e-6
        and abs(energy[-1] - b.reserve_kwh) <= 1e-6
    )
    if not valid:
        raise ValueError("Battery solver returned a physically invalid incumbent")
    value = float(np.sum(price / 1000 * (discharge - charge) * hours))
    gap = getattr(result, "mip_gap", None)
    return DispatchResult(
        status,
        value,
        charge,
        discharge,
        energy,
        float(gap) if gap is not None else None,
        result.message,
    )
