"""Graphiti bootstrap helpers for the internal graph-service package."""

from __future__ import annotations

from graphiti_core import Graphiti

from miromem.graph_service.core.config import GraphServiceSettings
from miromem.graph_service.core.providers import (
    build_embedder,
    build_graph_driver,
    build_llm_client,
    build_reranker,
)


def build_graphiti(settings: GraphServiceSettings) -> Graphiti:
    """Build a Graphiti instance backed by FalkorDB and OpenAI-compatible providers."""
    return Graphiti(
        graph_driver=build_graph_driver(settings),
        llm_client=build_llm_client(settings),
        embedder=build_embedder(settings),
        cross_encoder=build_reranker(settings),
    )
