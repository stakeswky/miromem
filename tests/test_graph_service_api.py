"""API tests for the internal graph-service build and job routes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
import pytest

import miromem.graph_service.workers.build_worker as build_worker_module
from miromem.graph_service.app import create_app
from miromem.graph_service.domain.query_service import GraphQueryService


def test_compose_wires_falkordb_and_graph_service_for_mirofish() -> None:
    compose_text = Path("docker-compose.yaml").read_text(encoding="utf-8")
    dockerfile_text = Path("graph_service/Dockerfile").read_text(encoding="utf-8")
    graph_service_section = compose_text.split("\n  graph-service:\n", maxsplit=1)[1].split("\n\n  #", maxsplit=1)[0]
    mirofish_section = compose_text.split("\n  mirofish:\n", maxsplit=1)[1].split("\n\n  #", maxsplit=1)[0]

    assert "falkordb:" in compose_text
    assert "graph-service:" in compose_text
    assert "context: ." in compose_text
    assert "dockerfile: graph_service/Dockerfile" in compose_text
    assert "depends_on:" in graph_service_section
    assert "falkordb:" in graph_service_section
    assert "condition: service_healthy" in graph_service_section
    assert "GRAPH_SERVICE_BASE_URL: ${GRAPH_SERVICE_BASE_URL:-http://graph-service:8001}" in mirofish_section
    assert "GRAPH_BACKEND: ${GRAPH_BACKEND:-zep}" in mirofish_section
    assert "miromem.graph_service.app:app" in dockerfile_text
    assert "--port" in dockerfile_text
    assert "8001" in dockerfile_text


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


def test_snapshot_endpoint_returns_last_successful_snapshot_when_refresh_failed():
    app = create_app()
    app.state.snapshot_store.save_snapshot(
        graph_id="mirofish_demo",
        snapshot={
            "graph_id": "mirofish_demo",
            "node_count": 1,
            "edge_count": 0,
            "stale": False,
            "last_refreshed_at": "2026-03-24T12:00:00+00:00",
            "nodes": [
                {
                    "uuid": "node-1",
                    "name": "Alice",
                    "labels": ["Entity", "Person"],
                    "summary": "A market analyst",
                    "attributes": {},
                    "created_at": "2026-03-24T11:00:00+00:00",
                }
            ],
            "edges": [],
        },
    )
    app.state.snapshot_store.mark_refresh_failed(
        "mirofish_demo",
        error_message="refresh failed",
    )

    with TestClient(app) as client:
        response = client.get("/graphs/mirofish_demo/snapshot")

    assert response.status_code == 200
    assert response.json() == {
        "graph_id": "mirofish_demo",
        "node_count": 1,
        "edge_count": 0,
        "stale": True,
        "last_refreshed_at": "2026-03-24T12:00:00+00:00",
        "nodes": [
            {
                "uuid": "node-1",
                "name": "Alice",
                "labels": ["Entity", "Person"],
                "summary": "A market analyst",
                "attributes": {},
                "created_at": "2026-03-24T11:00:00+00:00",
            }
        ],
        "edges": [],
    }


def test_entity_routes_delegate_to_query_service():
    class _FakeQueryService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        async def list_entities(
            self,
            *,
            graph_id: str,
            entity_type: str | None = None,
        ) -> dict[str, Any]:
            self.calls.append(
                (
                    "list_entities",
                    (),
                    {
                        "graph_id": graph_id,
                        "entity_type": entity_type,
                    },
                )
            )
            return {
                "entities": [{"uuid": "node-1", "name": "Alice"}],
                "entity_types": ["Person"],
                "total_count": 1,
                "filtered_count": 1,
            }

        async def get_entity_detail(
            self,
            *,
            graph_id: str,
            entity_id: str,
        ) -> dict[str, Any] | None:
            self.calls.append(
                (
                    "get_entity_detail",
                    (),
                    {
                        "graph_id": graph_id,
                        "entity_id": entity_id,
                    },
                )
            )
            return {
                "uuid": entity_id,
                "name": "Alice",
                "labels": ["Entity", "Person"],
                "summary": "A market analyst",
                "attributes": {},
                "related_edges": [],
                "related_nodes": [],
            }

        async def search(
            self,
            *,
            graph_id: str,
            query: str,
            limit: int = 10,
            center_node_uuid: str | None = None,
        ) -> dict[str, Any]:
            self.calls.append(
                (
                    "search",
                    (),
                    {
                        "graph_id": graph_id,
                        "query": query,
                        "limit": limit,
                        "center_node_uuid": center_node_uuid,
                    },
                )
            )
            return {
                "facts": ["Alice is campaigning in California."],
                "node_summaries": ["California: A state"],
                "context": "facts and nodes",
            }

    app = create_app()
    fake_query_service = _FakeQueryService()
    app.state.query_service = fake_query_service

    with TestClient(app) as client:
        entities_response = client.get(
            "/graphs/mirofish_demo/entities",
            params={"entity_type": "Person"},
        )
        entity_response = client.get("/graphs/mirofish_demo/entities/node-1")
        search_response = client.post(
            "/graphs/mirofish_demo/search",
            json={"query": "Alice", "limit": 5},
        )

    assert entities_response.status_code == 200
    assert entities_response.json()["entities"][0]["uuid"] == "node-1"
    assert entity_response.status_code == 200
    assert entity_response.json()["uuid"] == "node-1"
    assert search_response.status_code == 200
    assert search_response.json() == {
        "facts": ["Alice is campaigning in California."],
        "node_summaries": ["California: A state"],
        "context": "facts and nodes",
    }
    assert fake_query_service.calls == [
        (
            "list_entities",
            (),
            {
                "graph_id": "mirofish_demo",
                "entity_type": "Person",
            },
        ),
        (
            "get_entity_detail",
            (),
            {
                "graph_id": "mirofish_demo",
                "entity_id": "node-1",
            },
        ),
        (
            "search",
            (),
            {
                "graph_id": "mirofish_demo",
                "query": "Alice",
                "limit": 5,
                "center_node_uuid": None,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_query_service_search_preserves_fact_type_and_group_scope():
    class _FakeGraphiti:
        def __init__(self) -> None:
            self.search_calls: list[dict[str, Any]] = []

        async def search_(
            self,
            query: str,
            config: Any,
            group_ids: list[str] | None = None,
            center_node_uuid: str | None = None,
            bfs_origin_node_uuids: list[str] | None = None,
            search_filter: Any | None = None,
            driver: Any | None = None,
        ) -> Any:
            self.search_calls.append(
                {
                    "query": query,
                    "config_limit": config.limit,
                    "group_ids": group_ids,
                    "center_node_uuid": center_node_uuid,
                }
            )
            return SimpleNamespace(
                nodes=[
                    SimpleNamespace(
                        uuid="node-1",
                        name="Alice",
                        labels=["Entity", "Person"],
                        summary="A market analyst",
                        attributes={},
                        created_at=datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc),
                    ),
                    SimpleNamespace(
                        uuid="node-2",
                        name="Bob",
                        labels=["Entity", "Person"],
                        summary="A campaign manager",
                        attributes={},
                        created_at=datetime(2026, 3, 24, 12, 5, tzinfo=timezone.utc),
                    ),
                ],
                edges=[
                    SimpleNamespace(
                        uuid_="edge-1",
                        name="",
                        fact_type="ALLY_OF",
                        fact="Alice works closely with Bob.",
                        source_node_uuid="node-1",
                        target_node_uuid="node-2",
                        attributes={"confidence": "medium"},
                        created_at=datetime(2026, 3, 24, 12, 10, tzinfo=timezone.utc),
                        valid_at=None,
                        invalid_at=None,
                        expired_at=None,
                        episode_ids=["episode-1"],
                    )
                ],
            )

        async def close(self) -> None:
            return None

    fake_graphiti = _FakeGraphiti()
    query_service = GraphQueryService(graphiti_factory=lambda: fake_graphiti)

    payload = await query_service.search(
        graph_id="mirofish_demo",
        query="Alice alliances",
        limit=4,
        center_node_uuid="node-1",
    )

    assert fake_graphiti.search_calls == [
        {
            "query": "Alice alliances",
            "config_limit": 4,
            "group_ids": ["mirofish_demo"],
            "center_node_uuid": "node-1",
        }
    ]
    assert payload["facts"] == ["Alice works closely with Bob."]
    assert payload["node_summaries"] == [
        "Alice: A market analyst",
        "Bob: A campaign manager",
    ]
    assert payload["edges"] == [
        {
            "uuid": "edge-1",
            "name": "",
            "fact": "Alice works closely with Bob.",
            "fact_type": "ALLY_OF",
            "source_node_uuid": "node-1",
            "target_node_uuid": "node-2",
            "source_node_name": "Alice",
            "target_node_name": "Bob",
            "attributes": {"confidence": "medium"},
            "created_at": "2026-03-24T12:10:00+00:00",
            "valid_at": None,
            "invalid_at": None,
            "expired_at": None,
            "episodes": ["episode-1"],
        }
    ]
