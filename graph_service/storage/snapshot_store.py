"""In-memory persistence for graph snapshots and stale fallback metadata."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Any

from pydantic import BaseModel

from miromem.graph_service.models import utc_now


class StoredGraphSnapshot(BaseModel):
    """Persisted graph snapshot with refresh failure metadata."""

    graph_id: str
    payload: dict[str, Any]
    refresh_error: str | None = None
    last_failed_at: datetime | None = None


class InMemorySnapshotStore:
    """Store graph snapshots and retain the last successful payload on failures."""

    def __init__(self) -> None:
        self._snapshots: dict[str, StoredGraphSnapshot] = {}
        self._lock = RLock()

    def save_snapshot(self, *, graph_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Persist a successful snapshot refresh and clear any stale flag."""
        normalized_payload = deepcopy(snapshot)
        normalized_payload["graph_id"] = graph_id
        normalized_payload["stale"] = False
        record = StoredGraphSnapshot(graph_id=graph_id, payload=normalized_payload)

        with self._lock:
            self._snapshots[graph_id] = record

        return self._to_public_payload(record)

    def get_snapshot(self, graph_id: str) -> dict[str, Any] | None:
        """Fetch the latest snapshot payload, marking it stale if the last refresh failed."""
        with self._lock:
            record = self._snapshots.get(graph_id)
            if record is None:
                return None
            return self._to_public_payload(record)

    def mark_refresh_failed(self, graph_id: str, *, error_message: str) -> dict[str, Any] | None:
        """Preserve the last successful snapshot and mark it stale after a refresh failure."""
        with self._lock:
            record = self._snapshots.get(graph_id)
            if record is None:
                return None

            updated = record.model_copy(
                update={
                    "refresh_error": error_message,
                    "last_failed_at": utc_now(),
                },
                deep=True,
            )
            self._snapshots[graph_id] = updated
            return self._to_public_payload(updated)

    @staticmethod
    def _to_public_payload(record: StoredGraphSnapshot) -> dict[str, Any]:
        payload = deepcopy(record.payload)
        payload["stale"] = record.refresh_error is not None
        return payload
