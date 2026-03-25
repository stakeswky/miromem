"""Pydantic models shared by the internal graph-service package."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class GraphJobStatus(str, Enum):
    """Lifecycle states for graph-service background jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


class GraphJob(BaseModel):
    """In-memory representation of a graph-service background job."""

    job_id: str
    job_type: str
    graph_id: str
    status: GraphJobStatus = GraphJobStatus.QUEUED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    error_message: str | None = None
    degraded_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
