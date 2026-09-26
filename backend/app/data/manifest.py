"""Content-hashed manifests for prepared, redistributable data products."""

import datetime as dt
import hashlib
from pathlib import Path

from app.contracts.enums import DataKind
from app.contracts.models import Manifest

MANIFEST_ROOT = Path(__file__).resolve().parents[3] / "data/manifests"


def build_manifest(
    path: Path,
    *,
    dataset_id: str,
    kind: str,
    row_count: int,
    fields: dict,
    transformation: str,
    source_url=None,
    release=None,
    retrieved_at=None,
    covered_start=None,
    covered_end=None,
    license_notes="Synthetic benchmark data; repository MIT license.",
) -> Manifest:
    if row_count < 0:
        raise ValueError("Row count must be nonnegative")
    if retrieved_at is not None:
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise ValueError("Retrieval timestamp must be timezone-aware")
        retrieved_at = retrieved_at.astimezone(dt.UTC)
    if kind == "observed" and (not source_url or retrieved_at is None):
        raise ValueError("Observed data needs its source URL and retrieval timestamp")
    return Manifest(
        dataset_id=dataset_id,
        kind=kind,
        source_url=source_url,
        release=release,
        retrieved_at=retrieved_at,
        covered_start=covered_start,
        covered_end=covered_end,
        license_notes=license_notes,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        transformation=transformation,
        row_count=row_count,
        fields=fields,
    )


def write_manifest(manifest: Manifest, directory: Path | None = None) -> Path:
    directory = MANIFEST_ROOT if directory is None else Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{manifest.dataset_id}.json"
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def refresh_manifest(
    path: Path, dataset_id: str, directory: Path | None = None, field_kinds: dict | None = None
):
    """Keep an existing prepared-file manifest current after a provenance update."""
    directory = MANIFEST_ROOT if directory is None else Path(directory)
    manifest_path = directory / f"{dataset_id}.json"
    if manifest_path.exists():
        manifest = Manifest.model_validate_json(manifest_path.read_text())
        manifest.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if field_kinds:
            manifest.fields.update({k: DataKind(v) for k, v in field_kinds.items()})
        write_manifest(manifest, directory)
