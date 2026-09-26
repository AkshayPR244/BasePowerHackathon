from app.data import load as loader
from app.data.generate_standard import generate_standard


def test_standard_reproducible_and_loadable(tmp_path, monkeypatch):
    first, second = tmp_path / "one" / "standard", tmp_path / "two" / "standard"
    generate_standard(first, manifest_dir=tmp_path / "m1")
    generate_standard(second, manifest_dir=tmp_path / "m2")
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {
        p.name: p.read_bytes() for p in second.iterdir()
    }
    assert {p.name: p.read_bytes() for p in (tmp_path / "m1").iterdir()} == {
        p.name: p.read_bytes() for p in (tmp_path / "m2").iterdir()
    }
    monkeypatch.setattr(loader, "DATA_ROOT", first.parent)
    scenario = loader.load_scenario("standard")
    assert len(scenario.sites) == 30
    assert len(scenario.clusters) == 3
    assert len({c.crew_id for c in scenario.crew_days}) == 3
    assert len({c.date for c in scenario.crew_days}) == 10
    assert scenario.config.synthetic
    assert scenario.config.provenance[0].kind == "synthetic"
