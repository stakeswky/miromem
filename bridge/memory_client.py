"""Async HTTP client wrapping the EverMemOS REST API."""

from __future__ import annotations

from typing import Any

import httpx

from miromem.config.settings import MiroMemConfig, load_config


class EverMemClient:
    """Thin async wrapper around EverMemOS ``/api/v1`` endpoints."""

    def __init__(self, config: MiroMemConfig | None = None, timeout: float = 30.0) -> None:
        self._cfg = config or load_config()
        self._base = self._cfg.evermemos.base_url  # e.g. http://localhost:1995/api/v1
        self._timeout = timeout

    # -- helpers --

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=self._timeout)

    # -- public API --

    async def store_memory(
        self,
        user_id: str,
        message: str,
        role: str = "human",
        *,
        group_id: str | None = None,
        memory_type: str = "EpisodicMemory",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """POST /api/v1/memories — create a new memory."""
        payload: dict[str, Any] = {
            "user_id": user_id,
            "content": message,
            "memory_type": memory_type,
            "metadata": {**(metadata or {}), "role": role},
        }
        if group_id:
            payload["group_id"] = group_id
        async with self._client() as c:
            r = await c.post("/memories", json=payload)
            r.raise_for_status()
            return r.json()

    async def search_memories(
        self,
        query: str,
        user_id: str,
        *,
        method: str = "hybrid",
        memory_type: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """GET /api/v1/memories/search — search stored memories."""
        params: dict[str, Any] = {
            "query": query,
            "user_id": user_id,
            "method": method,
            "top_k": top_k,
        }
        if memory_type:
            params["memory_type"] = memory_type
        async with self._client() as c:
            r = await c.get("/memories/search", params=params)
            r.raise_for_status()
            return r.json()

    async def get_memories(
        self,
        user_id: str,
        *,
        memory_type: str | None = None,
        group_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """GET /api/v1/memories — retrieve memories for a user."""
        params: dict[str, Any] = {"user_id": user_id}
        if memory_type:
            params["memory_type"] = memory_type
        if group_id:
            params["group_id"] = group_id
        async with self._client() as c:
            r = await c.get("/memories", params=params)
            r.raise_for_status()
            return r.json()

    async def delete_memories(
        self,
        user_id: str,
        *,
        memory_type: str | None = None,
    ) -> dict[str, Any]:
        """DELETE /api/v1/memories — delete memories for a user."""
        params: dict[str, Any] = {"user_id": user_id}
        if memory_type:
            params["memory_type"] = memory_type
        async with self._client() as c:
            r = await c.delete("/memories", params=params)
            r.raise_for_status()
            return r.json()

    async def get_conversation_meta(self, user_id: str) -> dict[str, Any]:
        """GET /api/v1/memories/conversation-meta."""
        async with self._client() as c:
            r = await c.get("/memories/conversation-meta", params={"user_id": user_id})
            r.raise_for_status()
            return r.json()

    async def save_conversation_meta(self, user_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """POST /api/v1/memories/conversation-meta."""
        async with self._client() as c:
            r = await c.post("/memories/conversation-meta", json={"user_id": user_id, **metadata})
            r.raise_for_status()
            return r.json()

    async def health_check(self) -> dict[str, Any]:
        """GET /health on the EverMemOS root (not under /api/v1)."""
        root_url = self._base.rsplit("/api", 1)[0]
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(f"{root_url}/health")
            r.raise_for_status()
            return r.json()