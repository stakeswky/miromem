"""Tests for graph-service configuration loading."""

from __future__ import annotations

import graphiti_core.driver.falkordb_driver as falkordb_driver_module
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

import miromem.graph_service.core.graphiti_factory as graphiti_factory_module
from miromem.graph_service.core.config import GraphServiceSettings
from miromem.graph_service.core.providers import (
    build_embedder,
    build_graph_driver,
    build_llm_client,
    build_reranker,
)


def _stub_falkordb(monkeypatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    class FakeFalkorDB:
        def __init__(self, host, port, username=None, password=None):
            captured["host"] = host
            captured["port"] = port
            captured["username"] = username
            captured["password"] = password

        def select_graph(self, name):
            captured["database"] = name
            return object()

    monkeypatch.setattr(falkordb_driver_module, "FalkorDB", FakeFalkorDB)
    return captured


def test_graph_service_settings_load_graphiti_fields(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    monkeypatch.setenv("GRAPH_SERVICE_PORT", "8010")
    monkeypatch.setenv("FALKORDB_HOST", "falkor")

    settings = GraphServiceSettings()

    assert settings.graph_backend == "graphiti"
    assert settings.graph_service_port == 8010
    assert settings.falkordb_host == "falkor"


def test_build_graph_driver_uses_falkor(monkeypatch):
    captured = _stub_falkordb(monkeypatch)
    settings = GraphServiceSettings(
        falkordb_host="falkor",
        falkordb_port=6379,
        falkordb_database="mirofish_graphs",
    )

    driver = build_graph_driver(settings)

    assert driver.provider.value == "falkordb"
    assert driver._database == "mirofish_graphs"
    assert captured == {
        "host": "falkor",
        "port": 6379,
        "username": None,
        "password": None,
    }


def test_build_llm_client_uses_openai_compatible_settings():
    settings = GraphServiceSettings(
        graph_llm_api_key="key",
        graph_llm_base_url="https://llm.example.com/v1",
        graph_llm_model="Qwen/Qwen2.5-72B-Instruct",
    )

    llm_client = build_llm_client(settings)

    assert isinstance(llm_client, OpenAIGenericClient)
    assert llm_client.config.api_key == "key"
    assert llm_client.config.base_url == "https://llm.example.com/v1"
    assert llm_client.config.model == "Qwen/Qwen2.5-72B-Instruct"


def test_build_embedder_uses_openai_compatible_settings():
    settings = GraphServiceSettings(
        graph_embedding_api_key="key",
        graph_embedding_base_url="https://embed.example.com/v1",
        graph_embedding_model="Qwen/Qwen3-Embedding-0.6B",
        graph_embedding_dim=1024,
    )

    embedder = build_embedder(settings)

    assert embedder.config.api_key == "key"
    assert embedder.config.base_url == "https://embed.example.com/v1"
    assert embedder.config.embedding_model == "Qwen/Qwen3-Embedding-0.6B"
    assert embedder.config.embedding_dim == 1024


def test_build_reranker_returns_none_when_unconfigured():
    settings = GraphServiceSettings(
        graph_reranker_model="",
    )

    assert build_reranker(settings) is None


def test_build_graphiti_passes_through_optional_reranker(monkeypatch):
    captured: dict[str, object] = {}
    driver = object()
    llm_client = object()
    embedder = object()

    class FakeGraphiti:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(graphiti_factory_module, "Graphiti", FakeGraphiti)
    monkeypatch.setattr(graphiti_factory_module, "build_graph_driver", lambda settings: driver)
    monkeypatch.setattr(graphiti_factory_module, "build_llm_client", lambda settings: llm_client)
    monkeypatch.setattr(graphiti_factory_module, "build_embedder", lambda settings: embedder)
    monkeypatch.setattr(graphiti_factory_module, "build_reranker", lambda settings: None)

    graphiti = graphiti_factory_module.build_graphiti(GraphServiceSettings())

    assert isinstance(graphiti, FakeGraphiti)
    assert captured["graph_driver"] is driver
    assert captured["llm_client"] is llm_client
    assert captured["embedder"] is embedder
    assert captured["cross_encoder"] is None
