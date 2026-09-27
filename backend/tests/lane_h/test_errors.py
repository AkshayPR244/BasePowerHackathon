"""H-01: 500 errors show a generic message and a request ID. Details stay in the server log."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.contracts.models import ApiError
from app.planning.solve import InvalidPlanError

client = TestClient(main.app, raise_server_exceptions=False)
BODY = {"scenario_id": "tiny", "revision": 0}


@pytest.mark.parametrize(
    "error,code",
    [
        (RuntimeError("secret path C:/internal/db.sqlite"), "internal_error"),
        (InvalidPlanError("Plan x failed validation: CAPACITY on crew A"), "invalid_plan"),
    ],
)
def test_500_is_generic_with_request_id(monkeypatch, caplog, error, code):
    def crash(scenario, req):
        raise error

    monkeypatch.setattr(main, "plan", crash)
    with caplog.at_level(logging.ERROR, logger="slackline.api"):
        r = client.post("/api/plans", json=BODY)
    assert r.status_code == 500
    err = ApiError.model_validate(r.json())
    request_id = r.headers["x-request-id"]
    assert err.code == code
    assert request_id in err.message
    assert str(error) not in r.text  # no internal detail reaches the client
    assert type(error).__name__ not in r.text
    logged = "\n".join(rec.getMessage() + str(rec.exc_info) for rec in caplog.records)
    assert request_id in logged and str(error) in logged  # the server keeps the details


def test_request_ids_differ(monkeypatch):
    monkeypatch.setattr(main, "plan", lambda s, r: 1 / 0)
    ids = {client.post("/api/plans", json=BODY).headers["x-request-id"] for _ in range(3)}
    assert len(ids) == 3
