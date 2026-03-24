"""Snapshot refresh helper for frontend-compatible graph reads."""

from __future__ import annotations

from collections.abc import Callable
from inspect import isawaitable

from graphiti_core import Graphiti
from graphiti_core.errors import GroupsEdgesNotFoundError, GroupsNodesNotFoundError

from miromem.graph_service.domain.snapshot_serializer import serialize_snapshot
from miromem.graph_service.models import utc_now
from miromem.graph_service.storage.snapshot_store import InMemorySnapshotStore


class SnapshotWorker:
    """Refresh graph snapshots while preserving stale fallback behavior."""

    def __init__(
        self,
        *,
        graphiti_factory: Callable[[], Graphiti],
        snapshot_store: InMemorySnapshotStore,
    ) -> None:
        self._graphiti_factory = graphiti_factory
        self._snapshot_store = snapshot_store

    async def refresh_snapshot(self, graph_id: str) -> dict[str, object]:
        """Rebuild and persist the frontend snapshot for a graph."""
        graphiti = self._graphiti_factory()
        try:
            try:
                nodes = await graphiti.nodes.entity.get_by_group_ids([graph_id])
            except GroupsNodesNotFoundError:
                nodes = []

            try:
                edges = await graphiti.edges.entity.get_by_group_ids([graph_id])
            except GroupsEdgesNotFoundError:
                edges = []

            snapshot = serialize_snapshot(
                nodes=nodes,
                edges=edges,
                graph_id=graph_id,
                stale=False,
                last_refreshed_at=utc_now().isoformat(),
            )
            return self._snapshot_store.save_snapshot(graph_id=graph_id, snapshot=snapshot)
        except Exception as exc:
            fallback = self._snapshot_store.mark_refresh_failed(
                graph_id,
                error_message=str(exc),
            )
            if fallback is not None:
                return fallback
            raise
        finally:
            await _close_graphiti(graphiti)


async def _close_graphiti(graphiti: Graphiti) -> None:
    close = getattr(graphiti, "close", None)
    if close is None:
        return
    result = close()
    if isawaitable(result):
        await result
