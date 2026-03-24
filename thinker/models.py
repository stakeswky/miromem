"""Pydantic models for Thinker orchestration jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

ThinkerJobStatus = Literal[
    "created",
    "running",
    "succeeded",
    "failed",
    "materialized",
    "skipped",
]
ThinkerMode = Literal["topic_only", "upload", "polymarket"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _job_id() -> str:
    return str(uuid4())


class ThinkerUploadedFile(BaseModel):
    """Normalized uploaded file payload passed into Thinker."""

    name: str
    text: str = ""


class ThinkerPolymarketEvent(BaseModel):
    """Normalized Polymarket event payload used by Thinker."""

    title: str = ""
    description: str = ""
    outcomes: list[str] = Field(default_factory=list)
    url: str = ""
    summary: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class ThinkerReference(BaseModel):
    """Normalized evidence reference returned by Thinker providers."""

    title: str
    url: str
    source_type: str = "web"


class ThinkerResult(BaseModel):
    """Normalized Thinker output consumed by the API and materializer."""

    expanded_topics: list[str] = Field(default_factory=list)
    enriched_seed_text: str = ""
    suggested_simulation_prompt: str = ""
    references: list[ThinkerReference] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class ThinkerJob(BaseModel):
    """State tracked for a single Thinker orchestration job."""

    model_config = ConfigDict(validate_assignment=True)

    job_id: str = Field(default_factory=_job_id)
    mode: str
    research_direction: str
    status: ThinkerJobStatus = "created"
    result: ThinkerResult | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool | None = None
    can_continue_without_thinker: bool = True
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
