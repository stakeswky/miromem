"""Pydantic models for Thinker orchestration jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

ThinkerJobMode = Literal["topic_only", "upload", "polymarket"]

ThinkerJobStatus = Literal[
    "created",
    "running",
    "succeeded",
    "failed",
    "materialized",
    "skipped",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _job_id() -> str:
    return str(uuid4())


class ThinkerJob(BaseModel):
    """State tracked for a single Thinker orchestration job."""

    model_config = ConfigDict(validate_assignment=True)

    job_id: str = Field(default_factory=_job_id)
    mode: ThinkerJobMode
    research_direction: str
    status: ThinkerJobStatus = "created"
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
