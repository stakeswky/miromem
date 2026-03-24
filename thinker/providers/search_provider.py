"""Search provider protocol and HTTP implementation for Thinker."""

from __future__ import annotations

import os
from typing import Protocol

import httpx
from pydantic import BaseModel


class SearchHit(BaseModel):
    """Normalized search result used by the Thinker orchestrator."""

    title: str
    url: str
    snippet: str = ""


class SearchProvider(Protocol):
    """Provider contract for search results."""

    async def search(self, *, query: str) -> list[SearchHit]:
        """Return normalized search hits for the query."""


class HTTPSearchProvider:
    """Simple HTTP search adapter driven by THINKER_SEARCH_* settings."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url or os.getenv("THINKER_SEARCH_BASE_URL", "")
        self._api_key = api_key or os.getenv("THINKER_SEARCH_API_KEY", "")

        missing = [
            name
            for name, value in (
                ("THINKER_SEARCH_BASE_URL", self._base_url),
                ("THINKER_SEARCH_API_KEY", self._api_key),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Thinker search provider is not configured: missing {joined}")

        self._client = client or httpx.AsyncClient(timeout=20.0)

    async def search(self, *, query: str) -> list[SearchHit]:
        response = await self._client.post(
            self._base_url,
            json={"query": query},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = []
        if isinstance(payload, dict):
            raw_results = payload.get("results") or payload.get("items") or []
        elif isinstance(payload, list):
            raw_results = payload

        hits: list[SearchHit] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link") or ""
            if not url:
                continue
            hits.append(
                SearchHit(
                    title=str(item.get("title") or item.get("name") or url),
                    url=str(url),
                    snippet=str(item.get("snippet") or item.get("description") or ""),
                )
            )
        return hits
