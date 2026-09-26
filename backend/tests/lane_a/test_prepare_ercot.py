import datetime as dt

import pandas as pd
import pytest

from app.data.load import ScenarioLoadError
from app.data.prepare_ercot import TZ, interval_start_utc, normalize_prices


def rows_for_day(day):
    start = dt.datetime.combine(day, dt.time(), TZ).astimezone(dt.UTC)
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), TZ).astimezone(dt.UTC)
    rows = []
    for timestamp in pd.date_range(start, end, freq="15min", inclusive="left"):
        local = timestamp.to_pydatetime().astimezone(TZ)
        rows.append(
            {
                "Delivery Date": day.isoformat(),
                "Delivery Hour": local.hour + 1,
                "Delivery Interval": local.minute // 15 + 1,
                "Repeated Hour Flag": "Y" if local.fold else "N",
                "Settlement Point Name": "LZ_HOUSTON",
                "Settlement Point Price": 30.0,
            }
        )
    return rows


@pytest.mark.parametrize(
    "day,count",
    [(dt.date(2018, 3, 11), 92), (dt.date(2018, 11, 4), 100), (dt.date(2018, 6, 4), 96)],
)
def test_dst_and_interval_completeness(day, count):
    frame = normalize_prices(rows_for_day(day), start=day, end=day)
    assert len(frame) == count
    assert str(frame.timestamp_utc.dt.tz) == "UTC"
    assert frame.timestamp_utc.diff().dropna().eq(pd.Timedelta(minutes=15)).all()


def test_interval_ending_conversion():
    assert interval_start_utc("06/04/2018", 1, 1) == dt.datetime(2018, 6, 4, 5, tzinfo=dt.UTC)
    assert interval_start_utc("06/04/2018", 24, 4) == dt.datetime(2018, 6, 5, 4, 45, tzinfo=dt.UTC)
    first = interval_start_utc("11/04/2018", 2, 1, "N")
    second = interval_start_utc("11/04/2018", 2, 1, "Y")
    assert second - first == dt.timedelta(hours=1)


def test_no_filling_missing_intervals():
    day = dt.date(2018, 6, 4)
    with pytest.raises(ScenarioLoadError) as error:
        normalize_prices(rows_for_day(day)[1:], start=day, end=day)
    assert error.value.issues[0].code == "MISSING_INTERVAL"


def test_duplicate_interval_rejected():
    day = dt.date(2018, 6, 4)
    rows = rows_for_day(day)
    with pytest.raises(ScenarioLoadError) as error:
        normalize_prices(rows + rows[:1], start=day, end=day)
    assert error.value.issues[0].code == "DUPLICATE_ID"


@pytest.mark.parametrize("day,hour,flag", [("03/11/2018", 3, "N"), ("06/04/2018", 2, "Y")])
def test_invalid_local_times_rejected(day, hour, flag):
    with pytest.raises(ValueError):
        interval_start_utc(day, hour, 1, flag)


def test_selects_lz_type_without_mixing_lzew():
    day = dt.date(2018, 6, 4)
    regular = [{**r, "Settlement Point Type": "LZ"} for r in rows_for_day(day)]
    alternate = [
        {**r, "Settlement Point Type": "LZEW", "Settlement Point Price": 999}
        for r in rows_for_day(day)
    ]
    frame = normalize_prices(regular + alternate, start=day, end=day)
    assert len(frame) == 96
    assert frame.price_usd_mwh.eq(30).all()
