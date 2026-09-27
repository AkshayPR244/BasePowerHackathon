"""Behavior contracts for committed synthetic cases; no hand-authored schedules."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.contracts.models import PlanRequest
from app.data import load as loader
from app.data.generate_scenarios import ROOT, generate
from app.data.scenario_suite import SUITE, primary_disruption
from app.data.validate_inputs import validate_inputs
from app.planning.edits import apply_edits, appointment_windows
from app.planning.solve import plan
from app.recovery.repair import current_result
from app.recovery.service import prepared_scenario, recover
from app.validate import validate_plan

FEASIBLE = {"optimal", "feasible"}


def checked(base, result):
    effective = apply_edits(base, result.edits).scenario
    report = validate_plan(effective, result)
    assert report.valid, report.issues
    assert result.validation.checked and result.validation.valid
    # Appointment windows are edit-level constraints, outside frozen Scenario.
    windows = appointment_windows(result.edits)
    for a in result.assignments:
        if a.job_id in windows:
            start, end = windows[a.job_id]
            assert a.date >= start and (end is None or a.date <= end)


@pytest.mark.parametrize("sid", SUITE)
def test_planning_and_recovery_behavior(sid):
    s = loader.load_scenario(sid)
    assert not validate_inputs(s)
    assert s.config.synthetic and s.config.timezone == "America/Chicago"
    current = current_result(s)
    checked(s, current)
    assert current.objective.jobs_on_time == len(s.sites)
    healthy = plan(s, PlanRequest(scenario_id=sid, revision=0))
    assert healthy.status in FEASIBLE
    assert healthy.objective.jobs_on_time == len(s.sites)
    checked(s, healthy)
    edits = primary_disruption(s)
    strict = plan(s, PlanRequest(scenario_id=sid, revision=0, edits=edits))
    checked(s, strict)
    recovery = recover(s, edits)
    options = [recovery.no_action, *recovery.options]
    # Recovery solves with the past frozen, so check options against that scenario.
    prepared = prepared_scenario(s, edits)
    for option in options:
        checked(prepared, option.result)
    incumbents = [o.result for o in options if o.status in FEASIBLE]
    expected = SUITE[sid].recovery_class
    if expected == "locked-infeasible":
        assert strict.status == "infeasible"
        assert not incumbents
        assert all(o.status == "infeasible" for o in options)
        assert all(not o.result.assignments for o in options)
        assert any("lock" in o.result.message.lower() for o in options)
    elif expected == "late-but-feasible":
        assert strict.status == "infeasible"
        assert any(
            r.objective.jobs_late > 0 and r.objective.jobs_unscheduled == 0 for r in incumbents
        )
        assert any(
            a.date > max(site.deadline for site in s.sites)
            for r in incumbents
            for a in r.assignments
        )
    else:
        assert incumbents
        assert any(
            r.objective.jobs_late == 0 and r.objective.jobs_unscheduled == 0 for r in incumbents
        )
    if sid == "balanced_small":
        assert 9 <= len(s.sites) <= 15
        assert current.objective.crew_utilization < 0.4
    if sid == "tight_feasible":
        assert 24 <= len(s.sites) <= 36
        deadline = max(site.deadline for site in s.sites)
        battery_days = [c for c in current.crew_days if c.crew_id == "BA" and c.date <= deadline]
        utilization = sum(c.onsite_min + c.travel_min for c in battery_days) / sum(
            c.available_min for c in battery_days
        )
        assert utilization > 0.85
        assert strict.status == "infeasible"
    if sid == "inventory_delay_recoverable":
        assert recovery.impact.affected_job_ids
        assert all(j.endswith("-B") for j in recovery.impact.affected_job_ids)
        assert recovery.no_action.counts.visits_moved > 0
    if sid == "two_visit_cascade":
        changed = {c.job_id for c in recovery.no_action.diff_vs_original.changes}
        assert edits[0].job_id in changed
        assert edits[0].job_id.removesuffix("-I") + "-B" in changed
        assert any(step.kind == "pushed" and step.job_ids for step in recovery.impact.cascade)
    if sid == "skill_cluster_bottleneck":
        assert all(len(c.allowed_clusters) == 1 for c in s.crew_days)
        assert len({tuple(c.skills) for c in s.crew_days}) == 2
    if sid == "value_sensitive":
        travel = plan(
            s,
            PlanRequest(
                scenario_id=sid, revision=0, edits=edits, objective_policy="deadline_travel_only"
            ),
        )
        checked(s, travel)
        assert strict.status in FEASIBLE and travel.status in FEASIBLE
        assert strict.objective.operating_value_usd > travel.objective.operating_value_usd + 0.01
        assert {(a.job_id, a.crew_id, a.date) for a in strict.assignments} != {
            (a.job_id, a.crew_id, a.date) for a in travel.assignments
        }


@pytest.mark.parametrize("sid", SUITE)
def test_same_seed_regenerates_identical_inputs_plan_and_hash(sid, tmp_path):
    before = loader.load_scenario(sid)
    generated = generate(sid, tmp_path / "demo", tmp_path / "manifests", tmp_path / "presets")
    assert before.scenario_hash == generated.scenario_hash
    assert before.current_plan == generated.current_plan
    folder = loader.DATA_ROOT / sid
    for path in folder.iterdir():
        assert path.read_bytes() == (tmp_path / "demo" / sid / path.name).read_bytes(), path.name
    expected = json.loads((ROOT / "frontend/src/scenario-presets" / f"{sid}.json").read_text())
    assert expected == json.loads((tmp_path / "presets" / f"{sid}.json").read_text())
    for path in (tmp_path / "manifests").glob(f"{sid}_*.json"):
        assert path.read_bytes() == (ROOT / "data/manifests" / path.name).read_bytes()


def test_registry_api_listing_and_provenance():
    reports_path = ROOT / "frontend/src/narratives/reports.json"
    report_bytes = reports_path.read_bytes()
    reports = json.loads(report_bytes)
    assert set(reports) == set(SUITE)
    client = TestClient(app)
    listing = client.get("/api/scenarios")
    assert listing.status_code == 200
    assert set(SUITE) <= {r["scenario_id"] for r in listing.json()}
    for sid in SUITE:
        assert reports[sid]["scenario_id"] == sid
        response = client.get(f"/api/scenarios/{sid}")
        assert response.status_code == 200
        assert "narrative" not in response.json()
        assert reports[sid]["situation"] not in response.text
        body = {
            "scenario_id": sid,
            "revision": 0,
            "disruption": [
                e.model_dump(mode="json") for e in primary_disruption(loader.load_scenario(sid))
            ],
        }
        result = client.post("/api/recovery/options", json=body)
        assert result.status_code == 200, result.text
        assert not result.json()["stub"]
        assert result.json()["scenario_hash"]
        for path in (loader.DATA_ROOT / sid).iterdir():
            if path.suffix == ".parquet":
                assert path.read_bytes() == (loader.DATA_ROOT / "standard" / path.name).read_bytes()
            else:
                manifest = json.loads(
                    (
                        ROOT
                        / "data/manifests"
                        / (sid + "_" + path.name.replace(".", "_") + ".json")
                    ).read_text()
                )
                assert manifest["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert reports_path.read_bytes() == report_bytes
