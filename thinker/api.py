"""Thinker API endpoints for the gateway skeleton."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError

from miromem.thinker.file_ingest import extract_uploads
from miromem.thinker.jobs import InMemoryThinkerJobStore
from miromem.thinker.materializer import ThinkerMaterializer
from miromem.thinker.models import (
    ThinkerAdoptedInput,
    ThinkerJob,
    ThinkerJobAction,
    ThinkerJobStatus,
    ThinkerMode,
    ThinkerMaterializedPayload,
    ThinkerResult,
    ThinkerUploadedFile,
    thinker_available_actions,
)
from miromem.thinker.orchestrator import ThinkerOrchestrator

router = APIRouter(prefix="/api/v1/thinker", tags=["thinker"])

_job_store: InMemoryThinkerJobStore | None = None
_orchestrator: ThinkerOrchestrator | None = None
_materializer: ThinkerMaterializer | None = None


def _get_job_store() -> InMemoryThinkerJobStore:
    global _job_store
    if _job_store is None:
        _job_store = InMemoryThinkerJobStore()
    return _job_store


def _get_orchestrator() -> ThinkerOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ThinkerOrchestrator()
    return _orchestrator


def _get_materializer() -> ThinkerMaterializer:
    global _materializer
    if _materializer is None:
        _materializer = ThinkerMaterializer()
    return _materializer


class ThinkerJobCreateRequest(BaseModel):
    mode: ThinkerMode
    research_direction: str
    seed_text: str = ""
    uploaded_files: list[ThinkerUploadedFile] = Field(default_factory=list)
    polymarket_event: dict[str, Any] | None = None


class ThinkerJobCreateResponse(BaseModel):
    job_id: str
    status: ThinkerJobStatus


class ThinkerJobStatusResponse(BaseModel):
    job_id: str
    mode: str
    research_direction: str
    status: ThinkerJobStatus
    result: ThinkerResult | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool | None = None
    available_actions: list[ThinkerJobAction] = Field(default_factory=list)
    can_continue_without_thinker: bool = True


class ThinkerMaterializeRequest(BaseModel):
    job_id: str
    adopted: ThinkerAdoptedInput = Field(default_factory=ThinkerAdoptedInput)


class ThinkerMaterializeResponse(BaseModel):
    job_id: str
    status: ThinkerJobStatus
    payload: ThinkerMaterializedPayload


@router.post("/jobs", response_model=ThinkerJobCreateResponse)
async def create_job(request: Request) -> ThinkerJobCreateResponse:
    body = await _parse_job_create_request(request)
    job = _get_job_store().create_job(
        mode=body.mode,
        research_direction=body.research_direction,
        seed_text=body.seed_text,
        uploaded_files=body.uploaded_files,
        polymarket_event=body.polymarket_event,
    )
    asyncio.create_task(
        _execute_job(
            job.job_id,
            mode=body.mode,
            research_direction=body.research_direction,
            seed_text=body.seed_text,
            uploaded_files=body.uploaded_files,
            polymarket_event=body.polymarket_event,
        )
    )
    return ThinkerJobCreateResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=ThinkerJobStatusResponse)
async def get_job(job_id: str) -> ThinkerJobStatusResponse:
    try:
        job = _get_job_store().get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thinker job not found") from exc

    return _build_job_status_response(job)


@router.post("/materialize", response_model=ThinkerMaterializeResponse)
async def materialize_job(body: ThinkerMaterializeRequest) -> ThinkerMaterializeResponse:
    try:
        current_job = _get_job_store().get_job(body.job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thinker job not found") from exc
    if current_job.status != "succeeded":
        raise HTTPException(
            status_code=409,
            detail="Thinker job is not ready to materialize",
        )
    try:
        payload = _get_materializer().materialize(
            result=current_job.result,
            adopted=body.adopted,
        )
        job = _get_job_store().mark_materialized(body.job_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ThinkerMaterializeResponse(
        job_id=job.job_id,
        status=job.status,
        payload=payload,
    )


@router.post("/jobs/{job_id}/retry", response_model=ThinkerJobStatusResponse)
async def retry_job(job_id: str) -> ThinkerJobStatusResponse:
    store = _get_job_store()
    try:
        job = store.retry_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thinker job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Thinker job cannot be retried") from exc

    asyncio.create_task(
        _execute_job(
            job.job_id,
            mode=job.mode,
            research_direction=job.research_direction,
            seed_text=job.seed_text,
            uploaded_files=job.uploaded_files,
            polymarket_event=job.polymarket_event,
        )
    )
    return _build_job_status_response(job)


@router.post("/jobs/{job_id}/skip", response_model=ThinkerJobStatusResponse)
async def skip_job(job_id: str) -> ThinkerJobStatusResponse:
    try:
        job = _get_job_store().mark_skipped(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thinker job not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Thinker job cannot be skipped") from exc

    return _build_job_status_response(job)


async def _execute_job(
    job_id: str,
    *,
    mode: ThinkerMode,
    research_direction: str,
    seed_text: str = "",
    uploaded_files: list[ThinkerUploadedFile] | None = None,
    polymarket_event: dict[str, Any] | None = None,
) -> None:
    store = _get_job_store()
    try:
        store.mark_running(job_id)
        result = await _get_orchestrator().run(
            mode=mode,
            research_direction=research_direction,
            seed_text=seed_text,
            uploaded_files=uploaded_files or [],
            polymarket_event=polymarket_event,
        )
    except Exception as exc:
        error_code, retryable = _classify_job_error(exc)
        store.mark_failed(
            job_id,
            error_code=error_code,
            error_message=str(exc) or exc.__class__.__name__,
            retryable=retryable,
            can_continue_without_thinker=True,
        )
        return

    store.mark_succeeded(job_id, result=result)


def _classify_job_error(exc: Exception) -> tuple[str, bool]:
    message = str(exc).lower()
    if isinstance(exc, ValueError) and message.startswith("unsupported mode:"):
        return "unsupported_mode", False
    if isinstance(exc, RuntimeError) and "not configured" in message:
        return "provider_misconfigured", False
    if exc.__class__.__module__.startswith(("httpx", "openai")):
        return "provider_unavailable", True
    return "thinker_execution_failed", True


def _build_job_status_response(job: ThinkerJob) -> ThinkerJobStatusResponse:
    return ThinkerJobStatusResponse(
        job_id=job.job_id,
        mode=job.mode,
        research_direction=job.research_direction,
        status=job.status,
        result=job.result,
        error_code=job.error_code,
        error_message=job.error_message,
        retryable=job.retryable,
        available_actions=thinker_available_actions(
            status=job.status,
            retryable=job.retryable,
            can_continue_without_thinker=job.can_continue_without_thinker,
        ),
        can_continue_without_thinker=job.can_continue_without_thinker,
    )


async def _parse_job_create_request(request: Request) -> ThinkerJobCreateRequest:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        return await _parse_multipart_job_create_request(request)

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Thinker job payload") from exc

    return _validate_job_create_request(payload)


async def _parse_multipart_job_create_request(request: Request) -> ThinkerJobCreateRequest:
    form = await request.form()
    payload: dict[str, Any] = {
        "mode": form.get("mode"),
        "research_direction": form.get("research_direction"),
        "seed_text": form.get("seed_text", ""),
        "uploaded_files": [],
        "polymarket_event": None,
    }

    polymarket_event = form.get("polymarket_event")
    if polymarket_event not in (None, ""):
        if not isinstance(polymarket_event, str):
            raise HTTPException(
                status_code=400,
                detail="polymarket_event must be JSON text in multipart requests",
            )
        try:
            payload["polymarket_event"] = json.loads(polymarket_event)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail="polymarket_event must be valid JSON",
            ) from exc

    files = [
        candidate
        for key, candidate in form.multi_items()
        if key == "files" and hasattr(candidate, "filename")
    ]
    if payload["mode"] == "upload":
        try:
            payload["uploaded_files"] = await extract_uploads(files)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _validate_job_create_request(payload)


def _validate_job_create_request(payload: Any) -> ThinkerJobCreateRequest:
    try:
        body = ThinkerJobCreateRequest.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    if (
        body.mode == "upload"
        and not body.seed_text.strip()
        and not any(file.text.strip() for file in body.uploaded_files)
    ):
        raise HTTPException(
            status_code=422,
            detail="upload mode requires non-empty seed_text or at least one uploaded file with text",
        )
    if body.mode == "polymarket" and not body.polymarket_event:
        raise HTTPException(
            status_code=422,
            detail="polymarket_event is required when mode='polymarket'",
        )
    return body
