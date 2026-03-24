"""In-memory graph build metadata persistence."""

from __future__ import annotations

from datetime import datetime
from threading import RLock

from pydantic import BaseModel


class GraphBuildMetadata(BaseModel):
    """Stored build statistics for a graph."""

    graph_id: str
    chunk_count: int
    node_count: int
    edge_count: int
    last_built_at: datetime


class InMemoryGraphMetadataStore:
    """Store graph build metadata in memory behind a persistence-like interface."""

    def __init__(self) -> None:
        self._metadata: dict[str, GraphBuildMetadata] = {}
        self._lock = RLock()

    def save_metadata(
        self,
        *,
        graph_id: str,
        chunk_count: int,
        node_count: int,
        edge_count: int,
        last_built_at: datetime,
    ) -> GraphBuildMetadata:
        """Persist build statistics for a graph."""
        metadata = GraphBuildMetadata(
            graph_id=graph_id,
            chunk_count=chunk_count,
            node_count=node_count,
            edge_count=edge_count,
            last_built_at=last_built_at,
        )
        with self._lock:
            self._metadata[graph_id] = metadata
        return metadata.model_copy(deep=True)

    def get_metadata(self, graph_id: str) -> GraphBuildMetadata | None:
        """Fetch persisted build metadata for a graph."""
        with self._lock:
            metadata = self._metadata.get(graph_id)
            if metadata is None:
                return None
            return metadata.model_copy(deep=True)
