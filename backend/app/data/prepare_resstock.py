"""Prepare one explicitly modeled AMY 2018 ResStock load archetype.

Published timestamps are interval-ending fixed EST (UTC-5), including summer;
see https://natlabrockies.github.io/ResStock.github.io/docs/FAQ.html. Convert kWh
per quarter hour to kW, and require exact alignment with the prepared prices.
"""

import argparse
import csv
import datetime as dt
from pathlib import Path

import pandas as pd
import yaml

from app.data.manifest import build_manifest, refresh_manifest, write_manifest
from app.data.time_series import validate_energy_series

SOURCE_URL = (
    "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/"
    "end-use-load-profiles-for-us-building-stock/2025/resstock_amy2018_release_1/"
    "timeseries_individual_buildings/by_state/upgrade=0/state=TX/100-0.parquet"
)
ENERGY_COLUMN = "out.electricity.total.energy_consumption..kwh"
PROFILE_ID = "resstock-2025-1-amy2018-tx-100"


def normalize_loads(frame, *, start, end, profile_id=PROFILE_ID):
    if not {"timestamp", ENERGY_COLUMN} <= set(frame.columns):
        raise ValueError("ResStock source needs timestamp and total electricity kWh")
    timestamps = pd.to_datetime(frame.timestamp)
    if timestamps.dt.tz is not None:
        raise ValueError(
            "Expected the published ResStock naive fixed-EST interval-ending timestamps"
        )
    timestamps = timestamps.dt.tz_localize(dt.timezone(dt.timedelta(hours=-5))).dt.tz_convert("UTC")
    prepared = pd.DataFrame(
        {
            "timestamp_utc": timestamps - pd.Timedelta(minutes=15),
            "interval_hours": 0.25,
            "profile_id": profile_id,
            "load_kw": pd.to_numeric(frame[ENERGY_COLUMN]) / 0.25,
        }
    )
    prepared = validate_energy_series(prepared, "load_kw", start, end)
    if (prepared.load_kw < 0).any():
        raise ValueError("Demand must be nonnegative; do not use a net-export series")
    return prepared


def prepare_resstock(
    source: Path,
    scenario_dir: Path,
    *,
    source_url=SOURCE_URL,
    profile_id=PROFILE_ID,
    retrieved_at=None,
    manifest_dir=None,
):
    scenario_dir = Path(scenario_dir)
    config_path = scenario_dir / "scenario.yaml"
    config = yaml.safe_load(config_path.read_text())
    prices = pd.read_parquet(scenario_dir / "prices.parquet")
    # One archetype can be reused across zones only with identical interval boundaries.
    first_zone = prices[prices.load_zone == prices.load_zone.iloc[0]].sort_values("timestamp_utc")
    start = first_zone.timestamp_utc.iloc[0]
    end = first_zone.timestamp_utc.iloc[-1] + pd.Timedelta(hours=first_zone.interval_hours.iloc[-1])
    source = Path(source)
    raw = pd.read_parquet(source, columns=["timestamp", ENERGY_COLUMN])
    prepared = normalize_loads(raw, start=start, end=end, profile_id=profile_id)
    if not first_zone.timestamp_utc.reset_index(drop=True).equals(
        prepared.timestamp_utc
    ) or not first_zone.interval_hours.reset_index(drop=True).equals(prepared.interval_hours):
        raise ValueError("Load and price intervals do not match exactly")
    output = scenario_dir / "loads.parquet"
    prepared.to_parquet(output, index=False)
    manifest = build_manifest(
        output,
        dataset_id="resstock_amy2018_tx_100",
        kind="modeled",
        row_count=len(prepared),
        fields={
            "timestamp_utc": "derived",
            "interval_hours": "derived",
            "profile_id": "modeled",
            "load_kw": "modeled",
        },
        source_url=source_url,
        release="ResStock 2025 release 1; AMY 2018; Texas baseline building model 100",
        retrieved_at=retrieved_at or dt.datetime.fromtimestamp(source.stat().st_mtime, dt.UTC),
        covered_start=start.tz_convert(config["timezone"]).date(),
        covered_end=(end - pd.Timedelta(seconds=1)).tz_convert(config["timezone"]).date(),
        transformation="Fixed EST interval ends to UTC starts; quarter-hour kWh divided by 0.25 "
        "to kW. One Texas archetype assigned to all synthetic sites for sensitivity; "
        "not measured household demand. No gaps filled.",
        license_notes="ResStock license from the AWS public data registry; retained in "
        "data/LICENSE_RESSTOCK.md. Source model unmodified; data subset and units derived.",
    )
    write_manifest(manifest, manifest_dir)
    sites_path = scenario_dir / "sites.csv"
    with sites_path.open(newline="") as f:
        sites = list(csv.DictReader(f))
    for site in sites:
        site["profile_id"] = profile_id
    with sites_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(sites[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(sites)
    refresh_manifest(
        sites_path,
        scenario_dir.name + "_sites_csv",
        manifest_dir,
        field_kinds={"profile_id": "modeled"},
    )
    config_path = scenario_dir / "scenario.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["provenance"] = [
        p
        for p in config["provenance"]
        if p["input"] not in ("loads.parquet", "sites.csv:profile_id")
    ]
    for field in ("loads.parquet", "sites.csv:profile_id"):
        config["provenance"].append(
            dict(input=field, kind="modeled", source=source_url, manifest_id=manifest.dataset_id)
        )
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    refresh_manifest(config_path, scenario_dir.name + "_scenario_yaml", manifest_dir)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--scenario-dir", type=Path, required=True)
    args = parser.parse_args()
    print(prepare_resstock(args.input, args.scenario_dir).model_dump_json(indent=2))
