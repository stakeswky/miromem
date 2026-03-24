"""Pydantic models for Thinker orchestration jobs and API DTOs."""

from __future__ import annotations

from datetime import datetime, timezone
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


class ThinkerJob(BaseModel):
    """State tracked for a single Thinker orchestration job."""

    model_config = ConfigDict(validate_assignment=True)

    job_id: str = Field(default_factory=_job_id)
    mode: str
    research_direction: str
    status: ThinkerJobStatus = "created"
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class ThinkerJobCreateRequest(BaseModel):
    """Create-job request validated at the HTTP boundary."""

    mode: ThinkerMode
    research_direction: str


class ThinkerJobCreateResponse(BaseModel):
    """Create-job response body."""

    job_id: str
    status: ThinkerJobStatus


class ThinkerJobStatusResponse(BaseModel):
    """Job status response body."""

    job_id: str
    mode: str
    research_direction: str
    status: ThinkerJobStatus
    error_code: str | None = None
    error_message: str | None = None


class ThinkerAdoptedInput(BaseModel):
    """User-adopted placeholder data returned by the materialize skeleton."""

    expanded_topics: list[str] = Field(default_factory=list)
    enriched_seed_text: str = ""
    suggested_simulation_prompt: str = ""


class ThinkerMaterializeRequest(BaseModel):
    """Materialize request body."""

    job_id: str
    adopted: ThinkerAdoptedInput = Field(default_factory=ThinkerAdoptedInput)


class ThinkerMaterializedPayload(BaseModel):
    """Placeholder materialized output for the Task 2 skeleton."""

    final_topics: list[str] = Field(default_factory=list)
    final_seed_text: str = ""
    final_simulation_requirement: str = ""


class ThinkerMaterializeResponse(BaseModel):
    """Materialize response body."""

    job_id: str
    status: ThinkerJobStatus
    payload: ThinkerMaterializedPayload
