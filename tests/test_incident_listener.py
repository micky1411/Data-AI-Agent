from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.testclient import TestClient

from agent.listener.app import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "incidents.sqlite3")) as test_client:
        yield test_client


def event(**overrides):
    payload = {
        "dag_id": "daily_sales_pipeline",
        "task_id": "pyspark_ingest",
        "run_id": "manual__2026-08-18T12:00:00+00:00",
        "try_number": 1,
        "logical_date": "2026-08-15T00:00:00+00:00",
        "exception": "vendor schema mismatch",
        "log_url": "http://airflow:8080/log/example",
    }
    payload.update(overrides)
    return payload


def test_failure_event_creates_incident_with_initial_transition(client):
    response = client.post("/events/airflow", json=event())

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["incident"]["state"] == "DETECTED"
    assert body["incident"]["event_count"] == 1
    assert body["incident"]["transitions"][0]["to_state"] == "DETECTED"


def test_duplicate_callback_returns_same_incident(client):
    first = client.post("/events/airflow", json=event()).json()
    second_response = client.post(
        "/events/airflow", json=event(task_id="audit_sales", exception="upstream failed")
    )
    second = second_response.json()

    assert second_response.status_code == 200
    assert second["created"] is False
    assert second["incident"]["incident_id"] == first["incident"]["incident_id"]
    assert second["incident"]["event_count"] == 2
    assert [item["task_id"] for item in second["incident"]["events"]] == [
        "pyspark_ingest", "audit_sales"
    ]
    assert len(client.get("/incidents").json()) == 1


def test_concurrent_duplicate_callbacks_are_atomic(client):
    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(lambda _: client.post("/events/airflow", json=event()), range(8)))

    assert sum(response.status_code == 201 for response in responses) == 1
    incidents = client.get("/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["event_count"] == 8


def test_state_machine_records_history_and_rejects_invalid_jump(client):
    incident_id = client.post("/events/airflow", json=event()).json()["incident"]["incident_id"]
    invalid = client.post(
        f"/incidents/{incident_id}/transitions",
        json={"state": "RESOLVED", "reason": "skipped required states"},
    )
    valid = client.post(
        f"/incidents/{incident_id}/transitions",
        json={"state": "COLLECTING", "reason": "collector started"},
    )

    assert invalid.status_code == 409
    assert valid.status_code == 200
    assert valid.json()["state"] == "COLLECTING"
    assert len(valid.json()["transitions"]) == 2


def test_payload_validation_rejects_unknown_or_missing_fields(client):
    bad = event(untrusted_extra="no")
    del bad["dag_id"]
    response = client.post("/events/airflow", json=bad)
    assert response.status_code == 422
