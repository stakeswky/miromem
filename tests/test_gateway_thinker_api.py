"""Tests for the Thinker gateway router skeleton."""

from __future__ import annotations

from fastapi.testclient import TestClient

from miromem.gateway.app import app
from miromem.thinker import api as thinker_api
from miromem.thinker.jobs import InMemoryThinkerJobStore


def _client() -> TestClient:
    thinker_api._job_store = InMemoryThinkerJobStore()
    return TestClient(app)


def _create_succeeded_job() -> str:
    store = thinker_api._get_job_store()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")
    store.mark_running(job.job_id)
    store.mark_succeeded(job.job_id)
    return job.job_id


def test_create_thinker_job_returns_job_id():
    client = _client()
    response = client.post(
        "/api/v1/thinker/jobs",
        json={
            "mode": "topic_only",
            "research_direction": "Fed outlook",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"]
    assert body["status"] == "created"


def test_get_thinker_job_returns_created_status():
    client = _client()
    create_response = client.post(
        "/api/v1/thinker/jobs",
        json={
            "mode": "topic_only",
            "research_direction": "Fed outlook",
        },
    )
    job_id = create_response.json()["job_id"]

    response = client.get(f"/api/v1/thinker/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job_id,
        "mode": "topic_only",
        "research_direction": "Fed outlook",
        "status": "created",
        "error_code": None,
        "error_message": None,
    }


def test_missing_job_returns_404():
    client = _client()
    response = client.get("/api/v1/thinker/jobs/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Thinker job not found"}


def test_materialize_returns_placeholder_payload():
    client = _client()
    job_id = _create_succeeded_job()

    response = client.post(
        "/api/v1/thinker/materialize",
        json={
            "job_id": job_id,
            "adopted": {
                "expanded_topics": ["Fed", "inflation"],
                "enriched_seed_text": "edited seed",
                "suggested_simulation_prompt": "edited prompt",
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job_id,
        "status": "materialized",
        "payload": {
            "final_topics": [],
            "final_seed_text": "",
            "final_simulation_requirement": "",
        },
    }
