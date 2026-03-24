"""Provider factory helpers for Graphiti service bootstrap."""

from __future__ import annotations

from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb_driver import FalkorDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

from miromem.graph_service.core.config import GraphServiceSettings


def _clean_base_url(value: str) -> str | None:
    """Normalize blank OpenAI-compatible base URLs to None."""
    cleaned = value.strip()
    return cleaned or None


def build_graph_driver(settings: GraphServiceSettings) -> FalkorDriver:
    """Build the FalkorDB driver used by Graphiti."""
    return FalkorDriver(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
        username=settings.falkordb_username or None,
        password=settings.falkordb_password or None,
        database=settings.falkordb_database,
    )


def build_llm_client(settings: GraphServiceSettings) -> OpenAIGenericClient:
    """Build the OpenAI-compatible LLM client used by Graphiti extraction."""
    config = LLMConfig(
        api_key=settings.graph_llm_api_key or "",
        base_url=_clean_base_url(settings.graph_llm_base_url),
        model=settings.graph_llm_model,
    )
    return OpenAIGenericClient(config=config)


def build_embedder(settings: GraphServiceSettings) -> OpenAIEmbedder:
    """Build the OpenAI-compatible embedder used by Graphiti."""
    config = OpenAIEmbedderConfig(
        api_key=settings.graph_embedding_api_key or "",
        base_url=_clean_base_url(settings.graph_embedding_base_url),
        embedding_model=settings.graph_embedding_model,
        embedding_dim=settings.graph_embedding_dim,
    )
    return OpenAIEmbedder(config=config)


def build_reranker(settings: GraphServiceSettings) -> OpenAIRerankerClient | None:
    """Build the optional OpenAI-compatible reranker for v1 search paths."""
    provider_name = settings.graph_reranker_provider.strip().lower()
    if provider_name in {"", "disabled", "custom"}:
        return None

    model_name = settings.graph_reranker_model.strip()
    if provider_name != "openai_compat" or not model_name:
        return None

    config = LLMConfig(
        api_key=settings.graph_reranker_api_key or "",
        base_url=_clean_base_url(settings.graph_reranker_base_url),
        model=model_name,
    )
    return OpenAIRerankerClient(config=config)
