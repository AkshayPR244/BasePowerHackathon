import datetime as dt

import pandas as pd
import pytest

from app.data.prepare_resstock import ENERGY_COLUMN, normalize_loads


def test_resstock_fixed_est_interval_end_and_kw():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2018-06-04 00:15", "2018-06-04 00:30"]),
            ENERGY_COLUMN: [0.5, 1.0],
        }
    )
    result = normalize_loads(
        frame,
        start=dt.datetime(2018, 6, 4, 5, tzinfo=dt.UTC),
        end=dt.datetime(2018, 6, 4, 5, 30, tzinfo=dt.UTC),
    )
    assert result.load_kw.tolist() == [2.0, 4.0]
    assert result.timestamp_utc.iloc[0].hour == 5  # EST is UTC-5 even in summer.


def test_resstock_missing_interval_rejected():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2018-06-04 00:15", "2018-06-04 00:45"]),
            ENERGY_COLUMN: [0.5, 1.0],
        }
    )
    with pytest.raises(ValueError, match="MISSING_INTERVAL"):
        normalize_loads(
            frame,
            start=dt.datetime(2018, 6, 4, 5, tzinfo=dt.UTC),
            end=dt.datetime(2018, 6, 4, 5, 45, tzinfo=dt.UTC),
        )
