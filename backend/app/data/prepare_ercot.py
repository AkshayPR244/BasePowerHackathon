"""Prepare NP6-785-ER interval-start UTC prices from an explicit local archive.

Example (from backend): python -m app.data.prepare_ercot --input
../data/raw/RTMLZHBSPP_2018.zip --output ../data/demo/standard/prices.parquet
No downloads or missing-interval fills occur during preparation or app startup.
"""

import argparse
import csv
import datetime as dt
import io
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from app.contracts.models import InputIssue
from app.data.load import ScenarioLoadError
from app.data.manifest import build_manifest, refresh_manifest, write_manifest

SOURCE_URL = "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=642564849"
TZ = ZoneInfo("America/Chicago")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _xlsx_rows(content: bytes, months=None):
    """Read the archive's simple tabular XLSX without an extra Excel dependency."""
    with zipfile.ZipFile(io.BytesIO(content)) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            shared = [
                "".join(e.itertext()) for e in ET.fromstring(book.read("xl/sharedStrings.xml"))
            ]
        relationships = {
            r.attrib["Id"]: r.attrib["Target"]
            for r in ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        }
        for sheet in ET.fromstring(book.read("xl/workbook.xml")).find(NS + "sheets"):
            if months is not None and sheet.attrib["name"] not in months:
                continue
            rid = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
            target = relationships[rid]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            with book.open(target) as stream:
                headers = None
                for _, element in ET.iterparse(stream, events=("end",)):
                    if element.tag != NS + "row":
                        continue
                    cells = {}
                    for cell in element:
                        column = re.sub(r"\d", "", cell.attrib["r"])
                        value = cell.findtext(NS + "v", "")
                        if cell.attrib.get("t") == "s":
                            value = shared[int(value)]
                        elif cell.attrib.get("t") == "inlineStr":
                            value = "".join(cell.find(NS + "is").itertext())
                        cells[column] = value
                    if headers is None:
                        headers = cells
                    elif any(cells.values()):
                        yield {name: cells.get(col, "") for col, name in headers.items()}
                    element.clear()


def archive_rows(path: Path, *, months=None):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            yield from csv.DictReader(f)
    elif path.suffix.lower() == ".xlsx":
        yield from _xlsx_rows(path.read_bytes(), months)
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            found = False
            for name in sorted(archive.namelist()):
                if name.lower().endswith(".xlsx"):
                    found = True
                    yield from _xlsx_rows(archive.read(name), months)
                elif name.lower().endswith(".csv"):
                    found = True
                    yield from csv.DictReader(io.StringIO(archive.read(name).decode("utf-8-sig")))
            if not found:
                raise ValueError("Archive contains no CSV or XLSX report")
    else:
        raise ValueError("Expected a CSV, XLSX or ZIP report")


def interval_start_utc(delivery_date, hour, interval, repeated="N") -> dt.datetime:
    if isinstance(delivery_date, dt.datetime):
        date = delivery_date.date()
    elif isinstance(delivery_date, dt.date):
        date = delivery_date
    else:
        text = str(delivery_date)
        try:
            date = dt.datetime.strptime(text, "%m/%d/%Y").date()
        except ValueError:
            try:
                date = dt.date.fromisoformat(text)
            except ValueError:
                date = (dt.datetime(1899, 12, 30) + dt.timedelta(days=float(text))).date()
    h, i = float(hour), float(interval)
    if not h.is_integer() or not 1 <= h <= 24 or not i.is_integer() or not 1 <= i <= 4:
        raise ValueError("Delivery hour must be 1..24 and interval must be 1..4")
    flag = str(repeated).strip().upper()
    if flag not in ("Y", "N", "1", "0", "TRUE", "FALSE"):
        raise ValueError("Repeated Hour Flag must explicitly identify the repeated hour")
    fold = int(flag in ("Y", "1", "TRUE"))
    naive = dt.datetime.combine(date, dt.time()) + dt.timedelta(hours=h - 1, minutes=(i - 1) * 15)
    local = naive.replace(tzinfo=TZ, fold=fold)
    utc = local.astimezone(dt.UTC)
    back = utc.astimezone(TZ)
    if back.replace(tzinfo=None) != naive or back.fold != fold:
        raise ValueError("Nonexistent local time or invalid repeated-hour flag")
    return utc


