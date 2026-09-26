"""Read prepared local scenarios; never download or modify data on load."""

import csv
import json
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.contracts.hashing import scenario_hash
from app.contracts.models import InputIssue, Scenario, ScenarioSummary

DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "demo"


class ScenarioLoadError(ValueError):
    def __init__(self, issues: list[InputIssue]):
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues))


def scenario_ids() -> list[str]:
    return sorted(p.name for p in DATA_ROOT.iterdir() if (p / "scenario.yaml").is_file())


def summarize(scenario: Scenario) -> ScenarioSummary:
    return ScenarioSummary(
        scenario_id=scenario.scenario_id,
        name=scenario.config.name,
        scenario_hash=scenario.scenario_hash,
        planning_start=scenario.config.planning_start,
        planning_end=scenario.config.planning_end,
        n_sites=len(scenario.sites),
        n_crews=len({c.crew_id for c in scenario.crew_days}),
        n_crew_days=len(scenario.crew_days),
        synthetic=scenario.config.synthetic,
    )


def _csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _features(path: Path, key: str) -> dict:
    collection = json.loads(path.read_text())
    if collection.get("type") != "FeatureCollection":
        raise ValueError(f"{path.name}: expected a FeatureCollection")
    result = {}
    for row, feature in enumerate(collection["features"], 1):
        identifier = feature["properties"][key]
        if identifier in result:
            raise ScenarioLoadError(
                [
                    InputIssue(
                        code="DUPLICATE_ID",
                        file=path.name,
                        row=row,
                        message=f"Duplicate geometry ID {identifier}",
                    )
                ]
            )
        result[identifier] = feature
    return result


def _point(feature: dict) -> tuple[float, float]:
    geometry = feature["geometry"]
    if geometry["type"] == "Point":
        lon, lat = geometry["coordinates"]
        return lon, lat
    if geometry["type"] == "Polygon":
        ring = geometry["coordinates"][0]
        vertices = ring[:-1] if ring[0] == ring[-1] else ring
        return tuple(sum(p[i] for p in vertices) / len(vertices) for i in (0, 1))
    raise ValueError("Site geometry must be a Point or Polygon")


def load_scenario(scenario_id: str) -> Scenario:
    from app.data.validate_inputs import validate_inputs

    if not re.fullmatch(r"[A-Za-z0-9_-]+", scenario_id):
        raise ScenarioLoadError([InputIssue(code="BAD_VALUE", message="Invalid scenario ID")])
    folder = DATA_ROOT / scenario_id
    filename = "scenario.yaml"
    try:
        config = yaml.safe_load((folder / filename).read_text())
        travel = config.pop("travel_allowance_min")
        filename = "clusters.geojson"
        clusters = []
        for cid, f in _features(folder / filename, "cluster_id").items():
            if f["geometry"]["type"] != "Polygon":
                raise ValueError("Cluster geometry must be a Polygon")
            clusters.append(
                dict(
                    cluster_id=cid,
                    name=f["properties"]["name"],
                    outline=f["geometry"]["coordinates"][0],
                    travel_allowance_min=travel[cid],
                )
            )
        filename = "sites.geojson"
        geometries = _features(folder / filename, "site_id")
        filename = "sites.csv"
        sites = _csv(folder / filename)
        site_ids = {s["site_id"] for s in sites}
        if set(geometries) != site_ids:
            raise ScenarioLoadError(
                [
                    InputIssue(
                        code="UNKNOWN_REFERENCE",
                        file="sites.geojson",
                        message="Site table and geometry IDs differ",
                    )
                ]
            )
        for s in sites:
            s["profile_id"] = s.get("profile_id") or None
            s["lon"], s["lat"] = _point(geometries[s["site_id"]])
        filename = "visits.csv"
        if (folder / filename).exists():
            by_site = {s["site_id"]: s for s in sites}
            for v in _csv(folder / filename):
                if v["site_id"] not in by_site:
                    raise ScenarioLoadError(
                        [
                            InputIssue(
                                code="UNKNOWN_REFERENCE",
                                file=filename,
                                message=f"Visit {v['job_id']} names unknown home {v['site_id']}",
                            )
                        ]
                    )
                by_site[v.pop("site_id")].setdefault("visits", []).append(v)
        filename = "crew_days.csv"
        crews = _csv(folder / filename)
        for c in crews:
            for key in ("skills", "allowed_clusters"):
                c[key] = sorted({x.strip() for x in c[key].split(";") if x.strip()})
        filename = "inventory.csv"
        inventory = _csv(folder / filename)
        filename = "current_plan.csv"
        current = _csv(folder / filename)
        for row in current:
            row["job_id"] = row.get("job_id") or None
        filename = "scenario inputs"
        scenario = Scenario(
            scenario_id=scenario_id,
            scenario_hash="",
            config=config,
            clusters=clusters,
            sites=sites,
            crew_days=crews,
            inventory=inventory,
            current_plan=current,
        )
    except ScenarioLoadError:
        raise
    except FileNotFoundError as exc:
        raise ScenarioLoadError(
            [
                InputIssue(
                    code="MISSING_FILE", file=filename, message=f"Missing prepared file: {filename}"
                )
            ]
        ) from exc
    except ValidationError as exc:
        raise ScenarioLoadError(
            [
                InputIssue(
                    code="BAD_VALUE",
                    file=filename,
                    message=f"{'.'.join(map(str, e['loc']))}: {e['msg']}",
                )
                for e in exc.errors()
            ]
        ) from exc
    except (ValueError, KeyError, TypeError, IndexError, yaml.YAMLError) as exc:
        raise ScenarioLoadError(
            [InputIssue(code="BAD_VALUE", file=filename, message=f"Invalid {filename}: {exc}")]
        ) from exc
    issues = validate_inputs(scenario)
    if issues:
        raise ScenarioLoadError(issues)
    scenario.scenario_hash = scenario_hash(scenario)
    return scenario
