"""Graphiti bootstrap helpers for the internal graph-service package."""

from __future__ import annotations

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.client import CrossEncoderClient

from miromem.graph_service.core.config import GraphServiceSettings
from miromem.graph_service.core.providers import (
    build_embedder,
    build_graph_driver,
    build_llm_client,
    build_reranker,
)


class DisabledReranker(CrossEncoderClient):
    """No-op reranker to prevent Graphiti from instantiating its default OpenAI reranker."""

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        return [(passage, 0.0) for passage in passages]


def build_graphiti(settings: GraphServiceSettings) -> Graphiti:
    """Build a Graphiti instance backed by FalkorDB and OpenAI-compatible providers."""
    reranker = build_reranker(settings)

    return Graphiti(
        graph_driver=build_graph_driver(settings),
        llm_client=build_llm_client(settings),
        embedder=build_embedder(settings),
        cross_encoder=reranker if reranker is not None else DisabledReranker(),
    )
