"""In-memory graph job persistence primitives."""

from __future__ import annotations

from threading import RLock
from typing import Any
from uuid import uuid4

from miromem.graph_service.models import GraphJob, GraphJobStatus, utc_now


class InMemoryGraphJobStore:
    """Store graph jobs in memory behind a persistence-like interface."""

    def __init__(self) -> None:
        self._jobs: dict[str, GraphJob] = {}
        self._lock = RLock()

    def create_job(
        self,
        *,
        job_type: str,
        graph_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> GraphJob:
        """Create and store a new queued job."""
        job = GraphJob(
            job_id=uuid4().hex,
            job_type=job_type,
            graph_id=graph_id,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job.model_copy(deep=True)

    def get_job(self, job_id: str) -> GraphJob | None:
        """Fetch a stored job by id."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return job.model_copy(deep=True)

    def mark_running(self, job_id: str) -> GraphJob:
        """Transition a job to the running state."""
        return self._update_job(job_id, status=GraphJobStatus.RUNNING)

    def mark_completed(self, job_id: str, metadata: dict[str, Any] | None = None) -> GraphJob:
        """Transition a job to the completed state."""
        updates: dict[str, Any] = {
            "status": GraphJobStatus.COMPLETED,
            "completed_at": utc_now(),
            "error_message": None,
            "degraded_reason": None,
        }
        if metadata:
            updates["metadata"] = dict(metadata)
        return self._update_job(job_id, **updates)

    def mark_failed(self, job_id: str, *, error_message: str) -> GraphJob:
        """Transition a job to the failed state."""
        return self._update_job(
            job_id,
            status=GraphJobStatus.FAILED,
            completed_at=utc_now(),
            error_message=error_message,
            degraded_reason=None,
        )

    def mark_degraded(self, job_id: str, *, reason: str) -> GraphJob:
        """Transition a job to the degraded state."""
        return self._update_job(
            job_id,
            status=GraphJobStatus.DEGRADED,
            degraded_reason=reason,
        )

    def _update_job(self, job_id: str, **changes: Any) -> GraphJob:
        """Apply a state transition to an existing job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(f"Unknown graph job: {job_id}")
            updated = job.model_copy(update={"updated_at": utc_now(), **changes}, deep=True)
            self._jobs[job_id] = updated
            return updated.model_copy(deep=True)
