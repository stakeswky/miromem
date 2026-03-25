"""In-memory Thinker job registry used for local orchestration."""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from miromem.thinker.models import (
    ThinkerJob,
    ThinkerJobStatus,
    ThinkerResult,
    ThinkerUploadedFile,
    thinker_available_actions,
)

_UNSET = object()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryThinkerJobStore:
    """Manage Thinker jobs without external persistence."""

    _ALLOWED_TRANSITIONS: dict[ThinkerJobStatus, set[ThinkerJobStatus]] = {
        "created": {"running", "failed"},
        "running": {"succeeded", "failed"},
        "succeeded": {"materialized", "skipped"},
        "failed": {"created", "skipped"},
        "materialized": set(),
        "skipped": set(),
    }

    def __init__(self) -> None:
        self._jobs: dict[str, ThinkerJob] = {}

    def create_job(
        self,
        *,
        mode: str,
        research_direction: str,
        seed_text: str = "",
        uploaded_files: list[ThinkerUploadedFile] | None = None,
        polymarket_event: dict[str, Any] | None = None,
    ) -> ThinkerJob:
        job = ThinkerJob(
            mode=mode,
            research_direction=research_direction,
            seed_text=seed_text,
            uploaded_files=uploaded_files or [],
            polymarket_event=polymarket_event,
        )
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
            can_continue_without_thinker=True,
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
            can_continue_without_thinker=True,
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
        job = self._require_job(job_id)
        if job.status != "succeeded":
            raise ValueError("Thinker job is not ready to materialize")
        if job.result is None:
            raise ValueError("Thinker job cannot be materialized without a stored result")

        return self._transition(
            job_id,
            "materialized",
            error_code=None,
            error_message=None,
            retryable=None,
            can_continue_without_thinker=True,
        )

    def mark_skipped(self, job_id: str) -> ThinkerJob:
        job = self._require_job(job_id)
        if "skip" not in thinker_available_actions(
            status=job.status,
            retryable=job.retryable,
            can_continue_without_thinker=job.can_continue_without_thinker,
        ):
            raise ValueError("Thinker job cannot be skipped.")

        return self._transition(
            job_id,
            "skipped",
            error_code=None,
            error_message=None,
            retryable=None,
            can_continue_without_thinker=True,
        )

    def retry_job(self, job_id: str) -> ThinkerJob:
        job = self._require_job(job_id)
        if "retry" not in thinker_available_actions(
            status=job.status,
            retryable=job.retryable,
            can_continue_without_thinker=job.can_continue_without_thinker,
        ):
            raise ValueError("Thinker job cannot be retried.")

        return self._transition(
            job_id,
            "created",
            result=None,
            error_code=None,
            error_message=None,
            retryable=None,
            can_continue_without_thinker=True,
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
        result: ThinkerResult | None | object = _UNSET,
        error_code: str | None = None,
        error_message: str | None = None,
        retryable: bool | None = None,
        can_continue_without_thinker: bool | None = None,
    ) -> ThinkerJob:
        job = self._require_job(job_id)
        if status not in self._ALLOWED_TRANSITIONS[job.status]:
            raise ValueError(f"Illegal Thinker job transition: {job.status} -> {status}")

        job.status = status
        if result is not _UNSET:
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
