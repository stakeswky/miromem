"""Graph build routes for the internal graph-service API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
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


class GraphSearchRequest(BaseModel):
    """Request body for graph fact/entity search."""

    query: str
    limit: int = Field(default=10, gt=0)
    center_node_uuid: str | None = None


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


@router.get("/graphs/{graph_id}/snapshot")
async def get_graph_snapshot(graph_id: str, request: Request) -> dict[str, Any]:
    """Return the latest frontend snapshot, preferring the last successful cached payload."""
    snapshot = request.app.state.snapshot_store.get_snapshot(graph_id)
    if snapshot is not None:
        return snapshot

    try:
        return await request.app.state.snapshot_worker.refresh_snapshot(graph_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Snapshot unavailable for graph: {graph_id}",
        ) from exc


@router.get("/graphs/{graph_id}/entities")
async def list_graph_entities(
    graph_id: str,
    request: Request,
    entity_type: str | None = None,
) -> dict[str, Any]:
    """Return graph entities through the dedicated query service."""
    return await request.app.state.query_service.list_entities(
        graph_id=graph_id,
        entity_type=entity_type,
    )


@router.get("/graphs/{graph_id}/entities/{entity_id}")
async def get_graph_entity_detail(
    graph_id: str,
    entity_id: str,
    request: Request,
) -> dict[str, Any]:
    """Return one entity plus its local graph context."""
    payload = await request.app.state.query_service.get_entity_detail(
        graph_id=graph_id,
        entity_id=entity_id,
    )
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown graph entity: {entity_id}",
        )
    return payload


@router.post("/graphs/{graph_id}/search")
async def search_graph(
    graph_id: str,
    body: GraphSearchRequest,
    request: Request,
) -> dict[str, Any]:
    """Return fact and related-entity search output through the query service."""
    return await request.app.state.query_service.search(
        graph_id=graph_id,
        query=body.query,
        limit=body.limit,
        center_node_uuid=body.center_node_uuid,
    )
