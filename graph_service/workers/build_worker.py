"""Minimal in-process worker for graph build jobs."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock
from typing import Any

from miromem.graph_service.core.config import GraphServiceSettings
from miromem.graph_service.core.graphiti_factory import build_graphiti
from miromem.graph_service.domain.episode_builder import build_document_episodes
from miromem.graph_service.domain.schema_compiler import compile_ontology
from miromem.graph_service.models import utc_now
from miromem.graph_service.storage.graph_metadata_store import InMemoryGraphMetadataStore
from miromem.graph_service.storage.job_store import InMemoryGraphJobStore


@dataclass(slots=True)
class BuildGraphCommand:
    """Queued payload for a graph build request."""

    job_id: str
    graph_id: str
    request_payload: dict[str, Any]


class BuildWorker:
    """Queue-like abstraction that executes build jobs in process for v1."""

    def __init__(
        self,
        *,
        settings: GraphServiceSettings,
        job_store: InMemoryGraphJobStore,
        metadata_store: InMemoryGraphMetadataStore,
    ) -> None:
        self._settings = settings
        self._job_store = job_store
        self._metadata_store = metadata_store
        self._queue: deque[BuildGraphCommand] = deque()
        self._lock = RLock()
        self._draining = False

    def enqueue(self, *, job_id: str, graph_id: str, request_payload: Mapping[str, Any]) -> None:
        """Queue a build job and drain the in-memory worker immediately."""
        command = BuildGraphCommand(
            job_id=job_id,
            graph_id=graph_id,
            request_payload=dict(request_payload),
        )
        with self._lock:
            self._queue.append(command)
            if self._draining:
                return
            self._draining = True

        try:
            while True:
                with self._lock:
                    if not self._queue:
                        self._draining = False
                        break
                    next_command = self._queue.popleft()
                asyncio.run(self._execute(next_command))
        finally:
            with self._lock:
                self._draining = False

    async def _execute(self, command: BuildGraphCommand) -> None:
        self._job_store.mark_running(command.job_id)

        try:
            ontology = compile_ontology(command.request_payload.get("ontology", {}))
            episodes = build_document_episodes(
                graph_name=str(command.request_payload.get("graph_name", command.graph_id)),
                document_text=str(command.request_payload.get("document_text", "")),
                chunk_size=int(command.request_payload.get("chunk_size", 500)),
                chunk_overlap=int(command.request_payload.get("chunk_overlap", 50)),
            )
            graphiti = build_graphiti(self._settings)
            await graphiti.build_indices_and_constraints()
            results = await graphiti.add_episode_bulk(
                episodes,
                group_id=command.graph_id,
                entity_types=ontology.entity_types,
                edge_types=ontology.edge_types,
                edge_type_map=ontology.edge_type_map,
            )

            built_at = utc_now()
            node_count = len(getattr(results, "nodes", []))
            edge_count = len(getattr(results, "edges", []))
            chunk_count = len(episodes)

            self._metadata_store.save_metadata(
                graph_id=command.graph_id,
                chunk_count=chunk_count,
                node_count=node_count,
                edge_count=edge_count,
                last_built_at=built_at,
            )
            self._job_store.mark_completed(
                command.job_id,
                metadata={
                    "project_id": command.request_payload.get("project_id"),
                    "graph_name": command.request_payload.get("graph_name"),
                    "chunk_count": chunk_count,
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "last_built_at": built_at,
                },
            )
        except Exception as exc:
            self._job_store.mark_failed(command.job_id, error_message=str(exc))
