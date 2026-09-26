"""Business days: weekdays that are not US federal holidays (observed dates)."""

import datetime as dt


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: dt.date) -> dt.date:
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def federal_holidays(year: int) -> set[dt.date]:
    days = {
        _observed(dt.date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed(dt.date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 10, 0, 2),  # Columbus Day
        _observed(dt.date(year, 11, 11)),
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(dt.date(year, 12, 25)),
    }
    if year >= 2021:
        days.add(_observed(dt.date(year, 6, 19)))  # Juneteenth
    return days


def is_business_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in federal_holidays(d.year)


def business_days(start: dt.date, count: int) -> list[dt.date]:
    out, d = [], start
    while len(out) < count:
        if is_business_day(d):
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def business_ordinal(d: dt.date, origin: dt.date) -> int:
    """Business days in (origin, d]. Non-business days share the previous business day's number."""
    lo, hi, sign = (origin, d, 1) if d >= origin else (d, origin, -1)
    count, day = 0, lo
    while day < hi:
        day += dt.timedelta(days=1)
        count += is_business_day(day)
    return sign * count
