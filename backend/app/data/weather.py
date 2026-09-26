"""Observed hourly weather and the rule that turns it into lost crew-days.

Source: METAR reports from the Iowa Environmental Mesonet ASOS archive (no key).
Open-Meteo's historical API is kept for comparison. Its reanalysis reports no
thunderstorm codes for Houston in summer 2018, so it cannot express the lightning rule.
"""

import csv
import datetime as dt
import io
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.contracts.models import WeatherRule

IEM_URL = (
    "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={station}"
    "&data=wxcodes&data=p01i&year1={s.year}&month1={s.month}&day1={s.day}"
    "&year2={e.year}&month2={e.month}&day2={e.day}&tz=America%2FChicago"
    "&format=onlycomma&latlon=yes&missing=null&trace=T&report_type=3&report_type=4"
)
MM_PER_INCH = 25.4


@dataclass(frozen=True)
class Report:
    local: dt.datetime
    wxcodes: str
    precip_mm: float | None  # None when the report carries no hourly amount


def fetch_iem_csv(station: str, start: dt.date, end: dt.date) -> bytes:
    url = IEM_URL.format(station=station, s=start, e=end + dt.timedelta(days=1))
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def parse_iem_csv(raw: bytes | str) -> list[Report]:
    text = raw.decode() if isinstance(raw, bytes) else raw
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        amount = row.get("p01i", "null")
        if amount in ("null", ""):
            precip = None
        elif amount == "T":
            precip = 0.0  # trace
        else:
            precip = float(amount) * MM_PER_INCH
        wx = row.get("wxcodes", "null")
        out.append(
            Report(
                local=dt.datetime.strptime(row["valid"], "%Y-%m-%d %H:%M"),
                wxcodes="" if wx == "null" else wx,
                precip_mm=precip,
            )
        )
    return out


def load_reports(path: Path) -> list[Report]:
    return parse_iem_csv(path.read_bytes())


def lost_reasons(reports: list[Report], rule: WeatherRule) -> dict[dt.date, list[str]]:
    """Dates whose working hours hit the rule, with the reasons found."""
    out: dict[dt.date, set[str]] = {}
    for r in reports:
        if not (rule.work_start_hour <= r.local.hour < rule.work_end_hour):
            continue
        reasons = out.setdefault(r.local.date(), set())
        if rule.thunder and "TS" in r.wxcodes:
            reasons.add("thunderstorm")
        if r.precip_mm is not None and r.precip_mm >= rule.heavy_rain_mm_per_h:
            reasons.add("heavy rain")
    return {d: sorted(v) for d, v in sorted(out.items()) if v}
