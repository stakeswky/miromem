"""Graph build routes for the internal graph-service API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


class GraphBuildRequest(BaseModel):
    """Request body for queuing a graph build."""

    project_id: str
    graph_name: str
    document_text: str
    chunk_size: int = Field(default=500, gt=0)
    chunk_overlap: int = Field(default=50, ge=0)
    ontology: dict[str, Any]


class GraphJobQueuedResponse(BaseModel):
    """Response body returned when a graph build job is queued."""

    job_id: str
    status: str


router = APIRouter(tags=["graphs"])


@router.post("/graphs/{graph_id}/build", status_code=202, response_model=GraphJobQueuedResponse)
def build_graph(graph_id: str, body: GraphBuildRequest, request: Request) -> GraphJobQueuedResponse:
    """Create a build job and hand it to the in-process worker."""
    job = request.app.state.job_store.create_job(
        job_type="build_graph",
        graph_id=graph_id,
        metadata={
            "project_id": body.project_id,
            "graph_name": body.graph_name,
        },
    )
    request.app.state.build_worker.enqueue(
        job_id=job.job_id,
        graph_id=graph_id,
        request_payload=body.model_dump(mode="python"),
    )
    return GraphJobQueuedResponse(job_id=job.job_id, status=job.status.value)
