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
