"""Minimal in-process worker for graph build jobs."""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any

from miromem.graph_service.core.config import GraphServiceSettings
from miromem.graph_service.core.graphiti_factory import build_graphiti
from miromem.graph_service.domain.episode_builder import build_document_episodes
from miromem.graph_service.domain.schema_compiler import compile_ontology
from miromem.graph_service.models import utc_now
from miromem.graph_service.storage.graph_metadata_store import InMemoryGraphMetadataStore
from miromem.graph_service.storage.job_store import InMemoryGraphJobStore

import graphiti_core.graphiti as graphiti_module

logger = logging.getLogger(__name__)
_GRAPHITI_BUILD_INSTRUMENTED = False


@dataclass(slots=True)
class BuildGraphCommand:
    """Queued payload for a graph build request."""

    job_id: str
    graph_id: str
    request_payload: dict[str, Any]


class BuildWorker:
    """Queue-like abstraction that executes build jobs in process for v1."""

    BULK_BUILD_TIMEOUT_SECONDS = 45

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
        self._queue: Queue[BuildGraphCommand] = Queue()
        self._shutdown_event = Event()
        self._dispatcher = Thread(
            target=self._dispatch_loop,
            name="miromem-graph-build-worker",
            daemon=True,
        )
        self._dispatcher.start()

    def enqueue(self, *, job_id: str, graph_id: str, request_payload: Mapping[str, Any]) -> None:
        """Queue a build job for the background dispatcher and return immediately."""
        self._queue.put(
            BuildGraphCommand(
                job_id=job_id,
                graph_id=graph_id,
                request_payload=dict(request_payload),
            )
        )

    def shutdown(self, timeout: float = 1.0) -> None:
        """Stop the background dispatcher thread."""
        self._shutdown_event.set()
        if self._dispatcher.is_alive():
            self._dispatcher.join(timeout=timeout)

    def _dispatch_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                command = self._queue.get(timeout=0.1)
            except Empty:
                continue

            try:
                asyncio.run(self._execute(command))
            finally:
                self._queue.task_done()

    async def _execute(self, command: BuildGraphCommand) -> None:
        self._job_store.mark_running(command.job_id)

        try:
            _instrument_graphiti_build_steps()
            print(f"build_worker[{command.job_id}] stage=compile_ontology graph_id={command.graph_id}", flush=True)
            ontology = compile_ontology(command.request_payload.get("ontology", {}))
            print(f"build_worker[{command.job_id}] stage=build_document_episodes graph_id={command.graph_id}", flush=True)
            episodes = build_document_episodes(
                graph_name=str(command.request_payload.get("graph_name", command.graph_id)),
                document_text=str(command.request_payload.get("document_text", "")),
                chunk_size=int(command.request_payload.get("chunk_size", 500)),
                chunk_overlap=int(command.request_payload.get("chunk_overlap", 50)),
            )
            print(
                f"build_worker[{command.job_id}] stage=build_graphiti graph_id={command.graph_id} episodes={len(episodes)}",
                flush=True,
            )
            graphiti = build_graphiti(self._settings)
            print(f"build_worker[{command.job_id}] stage=build_indices graph_id={command.graph_id}", flush=True)
            await graphiti.build_indices_and_constraints()
            print(f"build_worker[{command.job_id}] stage=add_episode_bulk:start graph_id={command.graph_id}", flush=True)
            results = await self._add_episodes_with_fallback(
                graphiti=graphiti,
                graph_id=command.graph_id,
                episodes=episodes,
                ontology=ontology,
                job_id=command.job_id,
            )
            print(
                f"build_worker[{command.job_id}] stage=add_episode_bulk:done graph_id={command.graph_id} "
                f"nodes={len(getattr(results, 'nodes', []))} edges={len(getattr(results, 'edges', []))}",
                flush=True,
            )

            built_at = utc_now()
            node_count = len(getattr(results, "nodes", []))
            edge_count = len(getattr(results, "edges", []))
            chunk_count = len(episodes)

            print(f"build_worker[{command.job_id}] stage=save_metadata graph_id={command.graph_id}", flush=True)
            self._metadata_store.save_metadata(
                graph_id=command.graph_id,
                chunk_count=chunk_count,
                node_count=node_count,
                edge_count=edge_count,
                last_built_at=built_at,
            )
            print(f"build_worker[{command.job_id}] stage=mark_completed graph_id={command.graph_id}", flush=True)
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
            print(f"build_worker[{command.job_id}] stage=failed graph_id={command.graph_id}", flush=True)
            self._job_store.mark_failed(
                command.job_id,
                error_message=f"{exc}\n{traceback.format_exc()}",
            )

    async def _add_episodes_with_fallback(
        self,
        *,
        graphiti,
        graph_id: str,
        episodes: list[Any],
        ontology,
        job_id: str,
    ):
        try:
            return await asyncio.wait_for(
                graphiti.add_episode_bulk(
                    episodes,
                    group_id=graph_id,
                    entity_types=ontology.entity_types,
                    edge_types=ontology.edge_types,
                    edge_type_map=ontology.edge_type_map,
                ),
                timeout=self.BULK_BUILD_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            print(
                f"build_worker[{job_id}] stage=add_episode_bulk:fallback graph_id={graph_id} reason={exc}",
                flush=True,
            )
            nodes = []
            edges = []
            episode_results = []
            for episode in episodes:
                single_result = await graphiti.add_episode(
                    name=episode.name,
                    episode_body=episode.content,
                    source_description=episode.source_description,
                    reference_time=episode.reference_time,
                    source=episode.source,
                    group_id=graph_id,
                    entity_types=ontology.entity_types,
                    edge_types=ontology.edge_types,
                    edge_type_map=ontology.edge_type_map,
                )
                nodes.extend(getattr(single_result, "nodes", []))
                edges.extend(getattr(single_result, "edges", []))
                episode_results.append(getattr(single_result, "episode", None))

            return SimpleNamespace(nodes=nodes, edges=edges, episodes=episode_results)


def _instrument_graphiti_build_steps() -> None:
    global _GRAPHITI_BUILD_INSTRUMENTED
    if _GRAPHITI_BUILD_INSTRUMENTED:
        return

    def wrap_async(name: str, fn):
        async def wrapped(*args, **kwargs):
            print(f"graphiti_stage:start:{name}", flush=True)
            result = await fn(*args, **kwargs)
            print(f"graphiti_stage:end:{name}", flush=True)
            return result
        return wrapped

    def wrap_sync(name: str, fn):
        def wrapped(*args, **kwargs):
            print(f"graphiti_stage:start:{name}", flush=True)
            result = fn(*args, **kwargs)
            print(f"graphiti_stage:end:{name}", flush=True)
            return result
        return wrapped

    graphiti_module.add_nodes_and_edges_bulk = wrap_async(
        "add_nodes_and_edges_bulk",
        graphiti_module.add_nodes_and_edges_bulk,
    )
    graphiti_module.retrieve_previous_episodes_bulk = wrap_async(
        "retrieve_previous_episodes_bulk",
        graphiti_module.retrieve_previous_episodes_bulk,
    )
    graphiti_module.extract_nodes_and_edges_bulk = wrap_async(
        "extract_nodes_and_edges_bulk",
        graphiti_module.extract_nodes_and_edges_bulk,
    )
    graphiti_module.dedupe_nodes_bulk = wrap_async(
        "dedupe_nodes_bulk",
        graphiti_module.dedupe_nodes_bulk,
    )
    graphiti_module.dedupe_edges_bulk = wrap_async(
        "dedupe_edges_bulk",
        graphiti_module.dedupe_edges_bulk,
    )
    graphiti_module.resolve_edge_pointers = wrap_sync(
        "resolve_edge_pointers",
        graphiti_module.resolve_edge_pointers,
    )
    _GRAPHITI_BUILD_INSTRUMENTED = True
