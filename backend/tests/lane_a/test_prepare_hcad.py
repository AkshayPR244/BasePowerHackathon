import datetime as dt
import json
from urllib.parse import parse_qs, urlparse

import pytest

from app.data import load as loader
from app.data.prepare_hcad import BOUNDS, anonymize, prepare_hcad, query_url


def collection(offset=0):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "OBJECTID": offset + i,
                    "STATE_CLASS": "A1",
                    "OWNER_MAILTO": "Never retain this",
                    "SITE_ADDR_1": "Never retain this",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-95.4, 29.8], [-95.39, 29.8], [-95.39, 29.81], [-95.4, 29.8]]
                    ],
                },
            }
            for i in range(10)
        ],
    }


def test_anonymization_allowlist():
    result = anonymize(collection(), "N")
    assert result == anonymize(collection(), "N")
    assert "OWNER" not in json.dumps(result)
    assert "Never retain" not in json.dumps(result)
    assert all(set(f["properties"]) == {"site_id", "cluster_id"} for f in result)


def test_bounded_query_only_requests_needed_fields():
    query = parse_qs(urlparse(query_url(BOUNDS["N"])).query)
    assert query["outFields"] == ["OBJECTID,STATE_CLASS"]
    assert query["resultRecordCount"] == ["10"]
    with pytest.raises(ValueError):
        query_url((-100, 25, -90, 35))


def test_standard_real_loads_with_no_private_properties(tmp_path, monkeypatch):
    folder = tmp_path / "standard_real"
    prepare_hcad(
        {c: collection(i * 10) for i, c in enumerate(BOUNDS)},
        output=folder,
        manifest_dir=tmp_path / "manifests",
        retrieved_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    )
    monkeypatch.setattr(loader, "DATA_ROOT", tmp_path)
    scenario = loader.load_scenario("standard_real")
    assert len(scenario.sites) == 30
    assert scenario.config.synthetic
    assert all(s.site_id.startswith("parcel-") for s in scenario.sites)
    assert "OWNER" not in (folder / "sites.geojson").read_text()
    assert (tmp_path / "manifests/hcad_parcels.json").exists()
