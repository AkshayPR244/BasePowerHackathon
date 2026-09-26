"""Bounded residential parcel preparation with an explicit property allowlist.

Run: python -m app.data.prepare_hcad --download
Observed geometry remains local until redistribution terms are established.
Operational inputs are synthetic; candidate parcels are not customers.
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from app.data.generate_standard import generate_standard
from app.data.load import DATA_ROOT, _point
from app.data.manifest import build_manifest, refresh_manifest, write_manifest

LAYER_URL = "https://mycity2.houstontx.gov/pubgis02/rest/services/PDD/HCAD_Parcels/MapServer/0"
BOUNDS = {
    "N": (-95.415, 29.795, -95.385, 29.825),
    "S": (-95.385, 29.665, -95.355, 29.695),
    "W": (-95.505, 29.735, -95.475, 29.765),
}


def query_url(bounds, limit=10):
    west, south, east, north = bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid bounding box")
    if east - west > 0.1 or north - south > 0.1 or not 1 <= limit <= 100:
        raise ValueError("Parcel query must stay bounded to a small sample")
    return (
        LAYER_URL
        + "/query?"
        + urllib.parse.urlencode(
            {
                "where": "STATE_CLASS='A1'",
                "geometry": ",".join(map(str, bounds)),
                "geometryType": "esriGeometryEnvelope",
                "inSR": 4326,
                "outSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "OBJECTID,STATE_CLASS",
                "returnGeometry": "true",
                "orderByFields": "OBJECTID",
                "resultRecordCount": limit,
                "f": "geojson",
            }
        )
    )


def anonymize(collection, cluster, *, seed=42):
    """Copy geometry and a seeded opaque ID only; never retain source properties."""
    if collection.get("type") != "FeatureCollection" or "error" in collection:
        raise ValueError("HCAD response is not a GeoJSON FeatureCollection")
    output, seen = [], set()
    for feature in collection["features"]:
        props = feature["properties"]
        if props.get("STATE_CLASS") != "A1":
            raise ValueError("Query returned an unexpected residential class")
        identifier = str(props["OBJECTID"])
        if identifier in seen:
            raise ValueError("Duplicate parcel identifier")
        seen.add(identifier)
        geometry = feature["geometry"]
        if geometry["type"] != "Polygon":
            raise ValueError("Expected polygon parcel geometry")
        _point(feature)  # Verify the geometry is usable before writing it.
        sid = "parcel-" + hashlib.sha256(f"{seed}:{identifier}".encode()).hexdigest()[:16]
        output.append(
            {
                "type": "Feature",
                "properties": {"site_id": sid, "cluster_id": cluster},
                "geometry": geometry,
            }
        )
    return sorted(output, key=lambda f: f["properties"]["site_id"])


def prepare_hcad(
    collections, *, output=None, seed=42, retrieved_at=None, manifest_dir=None, source_url=None
):
    if retrieved_at is None:
        raise ValueError("Observed parcel data requires a retrieval timestamp")
    if set(collections) != set(BOUNDS):
        raise ValueError("Supply one bounded collection for each of N, S and W")
    output = DATA_ROOT / "standard_real" if output is None else Path(output)
    features = []
    for cluster in BOUNDS:
        clean = anonymize(collections[cluster], cluster, seed=seed)
        if len(clean) < 10:
            raise ValueError(f"Need ten parcels for cluster {cluster}")
        features.extend(clean[:10])
    if len({f["properties"]["site_id"] for f in features}) != 30:
        raise ValueError("Parcel samples overlap across clusters")
    generate_standard(output, seed, manifest_dir)
    # Keep observed files local; include only the recipe and manifest in version control.
    (output / ".gitignore").write_text("*\n!.gitignore\n!README.md\n")
    (output / "README.md").write_text(
        "# Local parcel scenario\n\nGenerate with `python -m app.data.prepare_hcad --download` "
        "from backend. Geometry comes from bounded HCAD A1 queries; operations are synthetic. "
        "Source redistribution terms are not established, so generated files remain local.\n"
    )
    path = output / "sites.geojson"
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, sort_keys=True, indent=2)
        + "\n"
    )
    with (output / "sites.csv").open(newline="") as f:
        sites = list(csv.DictReader(f))
    available = {
        c: iter([f for f in features if f["properties"]["cluster_id"] == c]) for c in BOUNDS
    }
    remap = {}
    for s in sites:
        old = s["site_id"]
        s["site_id"] = next(available[s["cluster_id"]])["properties"]["site_id"]
        remap[old] = s["site_id"]
    for filename, rows in [("sites.csv", sites), ("current_plan.csv", None)]:
        if rows is None:
            with (output / filename).open(newline="") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                row["site_id"] = remap[row["site_id"]]
        with (output / filename).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        refresh_manifest(
            output / filename,
            output.name + "_" + filename.replace(".", "_"),
            manifest_dir,
            field_kinds={"site_id": "derived"},
        )
    cfg_path = output / "scenario.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg["name"] = "HCAD parcel candidates with synthetic operations"
    cfg["description"] = "Observed parcel geometry, synthetic crews and commitments; not customers."
    cfg["provenance"] = [
        {
            "input": "operational tables and cluster allowances",
            "kind": "synthetic",
            "source": f"Seeded benchmark v1, seed {seed}; not customer demand.",
        },
        {
            "input": "sites.geojson:geometry",
            "kind": "observed",
            "source": LAYER_URL,
            "manifest_id": "hcad_parcels",
        },
        {
            "input": "sites.csv:site_id",
            "kind": "derived",
            "source": "Seeded parcel identifier hash",
        },
    ]
    prices = DATA_ROOT / "standard/prices.parquet"
    if prices.exists():
        shutil.copyfile(prices, output / "prices.parquet")
        cfg["provenance"].append(
            {
                "input": "prices.parquet",
                "kind": "observed",
                "source": "ERCOT NP6-785-ER 2018",
                "manifest_id": "ercot_np6_785_2018",
            }
        )
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    refresh_manifest(cfg_path, output.name + "_scenario_yaml", manifest_dir)
    manifest = build_manifest(
        path,
        dataset_id="hcad_parcels",
        kind="observed",
        row_count=30,
        source_url=source_url or LAYER_URL,
        retrieved_at=retrieved_at,
        release="HCAD layer; bounded current snapshot",
        fields={"geometry": "observed", "site_id": "derived", "cluster_id": "assumed"},
        transformation="Three bounded A1 parcel queries, ten candidates per cluster. "
        "Seeded ID hashes; all original properties discarded.",
        license_notes="Unknown, not redistributed. Observed scenario files are local and ignored.",
    )
    write_manifest(manifest, manifest_dir)
    # Replace the generator's synthetic geometry manifest with truthful observed provenance.
    write_manifest(
        manifest.model_copy(update={"dataset_id": output.name + "_sites_geojson"}), manifest_dir
    )
    return output


def download_samples():
    raw = DATA_ROOT.parent / "raw/hcad"
    raw.mkdir(parents=True, exist_ok=True)
    collections = {}
    for cluster, bounds in BOUNDS.items():
        url = query_url(bounds)
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()
        (raw / f"{cluster}.geojson").write_bytes(content)
        collections[cluster] = json.loads(content)
    return collections


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", required=True)
    args = parser.parse_args()
    print(prepare_hcad(download_samples(), retrieved_at=dt.datetime.now(dt.UTC)))
