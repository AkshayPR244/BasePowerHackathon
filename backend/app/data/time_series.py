"""Strict interval alignment for prepared energy series."""

import numpy as np
import pandas as pd


def validate_energy_series(frame, value_column, start, end):
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
