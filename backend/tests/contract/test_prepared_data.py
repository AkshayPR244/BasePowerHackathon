import hashlib
from pathlib import Path

import pandas as pd

from app.contracts.models import Manifest
from app.data import load_scenario

ROOT = Path(__file__).resolve().parents[3]


def test_bundled_manifest_hashes_and_provenance():
    folder = ROOT / "data/demo/standard"
    for filename in (
        "scenario.yaml",
        "sites.csv",
        "sites.geojson",
        "clusters.geojson",
        "crew_days.csv",
        "inventory.csv",
        "current_plan.csv",
        "prices.parquet",
        "loads.parquet",
    ):
        dataset_id = {
            "prices.parquet": "ercot_np6_785_2018",
            "loads.parquet": "resstock_amy2018_tx_100",
        }.get(filename, "standard_" + filename.replace(".", "_"))
        manifest = Manifest.model_validate_json(
            (ROOT / f"data/manifests/{dataset_id}.json").read_text()
        )
        assert manifest.sha256 == hashlib.sha256((folder / filename).read_bytes()).hexdigest()
    s = load_scenario("standard")
    assert s.config.synthetic
    assert {p.kind for p in s.config.provenance} == {"synthetic", "observed", "modeled"}
    prices = pd.read_parquet(folder / "prices.parquet")
    loads = pd.read_parquet(folder / "loads.parquet")
    assert len(prices) == len(loads) == 5376
    assert prices.timestamp_utc.equals(loads.timestamp_utc)
    assert prices.interval_hours.equals(loads.interval_hours)
