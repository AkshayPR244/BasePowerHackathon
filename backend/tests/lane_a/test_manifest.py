import datetime as dt
import hashlib

import pytest

from app.contracts.models import Manifest
from app.data.manifest import build_manifest, write_manifest


def test_manifest_hash_and_fields(tmp_path):
    p = tmp_path / "input.csv"
    p.write_text("value\n1\n")
    manifest = build_manifest(
        p,
        dataset_id="test",
        kind="observed",
        row_count=1,
        fields={"value": "observed"},
        transformation="Parsed one row",
        source_url="https://example.org",
        retrieved_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        release="v1",
        license_notes="Unknown, not redistributed",
    )
    path = write_manifest(manifest, tmp_path)
    assert Manifest.model_validate_json(path.read_text()) == manifest
    assert manifest.sha256 == hashlib.sha256(p.read_bytes()).hexdigest()
    p.write_text("value\n2\n")
    assert manifest.sha256 != hashlib.sha256(p.read_bytes()).hexdigest()


def test_manifest_naive_retrieval_rejected(tmp_path):
    p = tmp_path / "input"
    p.write_text("x")
    with pytest.raises(ValueError, match="timezone-aware"):
        build_manifest(
            p,
            dataset_id="bad",
            kind="observed",
            row_count=1,
            fields={},
            transformation="x",
            retrieved_at=dt.datetime(2026, 1, 1),
        )
