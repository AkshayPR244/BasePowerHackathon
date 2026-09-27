"""Generate the deterministic scenario suite: --all or --scenario <id>.

Operational generation never reads the frontend narrative registry. Presets contain
only typed API edits. Narratives are separately authored, static frontend metadata.
"""

import argparse
import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

import yaml

from app.data import load as loader
from app.data.generate_standard import generate_standard
from app.data.manifest import MANIFEST_ROOT, refresh_manifest
from app.data.scenario_suite import SUITE, primary_disruption

ROOT = Path(__file__).resolve().parents[3]


def generate(scenario_id, data_root=None, manifest_root=None, presets_root=None):
    data_root = Path(data_root or loader.DATA_ROOT)
    manifest_root = Path(manifest_root or MANIFEST_ROOT)
    presets_root = Path(presets_root or ROOT / "frontend/src/scenario-presets")
    entry = SUITE[scenario_id]
    source = ROOT / "data/demo/standard"
    # Build away from the discoverable demo directory; failed generation cannot break listing.
    with tempfile.TemporaryDirectory(prefix="slackline-suite-") as scratch:
        staging = Path(scratch) / scenario_id
        staging.mkdir()
        copied = []
        for name in ("prices.parquet", "loads.parquet"):
            if (source / name).exists():
                shutil.copyfile(source / name, staging / name)
                copied.append(name)
        if "prices.parquet" not in copied:
            raise ValueError("Prepare standard/prices.parquet before generating the suite")
        original_cfg = yaml.safe_load((source / "scenario.yaml").read_text())
        notes = [
            p for p in original_cfg["provenance"] if p["input"] in (*copied, "sites.csv:profile_id")
        ]
        (staging / "scenario.yaml").write_text(
            yaml.safe_dump({"provenance": notes}), encoding="utf-8", newline="\n"
        )
        local_manifests = Path(scratch) / "manifests"
        generate_standard(staging, entry.seed, local_manifests, entry.spec)
        config_path = staging / "scenario.yaml"
        cfg = yaml.safe_load(config_path.read_text())
        cfg["description"] = entry.description + " Synthetic portfolio; no real customers."
        for param in cfg["parameters"]:
            if param["name"] == "current_plan_rule":
                param.update(
                    value="strict CP-SAT",
                    derivation=(
                        "One worker, fixed seed, deterministic work limit; "
                        f"locks: {entry.spec.lock_policy}."
                    ),
                )
            if param["name"] == "deliveries" and entry.spec.inventory_receipts:
                param.update(
                    value=json.dumps(entry.spec.inventory_receipts),
                    unit="[day offset, units]",
                    derivation="Explicit incoming receipts from the suite specification.",
                )
            if param["name"] in {"install_duration", "battery_day_duration"}:
                param["derivation"] = "Seeded choice from the listed positive visit durations."
            if param["name"] == "min_gap_install_to_battery_day":
                param["derivation"] = "Minimum business-day gap required between the two visits."
            if param["name"] == "crew_mix":
                param["derivation"] = (
                    "See crew_spec parameter for explicit skills and territory restrictions."
                )
            if param["name"].startswith("weather_"):
                param["derivation"] = (
                    "Assumed sensitivity only; this suite applies explicit synthetic disruptions, "
                    "not observed weather."
                )
        for name, value in {
            "seed": entry.seed,
            "crew_spec": json.dumps([asdict(c) for c in entry.spec.crew_specs], sort_keys=True),
            "objective_policy": entry.spec.objective_policy,
            "qualification_lag": entry.spec.qualification_lag_days,
            "generator_spec": json.dumps(asdict(entry.spec), default=str, sort_keys=True),
        }.items():
            cfg["parameters"].append(
                dict(
                    name=name,
                    value=value,
                    unit="",
                    kind="assumed",
                    derivation="Explicit reproducible suite specification.",
                )
            )
        config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8", newline="\n")
        refresh_manifest(config_path, scenario_id + "_scenario_yaml", local_manifests)
        previous = loader.DATA_ROOT
        try:
            loader.DATA_ROOT = Path(scratch)
            scenario = loader.load_scenario(scenario_id)
            from app.recovery.repair import current_result

            healthy = current_result(scenario)
            if not healthy.validation.valid or healthy.objective.jobs_on_time != len(
                scenario.sites
            ):
                raise ValueError("Generated healthy schedule failed independent validation")
            edits = primary_disruption(scenario)
        finally:
            loader.DATA_ROOT = previous
        # Copy energy provenance manifests without inventing observed sources or timestamps.
        for note in notes:
            mid = note.get("manifest_id")
            if mid and (MANIFEST_ROOT / (mid + ".json")).exists():
                shutil.copyfile(MANIFEST_ROOT / (mid + ".json"), local_manifests / (mid + ".json"))
        destination = data_root / scenario_id
        destination.mkdir(parents=True, exist_ok=True)
        for path in sorted(staging.iterdir()):
            shutil.copyfile(path, destination / path.name)
        manifest_root.mkdir(parents=True, exist_ok=True)
        for path in local_manifests.iterdir():
            shutil.copyfile(path, manifest_root / path.name)
        presets_root.mkdir(parents=True, exist_ok=True)
        preset = {
            "scenario_id": scenario_id,
            "seed": entry.seed,
            "primary_disruption": [e.model_dump(mode="json") for e in edits],
            "recovery_class": entry.recovery_class,
        }
        (presets_root / f"{scenario_id}.json").write_text(
            json.dumps(preset, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        return scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--scenario", choices=sorted(SUITE))
    args = parser.parse_args()
    for name in SUITE if args.all else [args.scenario]:
        scenario = generate(name)
        print(name, scenario.scenario_hash, flush=True)


if __name__ == "__main__":
    main()
