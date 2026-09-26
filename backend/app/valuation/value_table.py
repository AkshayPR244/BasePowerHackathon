"""Site/date coefficients from a continuous price horizon, cached by content hash.

Tiny explicitly uses assumed zero values. All other scenarios require prepared
prices. An unfinished solve raises instead of silently becoming an exact coefficient.
"""

import datetime as dt
import hashlib
import json
import os
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pydantic import TypeAdapter, ValidationError

from app.contracts.hashing import scenario_hash
from app.contracts.models import ValueTableRow
from app.data import load as loader
from app.valuation.battery import dispatch

CACHE_ROOT = Path(__file__).resolve().parents[3] / "data/cache"
ROWS = TypeAdapter(list[ValueTableRow])
MODEL_VERSION = "battery-milp-v1"


def commissioning_utc(day: dt.date, config) -> dt.datetime:
    return dt.datetime.combine(
        day + dt.timedelta(days=1 + config.qualification_lag_days),
        dt.time(),
        ZoneInfo(config.timezone),
    ).astimezone(dt.UTC)


def _series(frame, value_column, start, end):
    """Validate exact interval coverage; never localize naive timestamps or fill gaps."""
    required = {"timestamp_utc", "interval_hours", value_column}
    if not required <= set(frame.columns):
        raise ValueError(f"Prepared series requires {sorted(required)}")
    if not isinstance(frame.timestamp_utc.dtype, pd.DatetimeTZDtype):
        raise ValueError("Energy timestamps must be timezone-aware")
    frame = frame.sort_values("timestamp_utc").copy()
    frame["timestamp_utc"] = frame.timestamp_utc.dt.tz_convert("UTC")
    frame = frame[(frame.timestamp_utc >= start) & (frame.timestamp_utc < end)]
    numeric = frame[["interval_hours", value_column]].to_numpy(dtype=float)
    if not len(frame) or not np.isfinite(numeric).all() or (numeric[:, 0] <= 0).any():
        raise ValueError("Empty, non-finite or invalid energy series")
    if frame.timestamp_utc.duplicated().any():
        raise ValueError("Duplicate energy intervals")
    ends = frame.timestamp_utc + pd.to_timedelta(frame.interval_hours, unit="h")
    if (
        frame.timestamp_utc.iloc[0] != start
        or ends.iloc[-1] != end
        or not np.array_equal(ends.iloc[:-1].to_numpy(), frame.timestamp_utc.iloc[1:].to_numpy())
    ):
        raise ValueError(
            "MISSING_INTERVAL: energy horizon has gaps, overlaps or missing boundaries"
        )
    return frame.reset_index(drop=True)


