"""Generate the deterministic synthetic 30-job benchmark, without network access.

Run from backend: python -m app.data.generate_standard
"""

import argparse
import csv
import datetime as dt
import json
import random
from pathlib import Path

import yaml

from app.data.load import DATA_ROOT
from app.data.manifest import build_manifest, write_manifest


def _csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _geojson(path, features):
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=2, sort_keys=True)
        + "\n"
    )


def generate_standard(
    output: Path | None = None, seed: int = 42, manifest_dir: Path | None = None
) -> Path:
    output = DATA_ROOT / "standard" if output is None else Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    start = dt.date(2018, 6, 4)
    days = [
        start + dt.timedelta(days=i)
        for i in range(14)
        if (start + dt.timedelta(days=i)).weekday() < 5
    ]
    cfg = yaml.safe_load((DATA_ROOT / "tiny/scenario.yaml").read_text())
    cfg.update(
        name="Standard synthetic recovery benchmark",
        description="30 synthetic jobs, 3 clusters, 3 crews and 10 working days.",
        planning_end=days[-1],
        random_seed=seed,
        unscheduled_penalty_days=30,
        solve_time_limit_s=15,
        travel_allowance_min={"N": 60, "S": 45, "W": 50},
        provenance=[
            {
                "input": "all operational and geometry files",
                "kind": "synthetic",
                "source": f"Seeded benchmark generator v1, seed {seed}. Not customers.",
            }
        ],
    )
    (output / "scenario.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    centers = {"N": (-95.40, 29.81), "S": (-95.37, 29.68), "W": (-95.49, 29.75)}
    clusters = []
    for cid, (lon, lat) in centers.items():
        ring = [
            [round(lon + x, 6), round(lat + y, 6)]
            for x, y in [
                (-0.015, -0.015),
                (0.015, -0.015),
                (0.015, 0.015),
                (-0.015, 0.015),
                (-0.015, -0.015),
            ]
        ]
        clusters.append(
            {
                "type": "Feature",
                "properties": {"cluster_id": cid, "name": cid},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    _geojson(output / "clusters.geojson", clusters)
    sites, geometry, plan = [], [], []
    for i in range(30):
        cluster = list(centers)[i % 3]
        day = i // 3
        sid = f"{cluster}-{day + 1:02d}"
        sites.append(
            dict(
                site_id=sid,
                cluster_id=cluster,
                program_id="P1",
                ready_date=days[max(0, day - rng.randint(0, 2))],
                deadline=days[min(9, day + rng.randint(0, 2))],
                duration_min=rng.choice([180, 210, 240]),
                required_skill="install",
                configuration_id="B13",
                load_zone="LZ_HOUSTON",
                profile_id="",
            )
        )
        lon, lat = centers[cluster]
        point = [round(lon + rng.uniform(-0.01, 0.01), 6), round(lat + rng.uniform(-0.01, 0.01), 6)]
        geometry.append(
            {
                "type": "Feature",
                "properties": {"site_id": sid},
                "geometry": {"type": "Point", "coordinates": point},
            }
        )
        plan.append(
            dict(
                site_id=sid,
                crew_id="ABC"[i % 3],
                date=days[day],
                locked="true" if day == 0 else "false",
            )
        )
    _csv(output / "sites.csv", sites)
    _geojson(output / "sites.geojson", geometry)
    _csv(output / "current_plan.csv", plan)
    crews = [
        dict(crew_id=c, date=day, available_min=480, skills="install", allowed_clusters="N;S;W")
        for c in "ABC"
        for day in days
    ]
    _csv(output / "crew_days.csv", crews)
    receipts = [
        dict(configuration_id="B13", available_date=days[d], quantity=q)
        for d, q in [(0, 9), (3, 9), (6, 12)]
    ]
    _csv(output / "inventory.csv", receipts)
    counts = {
        "scenario.yaml": 1,
        "sites.csv": 30,
        "sites.geojson": 30,
        "clusters.geojson": 3,
        "crew_days.csv": 30,
        "inventory.csv": 3,
        "current_plan.csv": 30,
    }
    for name, count in counts.items():
        path = output / name
        if path.suffix == ".csv":
            fields = {k: "synthetic" for k in path.read_text().splitlines()[0].split(",")}
        else:
            fields = {"geometry" if path.suffix == ".geojson" else "config": "synthetic"}
        write_manifest(
            build_manifest(
                path,
                dataset_id=output.name + "_" + name.replace(".", "_"),
                kind="synthetic",
                row_count=count,
                fields=fields,
                release=f"generator-v1-seed-{seed}",
                covered_start=start,
                covered_end=days[-1],
                transformation="Seeded synthetic inputs; no real customers.",
            ),
            manifest_dir,
        )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(generate_standard(args.output, args.seed))
