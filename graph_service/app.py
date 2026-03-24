"""FastAPI app for the internal Graphiti-backed graph service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from miromem.graph_service.api import graphs_router, health_router, jobs_router
from miromem.graph_service.core.config import GraphServiceSettings, get_graph_service_settings
from miromem.graph_service.storage.graph_metadata_store import InMemoryGraphMetadataStore
from miromem.graph_service.storage.job_store import InMemoryGraphJobStore
from miromem.graph_service.workers.build_worker import BuildWorker


def create_app(settings: GraphServiceSettings | None = None) -> FastAPI:
    """Create a graph-service app with in-memory stores for v1."""
    service_settings = settings or get_graph_service_settings()
    job_store = InMemoryGraphJobStore()
    metadata_store = InMemoryGraphMetadataStore()
    build_worker = BuildWorker(
        settings=service_settings,
        job_store=job_store,
        metadata_store=metadata_store,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            app.state.build_worker.shutdown()

    app = FastAPI(title="MiroMem Graph Service", version="0.1.0", lifespan=lifespan)
    app.state.settings = service_settings
    app.state.job_store = job_store
    app.state.graph_metadata_store = metadata_store
    app.state.build_worker = build_worker
    app.include_router(graphs_router)
    app.include_router(jobs_router)
    app.include_router(health_router)
    return app


app = create_app()
