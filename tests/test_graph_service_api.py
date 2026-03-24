"""API tests for the internal graph-service build and job routes."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace

from fastapi.testclient import TestClient

import miromem.graph_service.workers.build_worker as build_worker_module
from miromem.graph_service.app import create_app


class _FakeGraphiti:
    def __init__(self, *, started_event: Event | None = None, release_event: Event | None = None) -> None:
        self.bulk_calls: list[dict[str, object]] = []
        self.indices_built = False
        self.started_event = started_event
        self.release_event = release_event

    async def build_indices_and_constraints(self, delete_existing: bool = False) -> None:
        self.indices_built = True

    async def add_episode_bulk(
        self,
        bulk_episodes,
        *,
        group_id,
        entity_types,
        edge_types,
        edge_type_map,
    ):
        self.bulk_calls.append(
            {
                "bulk_episodes": bulk_episodes,
                "group_id": group_id,
                "entity_types": entity_types,
                "edge_types": edge_types,
                "edge_type_map": edge_type_map,
            }
        )
        if self.started_event is not None:
            self.started_event.set()
        if self.release_event is not None:
            self.release_event.wait(timeout=5)
        return SimpleNamespace(
            nodes=[{"uuid": "node-1"}, {"uuid": "node-2"}],
            edges=[{"uuid": "edge-1"}],
        )


def _wait_for_job_completion(client: TestClient, job_id: str, timeout_seconds: float = 2.0) -> dict[str, object]:
    deadline = monotonic() + timeout_seconds
    last_payload: dict[str, object] | None = None

    while monotonic() < deadline:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if payload["status"] == "completed":
            return payload
        sleep(0.02)

    raise AssertionError(f"Job {job_id} did not complete in time. Last payload: {last_payload}")


def test_build_graph_returns_queued_before_job_completion_and_updates_job_payload(monkeypatch):
    started_event = Event()
    release_event = Event()
    fake_graphiti = _FakeGraphiti(started_event=started_event, release_event=release_event)
    captured_ontology: dict[str, object] = {}

    def fake_compile_ontology(ontology):
        captured_ontology["ontology"] = ontology
        return SimpleNamespace(
            entity_types={"Person": object},
            edge_types={"KNOWS": object},
            edge_type_map={("Person", "Person"): ["KNOWS"]},
        )

    monkeypatch.setattr(build_worker_module, "build_graphiti", lambda settings: fake_graphiti)
    monkeypatch.setattr(build_worker_module, "compile_ontology", fake_compile_ontology)

    app = create_app()
    with TestClient(app) as client:
        request_json = {
            "project_id": "proj_demo",
            "graph_name": "Demo",
            "document_text": "Gavin Newsom is running. He is campaigning in California.",
            "chunk_size": 24,
            "chunk_overlap": 6,
            "ontology": {
                "entity_types": [{"name": "Person", "attributes": []}],
                "edge_types": [
                    {
                        "name": "KNOWS",
                        "attributes": [],
                        "source_targets": [{"source": "Person", "target": "Person"}],
                    }
                ],
            },
        }
        response_holder: dict[str, object] = {}

        def issue_request() -> None:
            response_holder["response"] = client.post("/graphs/mirofish_demo/build", json=request_json)

        request_thread = Thread(target=issue_request)
        request_thread.start()

        assert started_event.wait(timeout=1.0), "Build worker never started processing the queued job"
        request_thread.join(timeout=0.3)
        assert not request_thread.is_alive(), "Build route blocked until worker completion instead of returning queued"

        response = response_holder["response"]
        assert response.status_code == 202
        assert response.json()["status"] == "queued"
        job_id = response.json()["job_id"]

        job_response = client.get(f"/jobs/{job_id}")
        assert job_response.status_code == 200
        initial_payload = job_response.json()
        assert initial_payload["job_id"] == job_id
        assert initial_payload["job_type"] == "build_graph"
        assert initial_payload["graph_id"] == "mirofish_demo"
        assert initial_payload["status"] in {"queued", "running"}

        release_event.set()
        payload = _wait_for_job_completion(client, job_id)

        assert payload["metadata"]["project_id"] == "proj_demo"
        assert payload["metadata"]["chunk_count"] == 4
        assert payload["metadata"]["node_count"] == 2
        assert payload["metadata"]["edge_count"] == 1
        assert payload["metadata"]["last_built_at"]

        stored_metadata = app.state.graph_metadata_store.get_metadata("mirofish_demo")
        assert stored_metadata is not None
        assert stored_metadata.chunk_count == 4
        assert stored_metadata.node_count == 2
        assert stored_metadata.edge_count == 1
        assert stored_metadata.last_built_at == datetime.fromisoformat(payload["metadata"]["last_built_at"])

        assert captured_ontology["ontology"]["entity_types"][0]["name"] == "Person"
        assert fake_graphiti.indices_built is True
        assert len(fake_graphiti.bulk_calls) == 1
        assert fake_graphiti.bulk_calls[0]["group_id"] == "mirofish_demo"
        assert len(fake_graphiti.bulk_calls[0]["bulk_episodes"]) == 4


def test_job_status_endpoint_returns_404_for_missing_job():
    with TestClient(create_app()) as client:
        response = client.get("/jobs/missing")

        assert response.status_code == 404
        assert response.json() == {"detail": "Unknown graph job: missing"}


def test_health_routes_exist():
    with TestClient(create_app()) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

        assert live.status_code == 200
        assert ready.status_code == 200
        assert live.json()["status"] == "ok"
        assert ready.json()["status"] == "ok"
