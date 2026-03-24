"""API tests for the internal graph-service build and job routes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import miromem.graph_service.workers.build_worker as build_worker_module
from miromem.graph_service.app import create_app


class _FakeGraphiti:
    def __init__(self) -> None:
        self.bulk_calls: list[dict[str, object]] = []
        self.indices_built = False

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
        return SimpleNamespace(
            nodes=[{"uuid": "node-1"}, {"uuid": "node-2"}],
            edges=[{"uuid": "edge-1"}],
        )


def test_build_graph_returns_job_id_and_updates_job_payload(monkeypatch):
    fake_graphiti = _FakeGraphiti()
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
    client = TestClient(app)

    response = client.post(
        "/graphs/mirofish_demo/build",
        json={
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
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    job_id = response.json()["job_id"]

    job_response = client.get(f"/jobs/{job_id}")

    assert job_response.status_code == 200
    payload = job_response.json()
    assert payload["job_id"] == job_id
    assert payload["job_type"] == "build_graph"
    assert payload["graph_id"] == "mirofish_demo"
    assert payload["status"] == "completed"
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
    client = TestClient(create_app())

    response = client.get("/jobs/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown graph job: missing"}


def test_health_routes_exist():
    client = TestClient(create_app())

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert ready.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.json()["status"] == "ok"
