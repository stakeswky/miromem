"""Configuration for the internal graph-service package."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphServiceSettings(BaseSettings):
    """Environment-backed settings for the Graphiti graph service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    graph_backend: str = "graphiti"
    graph_service_host: str = "0.0.0.0"
    graph_service_port: int = 8001
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_database: str = "miromem_graph"
    falkordb_username: str = ""
    falkordb_password: str = ""
    graph_llm_api_key: str = ""
    graph_llm_base_url: str = ""
    graph_llm_model: str = "gpt-4o-mini"
    graph_embedding_api_key: str = ""
    graph_embedding_base_url: str = ""
    graph_embedding_model: str = "text-embedding-3-large"
    graph_embedding_dim: int = 3072
    graph_reranker_provider: str = "disabled"
    graph_reranker_api_key: str = ""
    graph_reranker_base_url: str = ""
    graph_reranker_model: str = ""


@lru_cache(maxsize=1)
def get_graph_service_settings() -> GraphServiceSettings:
    """Return a cached graph-service settings instance."""
    return GraphServiceSettings()
