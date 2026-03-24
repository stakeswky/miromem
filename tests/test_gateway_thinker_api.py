"""Tests for the Thinker gateway router skeleton."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from miromem.gateway.app import app
from miromem.thinker import api as thinker_api
from miromem.thinker.jobs import InMemoryThinkerJobStore
from miromem.thinker.models import ThinkerResult


def _client() -> TestClient:
    thinker_api._job_store = InMemoryThinkerJobStore()
    thinker_api._orchestrator = None
    return TestClient(app)


def _disable_background_tasks(monkeypatch) -> None:
    def _close_coroutine(coro):
        coro.close()
        return object()

    monkeypatch.setattr(thinker_api.asyncio, "create_task", _close_coroutine)


def _create_succeeded_job() -> str:
    store = thinker_api._get_job_store()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")
    store.mark_running(job.job_id)
    store.mark_succeeded(
        job.job_id,
        result=ThinkerResult(
            expanded_topics=["Fed"],
            enriched_seed_text="seed",
            suggested_simulation_prompt="prompt",
        ),
    )
    return job.job_id


def _wait_for_job_status(client: TestClient, job_id: str, expected_status: str) -> dict:
    deadline = time.monotonic() + 1.0
    last_body: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/thinker/jobs/{job_id}")
        assert response.status_code == 200
        last_body = response.json()
        if last_body["status"] == expected_status:
            return last_body
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} did not reach {expected_status}: {last_body}")


def test_create_thinker_job_returns_job_id(monkeypatch):
    _disable_background_tasks(monkeypatch)
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


def test_create_thinker_job_rejects_invalid_mode():
    client = _client()
    response = client.post(
        "/api/v1/thinker/jobs",
        json={
            "mode": "unsupported",
            "research_direction": "Fed outlook",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "mode"


def test_get_thinker_job_returns_created_status(monkeypatch):
    _disable_background_tasks(monkeypatch)
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
        "result": None,
        "error_code": None,
        "error_message": None,
        "retryable": None,
        "can_continue_without_thinker": True,
    }


class _FailingOrchestrator:
    async def run(self, *, mode: str, research_direction: str, **_: object) -> ThinkerResult:
        raise RuntimeError("Thinker LLM provider is not configured: missing THINKER_LLM_API_KEY")


def test_failed_job_returns_structured_error_shape():
    client = _client()
    thinker_api._orchestrator = _FailingOrchestrator()

    response = client.post(
        "/api/v1/thinker/jobs",
        json={
            "mode": "topic_only",
            "research_direction": "Fed outlook",
        },
    )

    body = _wait_for_job_status(client, response.json()["job_id"], "failed")

    assert body == {
        "job_id": response.json()["job_id"],
        "mode": "topic_only",
        "research_direction": "Fed outlook",
        "status": "failed",
        "result": None,
        "error_code": "provider_misconfigured",
        "error_message": "Thinker LLM provider is not configured: missing THINKER_LLM_API_KEY",
        "retryable": False,
        "can_continue_without_thinker": True,
    }


def test_missing_job_returns_404():
    client = _client()
    response = client.get("/api/v1/thinker/jobs/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Thinker job not found"}


def test_materialize_returns_409_for_non_succeeded_job():
    client = _client()
    job = thinker_api._get_job_store().create_job(
        mode="topic_only",
        research_direction="Fed outlook",
    )

    response = client.post(
        "/api/v1/thinker/materialize",
        json={
            "job_id": job.job_id,
            "adopted": {
                "expanded_topics": ["Fed", "inflation"],
                "enriched_seed_text": "edited seed",
                "suggested_simulation_prompt": "edited prompt",
            },
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Thinker job is not ready to materialize"}
    assert thinker_api._get_job_store().get_job(job.job_id).status == "created"


def test_materialize_marks_job_materialized_and_echoes_adopted_fields():
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
            "final_topics": ["Fed", "inflation"],
            "final_seed_text": "edited seed",
            "final_simulation_requirement": "edited prompt",
        },
    }
    assert thinker_api._get_job_store().get_job(job_id).status == "materialized"
