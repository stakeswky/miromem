"""Provider-backed Thinker orchestration flows."""

from __future__ import annotations

from miromem.thinker.models import ThinkerReference, ThinkerResult
from miromem.thinker.providers import (
    DefaultPolymarketProvider,
    HTTPScrapeProvider,
    HTTPSearchProvider,
    LLMProvider,
    OpenAILLMProvider,
    PolymarketProvider,
    ScrapeProvider,
    SearchHit,
    SearchProvider,
)


class ThinkerOrchestrator:
    """Run Thinker research workflows using replaceable providers."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider | None = None,
        search_provider: SearchProvider | None = None,
        scrape_provider: ScrapeProvider | None = None,
        polymarket_provider: PolymarketProvider | None = None,
        max_search_results: int = 3,
    ) -> None:
        self._llm_provider = llm_provider
        self._search_provider = search_provider
        self._scrape_provider = scrape_provider
        self._polymarket_provider = polymarket_provider
        self._max_search_results = max_search_results

    @property
    def llm_provider(self) -> LLMProvider:
        if self._llm_provider is None:
            self._llm_provider = OpenAILLMProvider()
        return self._llm_provider

    @property
    def search_provider(self) -> SearchProvider:
        if self._search_provider is None:
            self._search_provider = HTTPSearchProvider()
        return self._search_provider

    @property
    def scrape_provider(self) -> ScrapeProvider:
        if self._scrape_provider is None:
            self._scrape_provider = HTTPScrapeProvider()
        return self._scrape_provider

    @property
    def polymarket_provider(self) -> PolymarketProvider:
        if self._polymarket_provider is None:
            self._polymarket_provider = DefaultPolymarketProvider()
        return self._polymarket_provider

    async def run(
        self,
        *,
        mode: str,
        research_direction: str,
        **_: object,
    ) -> ThinkerResult:
        """Run the requested Thinker flow and return a normalized result."""
        if mode == "topic_only":
            return await self._run_topic_only(research_direction=research_direction)

        raise ValueError(f"Unsupported mode: {mode}")

    async def _run_topic_only(self, *, research_direction: str) -> ThinkerResult:
        evidence, references = await self._collect_topic_evidence(research_direction)
        result = await self.llm_provider.generate_research_bundle(
            research_direction=research_direction,
            evidence=evidence,
        )

        if result.references:
            final_references = result.references
        else:
            final_references = references

        meta = dict(result.meta)
        meta.setdefault("evidence_preview", evidence[:2])
        meta.setdefault("search_hits_count", len(references))

        return result.model_copy(
            update={
                "references": final_references,
                "meta": meta,
            }
        )

    async def _collect_topic_evidence(
        self,
        research_direction: str,
    ) -> tuple[list[str], list[ThinkerReference]]:
        raw_hits = await self.search_provider.search(query=research_direction)
        hits = [
            self._coerce_search_hit(raw_hit)
            for raw_hit in raw_hits[: self._max_search_results]
        ]

        evidence: list[str] = []
        references: list[ThinkerReference] = []
        for hit in hits:
            references.append(
                ThinkerReference(
                    title=hit.title,
                    url=hit.url,
                    source_type="web",
                )
            )
            summary = await self.scrape_provider.summarize(url=hit.url)
            evidence_text = " | ".join(
                part.strip()
                for part in (hit.title, hit.snippet, summary)
                if part and part.strip()
            )
            if evidence_text:
                evidence.append(evidence_text)

        return evidence, references

    def _coerce_search_hit(self, raw_hit: SearchHit | dict[str, str]) -> SearchHit:
        if isinstance(raw_hit, SearchHit):
            return raw_hit
        return SearchHit.model_validate(raw_hit)
