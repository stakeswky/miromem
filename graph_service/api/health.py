"""Health routes for the internal graph-service API."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    """Return a minimal liveness signal."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(request: Request) -> dict[str, str]:
    """Return a minimal readiness signal for the current backend."""
    return {
        "status": "ok",
        "graph_backend": request.app.state.settings.graph_backend,
    }
