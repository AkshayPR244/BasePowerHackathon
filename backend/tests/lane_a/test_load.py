import pytest

from app.contracts.hashing import scenario_hash
from app.data import ScenarioLoadError, load_scenario, scenario_ids, summarize


def test_load_tiny():
    s = load_scenario("tiny")
    assert len(s.sites) == 6
    assert s.sites[0].lon == -95.412
    assert s.sites[0].profile_id is None
    assert s.crew_days[0].allowed_clusters == ["N", "S"]
    assert s.current_plan[0].locked is True
    assert s.scenario_hash == scenario_hash(s)
    assert s.scenario_hash == "34fef406b07ac6d7e2cb486e804f01766bf33b1221e00eabd13b4ced8a516281"
    assert "tiny" in scenario_ids()
    assert summarize(s).n_crews == 2


@pytest.mark.parametrize("name,code", [("missing", "MISSING_FILE"), ("../tiny", "BAD_VALUE")])
def test_load_error(name, code):
    with pytest.raises(ScenarioLoadError) as error:
        load_scenario(name)
    assert error.value.issues[0].code == code


@pytest.fixture
def copy_tiny(tmp_path, monkeypatch):
    import shutil

    from app.data import load as loader

    shutil.copytree(loader.DATA_ROOT / "tiny", tmp_path / "tiny")
    monkeypatch.setattr(loader, "DATA_ROOT", tmp_path)
    return tmp_path / "tiny"


@pytest.mark.parametrize(
    "file,text",
    [("scenario.yaml", ""), ("scenario.yaml", "[a, b]"), ("clusters.geojson", "[]")],
    ids=["empty yaml", "yaml list", "geojson list"],
)
def test_malformed_files_raise_load_errors(copy_tiny, file, text):
    (copy_tiny / file).write_text(text, encoding="utf-8")
    with pytest.raises(ScenarioLoadError) as error:
        load_scenario("tiny")
    assert error.value.issues[0].code == "BAD_VALUE"


def test_site_skill_whitespace_is_stripped(copy_tiny):
    path = copy_tiny / "sites.csv"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(",install,", ",install ,", 1), encoding="utf-8")
    assert {s.required_skill for s in load_scenario("tiny").sites} == {"install", "panel_upgrade"}
