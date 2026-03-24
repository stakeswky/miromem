"""Provider-backed Thinker orchestration flows."""

from __future__ import annotations

from typing import Any

from miromem.thinker.models import (
    ThinkerPolymarketEvent,
    ThinkerReference,
    ThinkerResult,
    ThinkerUploadedFile,
)
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
        seed_text: str = "",
        uploaded_files: list[ThinkerUploadedFile | dict[str, Any]] | None = None,
        polymarket_event: ThinkerPolymarketEvent | dict[str, Any] | None = None,
        **_: object,
    ) -> ThinkerResult:
        """Run the requested Thinker flow and return a normalized result."""
        if mode == "topic_only":
            return await self._run_topic_only(research_direction=research_direction)
        if mode == "upload":
            return await self._run_upload(
                research_direction=research_direction,
                seed_text=seed_text,
                uploaded_files=uploaded_files or [],
            )
        if mode == "polymarket":
            return await self._run_polymarket(
                research_direction=research_direction,
                polymarket_event=polymarket_event or {},
            )

        raise ValueError(f"Unsupported mode: {mode}")

    async def _run_topic_only(self, *, research_direction: str) -> ThinkerResult:
        evidence, references = await self._collect_topic_evidence(research_direction)
        return await self._finalize_result(
            research_direction=research_direction,
            evidence=evidence,
            references=references,
            meta_defaults={
                "evidence_preview": evidence[:2],
                "search_hits_count": len(references),
            },
        )

    async def _run_upload(
        self,
        *,
        research_direction: str,
        seed_text: str,
        uploaded_files: list[ThinkerUploadedFile | dict[str, Any]],
    ) -> ThinkerResult:
        normalized_files = [
            self._coerce_uploaded_file(raw_file)
            for raw_file in uploaded_files
        ]
        evidence = [file.text.strip() for file in normalized_files if file.text.strip()]
        if not evidence and seed_text.strip():
            evidence = [seed_text.strip()]

        references = [
            ThinkerReference(
                title=file.name,
                url="",
                source_type="upload",
            )
            for file in normalized_files
        ]
        return await self._finalize_result(
            research_direction=research_direction,
            evidence=evidence,
            references=references,
            meta_defaults={
                "evidence_preview": self._preview_evidence(evidence),
                "uploaded_files_count": len(normalized_files),
            },
        )

    async def _run_polymarket(
        self,
        *,
        research_direction: str,
        polymarket_event: ThinkerPolymarketEvent | dict[str, Any],
    ) -> ThinkerResult:
        raw_event = (
            polymarket_event.model_dump()
            if isinstance(polymarket_event, ThinkerPolymarketEvent)
            else dict(polymarket_event)
        )
        normalized = await self.polymarket_provider.normalize_event(event=raw_event)
        event = ThinkerPolymarketEvent.model_validate(normalized)
        evidence = self._build_polymarket_evidence(event)
        references = [
            ThinkerReference(
                title=event.title or research_direction,
                url=event.url,
                source_type="polymarket",
            )
        ]
        return await self._finalize_result(
            research_direction=research_direction,
            evidence=evidence,
            references=references,
            meta_defaults={
                "evidence_preview": self._preview_evidence(evidence),
                "polymarket_event_title": event.title,
            },
        )

    async def _finalize_result(
        self,
        *,
        research_direction: str,
        evidence: list[str],
        references: list[ThinkerReference],
        meta_defaults: dict[str, Any],
    ) -> ThinkerResult:
        result = await self.llm_provider.generate_research_bundle(
            research_direction=research_direction,
            evidence=evidence,
        )
        meta = dict(result.meta)
        for key, value in meta_defaults.items():
            meta.setdefault(key, value)

        return result.model_copy(
            update={
                "references": result.references or references,
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

    def _coerce_uploaded_file(
        self,
        raw_file: ThinkerUploadedFile | dict[str, Any],
    ) -> ThinkerUploadedFile:
        if isinstance(raw_file, ThinkerUploadedFile):
            return raw_file
        return ThinkerUploadedFile.model_validate(raw_file)

    def _build_polymarket_evidence(self, event: ThinkerPolymarketEvent) -> list[str]:
        if event.summary.strip():
            return [event.summary.strip()]

        evidence = [
            part.strip()
            for part in (event.title, event.description, ", ".join(event.outcomes))
            if part and part.strip()
        ]
        return evidence

    def _preview_evidence(self, evidence: list[str]) -> str:
        return "\n\n".join(evidence[:2])
