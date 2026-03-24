"""Unified configuration for MiroMem system."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class EverMemOSConfig:
    """EverMemOS service connection settings."""

    host: str = field(default_factory=lambda: os.getenv("EVERMEMOS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("EVERMEMOS_PORT", "1995")))
    api_prefix: str = "/api/v1"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}{self.api_prefix}"


@dataclass
class MiroFishConfig:
    """MiroFish backend service connection settings."""

    host: str = field(default_factory=lambda: os.getenv("MIROFISH_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("MIROFISH_PORT", "5001")))

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class LLMConfig:
    """LLM provider settings (OpenAI-compatible)."""

    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))


@dataclass
class ThinkerConfig:
    """Thinker-specific LLM settings."""

    llm_api_key: str = field(default_factory=lambda: os.getenv("THINKER_LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("THINKER_LLM_BASE_URL", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("THINKER_LLM_MODEL", ""))


@dataclass
class InfraConfig:
    """Infrastructure connection settings."""

    mongodb_uri: str = field(default_factory=lambda: os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    mongodb_db: str = field(default_factory=lambda: os.getenv("MONGODB_DB", "miromem"))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))
    milvus_host: str = field(default_factory=lambda: os.getenv("MILVUS_HOST", "localhost"))
    milvus_port: int = field(default_factory=lambda: int(os.getenv("MILVUS_PORT", "19530")))
    es_url: str = field(default_factory=lambda: os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"))


@dataclass
class MiroMemConfig:
    """Root configuration aggregating all sub-configs."""

    evermemos: EverMemOSConfig = field(default_factory=EverMemOSConfig)
    mirofish: MiroFishConfig = field(default_factory=MiroFishConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    thinker: ThinkerConfig = field(default_factory=ThinkerConfig)
    infra: InfraConfig = field(default_factory=InfraConfig)
    gateway_port: int = field(default_factory=lambda: int(os.getenv("GATEWAY_PORT", "8000")))


def load_config() -> MiroMemConfig:
    """Load configuration from environment variables."""
    return MiroMemConfig()
