import datetime as dt
import shutil

import pytest

from app.data import ScenarioLoadError, load_scenario
from app.data import load as loader
from app.data.validate_inputs import validate_inputs


def codes(s):
    return {i.code for i in validate_inputs(s)}


def test_duplicate_ids(scenario):
    scenario.sites.append(scenario.sites[0])
    scenario.crew_days.append(scenario.crew_days[0])
    assert "DUPLICATE_ID" in codes(scenario)


def test_unknown_references(scenario):
    scenario.sites[0].cluster_id = "missing"
    scenario.inventory[0].configuration_id = "missing"
    assert "UNKNOWN_REFERENCE" in codes(scenario)


def test_date_order(scenario):
    scenario.config.evaluation_end = dt.date(2017, 1, 1)
    assert "DATE_ORDER" in codes(scenario)


def test_duplicate_planned_install(scenario):
    scenario.current_plan.append(scenario.current_plan[1])
    assert "DUPLICATE_PLANNED_INSTALL" in codes(scenario)


@pytest.mark.parametrize(
    "mutation", ["missing_crew", "capacity", "inventory", "duplicate", "ready"]
)
def test_contradictory_locks(scenario, mutation):
    if mutation == "missing_crew":
        scenario.current_plan[0].crew_id = "missing"
    elif mutation == "capacity":
        scenario.crew_days[1].available_min = 1
    elif mutation == "inventory":
        scenario.inventory = []
    elif mutation == "duplicate":
        scenario.current_plan.append(scenario.current_plan[0].model_copy())
    else:
        scenario.sites[0].ready_date = dt.date(2018, 6, 6)
    assert "CONTRADICTORY_LOCKS" in codes(scenario)
    assert scenario.current_plan[0].locked


@pytest.fixture
def copied_tiny(tmp_path, monkeypatch):
    dest = tmp_path / "tiny"
    shutil.copytree(loader.DATA_ROOT / "tiny", dest)
    monkeypatch.setattr(loader, "DATA_ROOT", tmp_path)
    return dest


def test_ready_after_deadline(copied_tiny):
    p = copied_tiny / "sites.csv"
    p.write_text(
        p.read_text().replace("N-02,N,P1,2018-06-04,2018-06-04", "N-02,N,P1,2018-06-05,2018-06-04")
    )
    scenario = load_scenario("tiny")
    assert scenario.sites[1].ready_date > scenario.sites[1].deadline


@pytest.mark.parametrize("replacement", ["-180", "nan", "inf", "nonsense"])
def test_bad_values_structured(copied_tiny, replacement):
    p = copied_tiny / "sites.csv"
    p.write_text(p.read_text().replace(",180,", f",{replacement},", 1))
    with pytest.raises(ScenarioLoadError) as error:
        load_scenario("tiny")
    assert error.value.issues[0].code == "BAD_VALUE"


def test_bad_efficiency(scenario):
    scenario.config.batteries[0].eta_discharge = 0
    assert "BAD_VALUE" in codes(scenario)


def test_geometry_ids_must_match(copied_tiny):
    p = copied_tiny / "sites.geojson"
    p.write_text(p.read_text().replace('"N-01"', '"missing"'))
    with pytest.raises(ScenarioLoadError) as error:
        load_scenario("tiny")
    assert error.value.issues[0].code == "UNKNOWN_REFERENCE"


@pytest.mark.parametrize("field,value", [("available_min", -1), ("available_min", float("inf"))])
def test_mutated_numeric_values_still_checked(scenario, field, value):
    setattr(scenario.crew_days[0], field, value)
    assert "BAD_VALUE" in codes(scenario)


def test_blank_job_id_row_duplicates_the_battery_day_row():
    s = load_scenario("tiny_two_visit")
    extra = s.current_plan[0].model_copy(
        update={"site_id": "H2", "job_id": None, "locked": False, "crew_id": "B"}
    )
    s.current_plan.append(extra)
    assert "DUPLICATE_PLANNED_INSTALL" in codes(s)
