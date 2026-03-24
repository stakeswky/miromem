"""Scrape provider protocol and HTTP implementation for Thinker."""

from __future__ import annotations

import os
from typing import Protocol

import httpx


class ScrapeProvider(Protocol):
    """Provider contract for summarizing a page into compact evidence."""

    async def summarize(self, *, url: str) -> str:
        """Return a textual summary for the given URL."""


class HTTPScrapeProvider:
    """Simple HTTP scrape adapter driven by THINKER_SCRAPE_* settings."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url or os.getenv("THINKER_SCRAPE_BASE_URL", "")
        self._api_key = api_key or os.getenv("THINKER_SCRAPE_API_KEY", "")

        missing = [
            name
            for name, value in (
                ("THINKER_SCRAPE_BASE_URL", self._base_url),
                ("THINKER_SCRAPE_API_KEY", self._api_key),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Thinker scrape provider is not configured: missing {joined}")

        self._client = client or httpx.AsyncClient(timeout=20.0)

    async def summarize(self, *, url: str) -> str:
        response = await self._client.post(
            self._base_url,
            json={"url": url},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            summary = payload.get("summary") or payload.get("content") or payload.get("text") or ""
            return str(summary)
        return ""
