"""TEMPORARY stand-in for Lane A's app.data.load. Delete once A-01 merges.

Reads data/demo/<id>/ into contract models with no input checks.
"""

import csv
import json
import os
from pathlib import Path

import yaml

from app.contracts.hashing import scenario_hash
from app.contracts.models import (
    Cluster,
    CrewDay,
    InventoryReceipt,
    PlannedInstall,
    Scenario,
    ScenarioConfig,
    Site,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_DIR = Path(os.environ.get("DEMO_DIR", REPO_ROOT / "data" / "demo"))


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _split(value: str) -> list[str]:
    return sorted(v.strip() for v in value.split(";") if v.strip())


def _point(geometry: dict) -> tuple[float, float]:
    if geometry["type"] == "Point":
        lon, lat = geometry["coordinates"][:2]
        return float(lon), float(lat)
    ring = geometry["coordinates"][0]
    return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)


def scenario_ids() -> list[str]:
    return sorted(p.name for p in DEMO_DIR.iterdir() if (p / "scenario.yaml").exists())


def load_scenario(scenario_id: str) -> Scenario:
    root = DEMO_DIR / scenario_id
    raw = yaml.safe_load((root / "scenario.yaml").read_text(encoding="utf-8"))
    travel = raw.pop("travel_allowance_min")
    points = {
        f["properties"]["site_id"]: _point(f["geometry"])
        for f in json.loads((root / "sites.geojson").read_text("utf-8"))["features"]
    }
    sites = []
    for row in _rows(root / "sites.csv"):
        lon, lat = points[row["site_id"]]
        row = {**row, "profile_id": row.get("profile_id") or None, "lon": lon, "lat": lat}
        sites.append(Site.model_validate(row))
    clusters = [
        Cluster(
            cluster_id=f["properties"]["cluster_id"],
            name=f["properties"]["name"],
            travel_allowance_min=travel[f["properties"]["cluster_id"]],
            outline=[tuple(p[:2]) for p in f["geometry"]["coordinates"][0]],
        )
        for f in json.loads((root / "clusters.geojson").read_text("utf-8"))["features"]
    ]
    crew_days = [
        CrewDay.model_validate(
            {**r, "skills": _split(r["skills"]), "allowed_clusters": _split(r["allowed_clusters"])}
        )
        for r in _rows(root / "crew_days.csv")
    ]
    scenario = Scenario(
        scenario_id=scenario_id,
        scenario_hash="",
        config=ScenarioConfig.model_validate(raw),
        clusters=clusters,
        sites=sites,
        crew_days=crew_days,
        inventory=[InventoryReceipt.model_validate(r) for r in _rows(root / "inventory.csv")],
        current_plan=[
            PlannedInstall.model_validate({**r, "locked": r["locked"].strip().lower() == "true"})
            for r in _rows(root / "current_plan.csv")
        ],
    )
    return scenario.model_copy(update={"scenario_hash": scenario_hash(scenario)})
