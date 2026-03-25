"""Job status routes for the internal graph-service API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from miromem.graph_service.models import GraphJob

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}", response_model=GraphJob)
def get_job(job_id: str, request: Request) -> GraphJob:
    """Return the current payload for a queued or completed graph job."""
    job = request.app.state.job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown graph job: {job_id}")
    return job
