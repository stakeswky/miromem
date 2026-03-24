"""MiroMem API Gateway - unified entry point routing to MiroFish and EverMemOS."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from miromem.config.settings import load_config
from miromem.evolution.api import router as evolution_router
from miromem.graph.api import router as graph_router
from miromem.thinker.api import router as thinker_router

config = load_config()
app = FastAPI(title="MiroMem Gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health Check ---


@app.get("/health")
async def health():
    """Gateway health check with downstream service status."""
    status = {"gateway": "ok", "evermemos": "unknown", "mirofish": "unknown"}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{config.evermemos.base_url.rsplit('/api', 1)[0]}/health")
            status["evermemos"] = "ok" if r.status_code == 200 else "error"
        except httpx.RequestError:
            status["evermemos"] = "unreachable"
        try:
            r = await client.get(f"{config.mirofish.base_url}/api/graph/project/list")
            status["mirofish"] = "ok" if r.status_code == 200 else "error"
        except httpx.RequestError:
            status["mirofish"] = "unreachable"
    return status


# --- Proxy: EverMemOS Memory API ---


@app.api_route("/api/v1/memories/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def proxy_evermemos(request: Request, path: str):
    """Proxy memory requests to EverMemOS."""
    return await _proxy(request, config.evermemos.base_url, f"/memories/{path}")


# --- Proxy: MiroFish Graph API ---


@app.api_route("/api/graph/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_mirofish_graph(request: Request, path: str):
    """Proxy graph requests to MiroFish backend."""
    return await _proxy(request, config.mirofish.base_url, f"/api/graph/{path}")


# --- Proxy: MiroFish Simulation API ---


@app.api_route("/api/simulation/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_mirofish_simulation(request: Request, path: str):
    """Proxy simulation requests to MiroFish backend."""
    return await _proxy(request, config.mirofish.base_url, f"/api/simulation/{path}")


# --- Proxy: MiroFish Report API ---


@app.api_route("/api/report/{path:path}", methods=["GET", "POST"])
async def proxy_mirofish_report(request: Request, path: str):
    """Proxy report requests to MiroFish backend."""
    return await _proxy(request, config.mirofish.base_url, f"/api/report/{path}")


# --- Proxy: MiroFish Polymarket API ---


@app.api_route("/api/polymarket/{path:path}", methods=["GET"])
async def proxy_mirofish_polymarket(request: Request, path: str):
    """Proxy Polymarket requests to MiroFish backend."""
    return await _proxy(request, config.mirofish.base_url, f"/api/polymarket/{path}")


# --- MiroMem Native: Knowledge Graph Extension ---

app.include_router(graph_router)


# --- MiroMem Native: Cross-Simulation Evolution ---

app.include_router(evolution_router)


# --- MiroMem Native: Thinker Orchestration ---

app.include_router(thinker_router)


# --- Internal Proxy Helper ---


async def _proxy(request: Request, base_url: str, path: str) -> Response:
    """Forward request to downstream service and return response."""
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if request.query_params:
        url += f"?{request.query_params}"

    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                headers=headers,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Downstream service unreachable: {e}"}, status_code=502)