def normalize_prices(rows, *, start: dt.date, end: dt.date, zones=("LZ_HOUSTON",)) -> pd.DataFrame:
    """Require every quarter hour in the inclusive local-date range, for every zone."""
    if start > end or not zones or any(not z.startswith("LZ_") for z in zones):
        raise ValueError("Require ordered dates and explicit load zones")
    records, issues = [], []
    lower = dt.datetime.combine(start, dt.time(), TZ).astimezone(dt.UTC)
    upper = dt.datetime.combine(end + dt.timedelta(days=1), dt.time(), TZ).astimezone(dt.UTC)
    for number, row in enumerate(rows, 2):
        zone = row.get("Settlement Point Name", row.get("Settlement Point"))
        if zone not in zones or row.get("Settlement Point Type", "LZ") != "LZ":
            continue
        try:
            timestamp = interval_start_utc(
                row["Delivery Date"],
                row["Delivery Hour"],
                row["Delivery Interval"],
                row["Repeated Hour Flag"],
            )
            if not lower <= timestamp < upper:
                continue
            price = float(row["Settlement Point Price"])
            if not math.isfinite(price):
                raise ValueError("Price must be finite")
            records.append(
                dict(
                    timestamp_utc=timestamp,
                    interval_hours=0.25,
                    load_zone=zone,
                    price_usd_mwh=price,
                )
            )
        except (ValueError, KeyError, OverflowError) as exc:
            issues.append(InputIssue(code="BAD_VALUE", file="prices", row=number, message=str(exc)))
    if issues:
        raise ScenarioLoadError(issues)
    frame = pd.DataFrame(
        records, columns=["timestamp_utc", "interval_hours", "load_zone", "price_usd_mwh"]
    )
    frame["timestamp_utc"] = pd.to_datetime(frame.timestamp_utc, utc=True)
    if frame.duplicated(["load_zone", "timestamp_utc"]).any():
        raise ScenarioLoadError(
            [InputIssue(code="DUPLICATE_ID", message="Duplicate zone/interval")]
        )
    expected = pd.date_range(lower, upper, freq="15min", inclusive="left")
    for zone in zones:
        actual = pd.DatetimeIndex(frame.loc[frame.load_zone == zone, "timestamp_utc"])
        missing = expected.difference(actual)
        if len(missing):
            issues.append(
                InputIssue(
                    code="MISSING_INTERVAL",
                    file="prices",
                    message=f"{zone}: {len(missing)} missing intervals; first {missing[0]}",
                )
            )
    if issues:
        raise ScenarioLoadError(issues)
    return frame.sort_values(["load_zone", "timestamp_utc"]).reset_index(drop=True)


def prepare_ercot(
    source: Path,
    output: Path,
    *,
    start=dt.date(2018, 6, 4),
    end=dt.date(2018, 7, 29),
    zones=("LZ_HOUSTON",),
    source_url=SOURCE_URL,
    retrieved_at=None,
    manifest_dir=None,
):
    months = {(start + dt.timedelta(days=i)).strftime("%b") for i in range((end - start).days + 1)}
    frame = normalize_prices(archive_rows(source, months=months), start=start, end=end, zones=zones)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    manifest = build_manifest(
        output,
        dataset_id="ercot_np6_785_2018",
        kind="observed",
        source_url=source_url,
        release="NP6-785-ER RTMLZHBSPP_2018; published 2019-01-01",
        retrieved_at=retrieved_at
        or dt.datetime.fromtimestamp(Path(source).stat().st_mtime, dt.UTC),
        covered_start=start,
        covered_end=end,
        row_count=len(frame),
        fields={
            "timestamp_utc": "derived",
            "interval_hours": "derived",
            "load_zone": "observed",
            "price_usd_mwh": "observed",
        },
        transformation="Select LZ type, requested zones and dates; convert Chicago "
        "times to UTC interval starts using the repeated-hour flag; reject gaps.",
        license_notes="ERCOT Terms of Use section 5 permits public raw data in compilations and "
        "analyses. Source: https://www.ercot.com/help/terms (checked 2026-09-26).",
    )
    write_manifest(manifest, manifest_dir)
    config_path = output.parent / "scenario.yaml"
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text())
        config["provenance"] = [p for p in config["provenance"] if p["input"] != "prices.parquet"]
        config["provenance"].append(
            dict(
                input="prices.parquet",
                kind="observed",
                source=source_url,
                manifest_id=manifest.dataset_id,
            )
        )
        config_path.write_text(yaml.safe_dump(config, sort_keys=False))
        refresh_manifest(config_path, output.parent.name + "_scenario_yaml", manifest_dir)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2018, 6, 4))
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date(2018, 7, 29))
    args = parser.parse_args()
    print(
        prepare_ercot(args.input, args.output, start=args.start, end=args.end).model_dump_json(
            indent=2
        )
    )
