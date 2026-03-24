"""In-memory Thinker job registry used for local orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from miromem.thinker.models import ThinkerJob, ThinkerJobStatus, ThinkerResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryThinkerJobStore:
    """Manage Thinker jobs without external persistence."""

    _ALLOWED_TRANSITIONS: dict[ThinkerJobStatus, set[ThinkerJobStatus]] = {
        "created": {"running", "failed"},
        "running": {"succeeded", "failed"},
        "succeeded": {"materialized"},
        "failed": {"created", "skipped"},
        "materialized": set(),
        "skipped": set(),
    }

    def __init__(self) -> None:
        self._jobs: dict[str, ThinkerJob] = {}

    def create_job(self, *, mode: str, research_direction: str) -> ThinkerJob:
        job = ThinkerJob(mode=mode, research_direction=research_direction)
        self._jobs[job.job_id] = job
        return self._copy_job(job)

    def get_job(self, job_id: str) -> ThinkerJob:
        return self._copy_job(self._require_job(job_id))

    def mark_running(self, job_id: str) -> ThinkerJob:
        return self._transition(
            job_id,
            "running",
            error_code=None,
            error_message=None,
            retryable=None,
        )

    def mark_succeeded(
        self,
        job_id: str,
        *,
        result: ThinkerResult | None = None,
    ) -> ThinkerJob:
        return self._transition(
            job_id,
            "succeeded",
            result=result,
            error_code=None,
            error_message=None,
            retryable=None,
        )

    def mark_failed(
        self,
        job_id: str,
        *,
        error_code: str,
        error_message: str,
        retryable: bool = True,
        can_continue_without_thinker: bool = True,
    ) -> ThinkerJob:
        return self._transition(
            job_id,
            "failed",
            error_code=error_code,
            error_message=error_message,
            retryable=retryable,
            can_continue_without_thinker=can_continue_without_thinker,
        )

    def mark_materialized(self, job_id: str) -> ThinkerJob:
        return self._transition(job_id, "materialized")

    def mark_skipped(self, job_id: str) -> ThinkerJob:
        return self._transition(job_id, "skipped")

    def retry_job(self, job_id: str) -> ThinkerJob:
        job = self._require_job(job_id)
        if job.status != "failed":
            raise ValueError("Only failed jobs can be retried.")

        return self._transition(
            job_id,
            "created",
            result=None,
            error_code=None,
            error_message=None,
            retryable=None,
        )

    def _require_job(self, job_id: str) -> ThinkerJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise KeyError(f"Unknown Thinker job: {job_id}") from exc

    def _transition(
        self,
        job_id: str,
        status: ThinkerJobStatus,
        *,
        result: ThinkerResult | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        retryable: bool | None = None,
        can_continue_without_thinker: bool | None = None,
    ) -> ThinkerJob:
        job = self._require_job(job_id)
        if status not in self._ALLOWED_TRANSITIONS[job.status]:
            raise ValueError(f"Illegal Thinker job transition: {job.status} -> {status}")

        job.status = status
        if result is not None:
            job.result = result
        job.error_code = error_code
        job.error_message = error_message
        job.retryable = retryable
        if can_continue_without_thinker is not None:
            job.can_continue_without_thinker = can_continue_without_thinker
        job.updated_at = _utcnow()
        return self._copy_job(job)

    def _copy_job(self, job: ThinkerJob) -> ThinkerJob:
        return job.model_copy(deep=True)
