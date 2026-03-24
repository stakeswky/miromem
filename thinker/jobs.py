"""In-memory Thinker job registry used for local orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from miromem.thinker.models import ThinkerJob, ThinkerJobStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryThinkerJobStore:
    """Manage Thinker jobs without external persistence."""

    def __init__(self) -> None:
        self._jobs: dict[str, ThinkerJob] = {}

    def create_job(self, *, mode: str, research_direction: str) -> ThinkerJob:
        job = ThinkerJob(mode=mode, research_direction=research_direction)
        self._jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> ThinkerJob:
        return self._require_job(job_id)

    def mark_running(self, job_id: str) -> ThinkerJob:
        return self._set_status(job_id, "running")

    def mark_succeeded(self, job_id: str) -> ThinkerJob:
        return self._set_status(job_id, "succeeded")

    def mark_failed(self, job_id: str, *, error_code: str, error_message: str) -> ThinkerJob:
        return self._set_status(
            job_id,
            "failed",
            error_code=error_code,
            error_message=error_message,
        )

    def mark_materialized(self, job_id: str) -> ThinkerJob:
        return self._set_status(job_id, "materialized")

    def mark_skipped(self, job_id: str) -> ThinkerJob:
        return self._set_status(job_id, "skipped")

    def retry_job(self, job_id: str) -> ThinkerJob:
        job = self._require_job(job_id)
        if job.status != "failed":
            raise ValueError("Only failed jobs can be retried.")

        return self._set_status(job_id, "created", error_code=None, error_message=None)

    def _require_job(self, job_id: str) -> ThinkerJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError(f"Unknown Thinker job: {job_id}") from exc

    def _set_status(
        self,
        job_id: str,
        status: ThinkerJobStatus,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ThinkerJob:
        job = self._require_job(job_id)
        job.status = status
        job.error_code = error_code
        job.error_message = error_message
        job.updated_at = _utcnow()
        return job