def _atomic_cache(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            f.write(ROWS.dump_json(rows))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def value_table(
    scenario, *, load_limited=False, export_allowance_kw=0.0, time_limit=30.0
) -> list[ValueTableRow]:
    folder = loader.DATA_ROOT / scenario.scenario_id
    price_path, load_path = folder / "prices.parquet", folder / "loads.parquet"
    price_bytes = price_path.read_bytes() if price_path.exists() else None
    if load_limited and not load_path.exists():
        raise ValueError("Load-limited valuation requires prepared loads.parquet")
    if export_allowance_kw < 0 or not np.isfinite(export_allowance_kw):
        raise ValueError("Export allowance must be finite and nonnegative")
    if not load_limited and export_allowance_kw:
        raise ValueError("Export allowance requires load-limited mode")
    load_bytes = load_path.read_bytes() if load_limited else None
    key = hashlib.sha256(
        json.dumps(
            {
                "model": MODEL_VERSION,
                "scenario": scenario_hash(scenario),
                "prices": hashlib.sha256(price_bytes).hexdigest()
                if price_bytes is not None
                else None,
                "loads": hashlib.sha256(load_bytes).hexdigest() if load_bytes is not None else None,
                "load_limited": load_limited,
                "export_allowance_kw": export_allowance_kw,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    days = [
        scenario.config.planning_start + dt.timedelta(days=i)
        for i in range((scenario.config.planning_end - scenario.config.planning_start).days + 1)
    ]
    expected = {(s.site_id, day) for s in scenario.sites for day in days}
    cache = CACHE_ROOT / f"values-{key}.json"
    if cache.exists():
        try:
            cached = ROWS.validate_json(cache.read_bytes())
            if (
                len(cached) == len(expected)
                and {(r.site_id, r.install_date) for r in cached} == expected
                and all(
                    r.input_hash == key
                    and r.solver_status in ("optimal", "assumed_zero")
                    and r.commissioning_utc == commissioning_utc(r.install_date, scenario.config)
                    for r in cached
                )
            ):
                return cached
        except (ValueError, ValidationError):
            pass  # A partial or corrupt cache is not a source of truth.
    if price_bytes is None:
        if scenario.scenario_id != "tiny" or load_limited:
            raise ValueError("Prepared prices.parquet is required; no implicit zero-price fallback")
        rows = [
            ValueTableRow(
                site_id=s.site_id,
                install_date=day,
                commissioning_utc=commissioning_utc(day, scenario.config),
                value_usd=0,
                solver_status="assumed_zero",
                kind="assumed",
                input_hash=key,
            )
            for s in scenario.sites
            for day in days
        ]
        _atomic_cache(cache, rows)
        return rows
    prices = pd.read_parquet(price_path)
    if "load_zone" not in prices:
        raise ValueError("Prepared prices require load_zone")
    start = dt.datetime.combine(
        scenario.config.planning_start, dt.time(), ZoneInfo(scenario.config.timezone)
    ).astimezone(dt.UTC)
    end = dt.datetime.combine(
        scenario.config.evaluation_end + dt.timedelta(days=1),
        dt.time(),
        ZoneInfo(scenario.config.timezone),
    ).astimezone(dt.UTC)
    by_zone = {
        zone: _series(prices[prices.load_zone == zone], "price_usd_mwh", start, end)
        for zone in {s.load_zone for s in scenario.sites}
    }
    loads = pd.read_parquet(load_path) if load_limited else None
    by_profile = {}
    if loads is not None:
        if "profile_id" not in loads:
            raise ValueError("Prepared loads require profile_id")
        for profile in {s.profile_id for s in scenario.sites}:
            if profile is None:
                raise ValueError("Each load-limited site requires a modeled profile_id")
            series = _series(loads[loads.profile_id == profile], "load_kw", start, end)
            if (series.load_kw < 0).any():
                raise ValueError("Load must be nonnegative")
            by_profile[profile] = series
    batteries = {b.configuration_id: b for b in scenario.config.batteries}
    solved, rows = {}, []
    for s in scenario.sites:
        series = by_zone[s.load_zone]
        profile = by_profile.get(s.profile_id)
        if profile is not None and (
            not series.timestamp_utc.equals(profile.timestamp_utc)
            or not series.interval_hours.equals(profile.interval_hours)
        ):
            raise ValueError("Load and price interval boundaries must match exactly")
        for day in days:
            commission = commissioning_utc(day, scenario.config)
            group = (
                s.configuration_id,
                s.load_zone,
                s.profile_id if load_limited else None,
                commission,
            )
            if group not in solved:
                active = series.timestamp_utc >= commission
                selected = series[active]
                # Exclude intervals straddling commissioning; starts must be on/after commissioning.
                out = dispatch(
                    selected.price_usd_mwh.to_numpy(),
                    selected.interval_hours.to_numpy(),
                    batteries[s.configuration_id],
                    time_limit=time_limit,
                    load_kw=profile.loc[active, "load_kw"].to_numpy()
                    if profile is not None
                    else None,
                    export_allowance_kw=export_allowance_kw,
                )
                if out.solver_status != "optimal" or out.value_usd is None:
                    raise ValueError(
                        f"Valuation solve {out.solver_status}; exact coefficients unavailable"
                    )
                solved[group] = out.value_usd
            rows.append(
                ValueTableRow(
                    site_id=s.site_id,
                    install_date=day,
                    commissioning_utc=commission,
                    value_usd=solved[group],
                    solver_status="optimal",
                    kind="modeled",
                    input_hash=key,
                )
            )
    _atomic_cache(cache, rows)
    return rows
