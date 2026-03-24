"""Thinker API endpoints for the gateway skeleton."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from miromem.thinker.jobs import InMemoryThinkerJobStore
from miromem.thinker.models import (
    ThinkerJobCreateRequest,
    ThinkerJobCreateResponse,
    ThinkerJobStatusResponse,
    ThinkerMaterializedPayload,
    ThinkerMaterializeRequest,
    ThinkerMaterializeResponse,
)

router = APIRouter(prefix="/api/v1/thinker", tags=["thinker"])

_job_store: InMemoryThinkerJobStore | None = None


def _get_job_store() -> InMemoryThinkerJobStore:
    global _job_store
    if _job_store is None:
        _job_store = InMemoryThinkerJobStore()
    return _job_store


@router.post("/jobs", response_model=ThinkerJobCreateResponse)
async def create_job(body: ThinkerJobCreateRequest) -> ThinkerJobCreateResponse:
    job = _get_job_store().create_job(
        mode=body.mode,
        research_direction=body.research_direction,
    )
    return ThinkerJobCreateResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=ThinkerJobStatusResponse)
async def get_job(job_id: str) -> ThinkerJobStatusResponse:
    try:
        job = _get_job_store().get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thinker job not found") from exc

    return ThinkerJobStatusResponse(
        job_id=job.job_id,
        mode=job.mode,
        research_direction=job.research_direction,
        status=job.status,
        error_code=job.error_code,
        error_message=job.error_message,
    )


@router.post("/materialize", response_model=ThinkerMaterializeResponse)
async def materialize_job(body: ThinkerMaterializeRequest) -> ThinkerMaterializeResponse:
    try:
        job = _get_job_store().get_job(body.job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thinker job not found") from exc

    if job.status != "succeeded":
        raise HTTPException(
            status_code=409,
            detail="Thinker job is not ready to materialize",
        )

    return ThinkerMaterializeResponse(
        job_id=job.job_id,
        status=job.status,
        payload=ThinkerMaterializedPayload(
            final_topics=body.adopted.expanded_topics,
            final_seed_text=body.adopted.enriched_seed_text,
            final_simulation_requirement=body.adopted.suggested_simulation_prompt,
        ),
    )
