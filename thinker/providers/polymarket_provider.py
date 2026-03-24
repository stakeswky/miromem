"""Polymarket provider protocol and thin normalization adapter for Thinker."""

from __future__ import annotations

import json
from typing import Any, Protocol


class PolymarketProvider(Protocol):
    """Provider contract for normalizing external Polymarket event payloads."""

    async def normalize_event(self, *, event: dict[str, Any]) -> dict[str, Any]:
        """Return a gateway-friendly normalized event payload."""


class DefaultPolymarketProvider:
    """Normalize existing event payloads without fetching external data."""

    async def normalize_event(self, *, event: dict[str, Any]) -> dict[str, Any]:
        title = _first_text(event, "title", "question", "name")
        description = _first_text(event, "description", "subtitle")
        outcomes = _normalize_outcomes(event.get("outcomes"))
        market_summaries = _normalize_market_summaries(event.get("markets"))
        summary_parts = [title, description]
        summary_parts.extend(market_summaries)

        return {
            "title": title,
            "description": description,
            "outcomes": outcomes,
            "url": _normalize_url(event),
            "summary": " | ".join(part for part in summary_parts if part),
            "raw": event,
        }


def _first_text(event: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = event.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_outcomes(raw_outcomes: Any) -> list[str]:
    if isinstance(raw_outcomes, list):
        return [str(outcome).strip() for outcome in raw_outcomes if str(outcome).strip()]
    if raw_outcomes is None:
        return []
    if isinstance(raw_outcomes, str):
        text = raw_outcomes.strip()
        if not text:
            return []
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return [text]
        if isinstance(decoded, list):
            return [str(outcome).strip() for outcome in decoded if str(outcome).strip()]
        if decoded is None:
            return []
        decoded_text = str(decoded).strip()
        return [decoded_text] if decoded_text else []
    text = str(raw_outcomes).strip()
    return [text] if text else []


def _normalize_market_summaries(raw_markets: Any) -> list[str]:
    if not isinstance(raw_markets, list):
        return []

    summaries: list[str] = []
    for market in raw_markets:
        if not isinstance(market, dict):
            continue
        question = _first_text(market, "question", "title")
        outcomes = _normalize_outcomes(market.get("outcomes"))
        if question and outcomes:
            summaries.append(f"{question} ({', '.join(outcomes)})")
            continue
        if question:
            summaries.append(question)
    return summaries


def _normalize_url(event: dict[str, Any]) -> str:
    explicit_url = _first_text(event, "url")
    if explicit_url:
        return explicit_url

    slug = _first_text(event, "slug", "event_slug")
    if slug:
        return f"https://polymarket.com/event/{slug}"

    return ""
