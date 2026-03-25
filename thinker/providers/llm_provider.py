"""LLM provider protocol and OpenAI-compatible implementation for Thinker."""

from __future__ import annotations

import json
import os
from typing import Protocol

from openai import AsyncOpenAI

from miromem.thinker.models import ThinkerReference, ThinkerResult


class LLMProvider(Protocol):
    """Provider contract for generating a normalized research bundle."""

    async def generate_research_bundle(
        self,
        *,
        research_direction: str,
        evidence: list[str],
    ) -> ThinkerResult:
        """Return Thinker output for a research direction and collected evidence."""


class OpenAILLMProvider:
    """OpenAI-compatible LLM adapter driven by THINKER_LLM_* settings."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("THINKER_LLM_API_KEY", "")
        self._base_url = base_url or os.getenv("THINKER_LLM_BASE_URL", "")
        self._model = model or os.getenv("THINKER_LLM_MODEL", "")

        missing = [
            name
            for name, value in (
                ("THINKER_LLM_API_KEY", self._api_key),
                ("THINKER_LLM_BASE_URL", self._base_url),
                ("THINKER_LLM_MODEL", self._model),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Thinker LLM provider is not configured: missing {joined}")

        self._client = client or AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)

    async def generate_research_bundle(
        self,
        *,
        research_direction: str,
        evidence: list[str],
    ) -> ThinkerResult:
        evidence_block = "\n".join(f"- {item}" for item in evidence) or "- No evidence collected."
        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Thinker, a research planning assistant. "
                        "Return JSON with keys expanded_topics, enriched_seed_text, "
                        "suggested_simulation_prompt, references, and meta."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Research direction:\n{research_direction}\n\n"
                        f"Evidence:\n{evidence_block}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)

        references = [
            ThinkerReference(
                title=reference.get("title", reference.get("url", "reference")),
                url=reference.get("url", ""),
                source_type=reference.get("source_type", "web"),
            )
            for reference in payload.get("references", [])
            if isinstance(reference, dict)
        ]

        return ThinkerResult(
            expanded_topics=[str(topic) for topic in payload.get("expanded_topics", [])],
            enriched_seed_text=str(payload.get("enriched_seed_text", "")),
            suggested_simulation_prompt=str(payload.get("suggested_simulation_prompt", "")),
            references=references,
            meta=payload.get("meta", {}) if isinstance(payload.get("meta", {}), dict) else {},
        )
