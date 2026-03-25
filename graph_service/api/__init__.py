"""Router exports for the internal graph-service API."""

from __future__ import annotations

from miromem.graph_service.api.graphs import router as graphs_router
from miromem.graph_service.api.health import router as health_router
from miromem.graph_service.api.jobs import router as jobs_router

__all__ = ["graphs_router", "health_router", "jobs_router"]
