"""Polymarket provider protocol and thin normalization adapter for Thinker."""

from __future__ import annotations

from typing import Any, Protocol


class PolymarketProvider(Protocol):
    """Provider contract for normalizing external Polymarket event payloads."""

    async def normalize_event(self, *, event: dict[str, Any]) -> dict[str, Any]:
        """Return a gateway-friendly normalized event payload."""


class DefaultPolymarketProvider:
    """Normalize existing event payloads without fetching external data."""

    async def normalize_event(self, *, event: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": str(event.get("title", "")),
            "description": str(event.get("description", "")),
            "outcomes": list(event.get("outcomes", [])),
            "raw": event,
        }
