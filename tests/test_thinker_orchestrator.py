"""Tests for topic-only Thinker orchestration."""

from __future__ import annotations

import pytest

from miromem.thinker.models import ThinkerResult
from miromem.thinker.orchestrator import ThinkerOrchestrator
from miromem.thinker.providers import SearchHit


class FakeLLMProvider:
    async def generate_research_bundle(
        self,
        *,
        research_direction: str,
        evidence: list[str],
    ) -> ThinkerResult:
        return ThinkerResult(
            expanded_topics=["Fed policy path", "Q3 macro conditions"],
            enriched_seed_text=f"{research_direction}\n\n" + "\n".join(evidence),
            suggested_simulation_prompt="Simulate analysts debating the Fed path in Q3.",
        )


class FakeSearchProvider:
    async def search(self, *, query: str) -> list[SearchHit]:
        return [
            SearchHit(title="Fed watch", url="https://example.com/fed"),
            SearchHit(title="Macro note", url="https://example.com/macro"),
        ]


class FakeScrapeProvider:
    async def summarize(self, *, url: str) -> str:
        return f"summary for {url}"


class FakePolymarketProvider:
    async def normalize_event(self, *, event: dict[str, object]) -> dict[str, object]:
        return event


@pytest.mark.asyncio
async def test_topic_only_job_produces_topics_seed_and_prompt():
    orchestrator = ThinkerOrchestrator(
        llm_provider=FakeLLMProvider(),
        search_provider=FakeSearchProvider(),
        scrape_provider=FakeScrapeProvider(),
        polymarket_provider=FakePolymarketProvider(),
    )

    result = await orchestrator.run(
        mode="topic_only",
        research_direction="Will the Fed keep tightening in Q3?",
    )

    assert result.expanded_topics
    assert result.enriched_seed_text
    assert result.suggested_simulation_prompt


@pytest.mark.asyncio
async def test_upload_mode_prefers_uploaded_text_as_evidence():
    orchestrator = ThinkerOrchestrator(
        llm_provider=FakeLLMProvider(),
        search_provider=FakeSearchProvider(),
        scrape_provider=FakeScrapeProvider(),
        polymarket_provider=FakePolymarketProvider(),
    )

    result = await orchestrator.run(
        mode="upload",
        research_direction="Fed outlook",
        seed_text="Uploaded memo text",
        uploaded_files=[{"name": "fed.pdf", "text": "Uploaded memo text"}],
    )

    assert "Uploaded memo text" in result.meta["evidence_preview"]


@pytest.mark.asyncio
async def test_polymarket_mode_normalizes_selected_event():
    orchestrator = ThinkerOrchestrator(
        llm_provider=FakeLLMProvider(),
        search_provider=FakeSearchProvider(),
        scrape_provider=FakeScrapeProvider(),
        polymarket_provider=FakePolymarketProvider(),
    )

    result = await orchestrator.run(
        mode="polymarket",
        research_direction="Election pricing drift",
        polymarket_event={"title": "Will X win?", "description": "Market event"},
    )

    assert result.references
