"""Tests for graph-service configuration loading."""

from __future__ import annotations

from types import SimpleNamespace

import graphiti_core.driver.falkordb_driver as falkordb_driver_module
import graphiti_core.graphiti as runtime_graphiti_module
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.driver.falkordb.operations.entity_edge_ops import FalkorEntityEdgeOperations
from graphiti_core.driver.falkordb.operations.entity_node_ops import FalkorEntityNodeOperations
from graphiti_core.llm_client import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.prompts.extract_nodes import ExtractedEntities
from graphiti_core.prompts.models import Message
from graphiti_core.utils import bulk_utils as bulk_utils_module
import pytest

import miromem.graph_service.core.graphiti_factory as graphiti_factory_module
import miromem.graph_service.core.providers as providers_module
from miromem.graph_service.core.config import GraphServiceSettings
from miromem.graph_service.core.providers import (
    StructuredOutputCompatClient,
    patch_falkor_property_serialization,
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
    monkeypatch.setenv("GRAPH_RERANKER_PROVIDER", "custom")

    settings = GraphServiceSettings()

    assert settings.graph_backend == "graphiti"
    assert settings.graph_service_port == 8010
    assert settings.falkordb_host == "falkor"
    assert settings.graph_reranker_provider == "custom"


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


def test_build_graph_driver_does_not_schedule_background_index_task(monkeypatch):
    captured = _stub_falkordb(monkeypatch)
    created_tasks: list[object] = []

    class FakeLoop:
        def create_task(self, coro):
            created_tasks.append(coro)
            return object()

    monkeypatch.setattr(falkordb_driver_module.asyncio, "get_running_loop", lambda: FakeLoop())

    settings = GraphServiceSettings(
        falkordb_host="falkor",
        falkordb_port=6379,
        falkordb_database="mirofish_graphs",
    )

    driver = build_graph_driver(settings)

    assert driver.provider.value == "falkordb"
    assert captured["host"] == "falkor"
    assert created_tasks == []


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


@pytest.mark.asyncio
async def test_structured_output_client_injects_json_hint_and_normalizes_entity_payload():
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, *, model, messages, temperature, max_tokens, response_format):
            captured["messages"] = messages
            captured["response_format"] = response_format
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"response_type":"json","entities":[{"name":"Alice","entity_type_id":0}]}'
                        )
                    )
                ]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = StructuredOutputCompatClient(
        config=LLMConfig(
            api_key="key",
            base_url="https://coding.dashscope.aliyuncs.com/v1",
            model="qwen3.5-plus",
        ),
        client=fake_client,
    )

    result = await client.generate_response(
        [
            Message(role="system", content="Extract entities from the content."),
            Message(role="user", content="Alice discusses election forecasting."),
        ],
        response_model=ExtractedEntities,
        prompt_name="test.extract_nodes",
    )

    assert "json" in captured["messages"][0]["content"].lower()
    assert result == {"extracted_entities": [{"name": "Alice", "entity_type_id": 0}]}


@pytest.mark.asyncio
async def test_structured_output_client_uses_json_object_for_compat_backends():
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, *, model, messages, temperature, max_tokens, response_format):
            captured["response_format"] = response_format
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"extracted_entities":[{"name":"Alice","entity_type_id":0}]}'
                        )
                    )
                ]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = StructuredOutputCompatClient(
        config=LLMConfig(
            api_key="key",
            base_url="https://coding.dashscope.aliyuncs.com/v1",
            model="qwen3.5-plus",
        ),
        client=fake_client,
    )

    await client.generate_response(
        [
            Message(role="system", content="Extract entities from the content."),
            Message(role="user", content="Alice discusses election forecasting."),
        ],
        response_model=ExtractedEntities,
        prompt_name="test.extract_nodes.response_format",
    )

    assert captured["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_structured_output_client_normalizes_nested_entity_name_keys():
    class FakeCompletions:
        async def create(self, *, model, messages, temperature, max_tokens, response_format):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"extracted_entities":[{"entity_name":"Alice","entity_type_id":0}]}'
                        )
                    )
                ]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = StructuredOutputCompatClient(
        config=LLMConfig(
            api_key="key",
            base_url="https://coding.dashscope.aliyuncs.com/v1",
            model="qwen3.5-plus",
        ),
        client=fake_client,
    )

    result = await client.generate_response(
        [
            Message(role="system", content="Extract entities from the content."),
            Message(role="user", content="Alice discusses election forecasting."),
        ],
        response_model=ExtractedEntities,
        prompt_name="test.extract_nodes.aliases",
    )

    assert result == {"extracted_entities": [{"name": "Alice", "entity_type_id": 0}]}


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


def test_build_embedder_configures_async_client_timeout(monkeypatch):
    captured: dict[str, object] = {}

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key, base_url, timeout, max_retries):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["timeout"] = timeout
            captured["max_retries"] = max_retries

    monkeypatch.setattr(providers_module, "AsyncOpenAI", FakeAsyncOpenAI)

    settings = GraphServiceSettings(
        graph_embedding_api_key="key",
        graph_embedding_base_url="https://embed.example.com/v1",
        graph_embedding_model="Qwen/Qwen3-Embedding-0.6B",
        graph_embedding_dim=1024,
    )

    embedder = build_embedder(settings)

    assert embedder.client.__class__ is FakeAsyncOpenAI
    assert captured["api_key"] == "key"
    assert captured["base_url"] == "https://embed.example.com/v1"
    assert captured["timeout"] == providers_module.COMPAT_EMBEDDING_TIMEOUT_SECONDS
    assert captured["max_retries"] == 0


def test_build_reranker_returns_none_when_unconfigured():
    settings = GraphServiceSettings(
        graph_reranker_provider="disabled",
        graph_reranker_model="",
    )

    assert build_reranker(settings) is None


def test_build_reranker_uses_openai_compatible_provider():
    settings = GraphServiceSettings(
        graph_reranker_provider="openai_compat",
        graph_reranker_api_key="key",
        graph_reranker_base_url="https://rerank.example.com/v1",
        graph_reranker_model="rerank-model",
    )

    reranker = build_reranker(settings)

    assert isinstance(reranker, OpenAIRerankerClient)
    assert reranker.config.api_key == "key"
    assert reranker.config.base_url == "https://rerank.example.com/v1"
    assert reranker.config.model == "rerank-model"


def test_build_reranker_custom_provider_is_startup_safe():
    settings = GraphServiceSettings(
        graph_reranker_provider="custom",
        graph_reranker_model="custom-reranker",
    )

    assert build_reranker(settings) is None


def test_build_graphiti_injects_disabled_reranker_when_provider_is_disabled(monkeypatch):
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
    assert isinstance(captured["cross_encoder"], graphiti_factory_module.DisabledReranker)


def test_patch_falkor_property_serialization_wraps_node_and_edge_savers(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_node_save_bulk(self, executor, nodes, tx=None, batch_size=100):
        captured["nodes"] = nodes

    async def fake_edge_save_bulk(self, executor, edges, tx=None, batch_size=100):
        captured["edges"] = edges

    monkeypatch.setattr(FalkorEntityNodeOperations, "save_bulk", fake_node_save_bulk)
    monkeypatch.setattr(FalkorEntityEdgeOperations, "save_bulk", fake_edge_save_bulk)
    monkeypatch.setattr(providers_module, "_FALKOR_PATCHED", False)

    patch_falkor_property_serialization()

    node = SimpleNamespace(attributes={"profile": {"country": "US"}, "tags": ["a", "b"], "count": 1})
    edge = SimpleNamespace(attributes={"context": {"source": "demo"}, "scores": [1, 2], "active": True})

    import asyncio

    asyncio.run(FalkorEntityNodeOperations().save_bulk(None, [node]))
    asyncio.run(FalkorEntityEdgeOperations().save_bulk(None, [edge]))

    saved_node = captured["nodes"][0]
    saved_edge = captured["edges"][0]

    assert saved_node.attributes["profile"] == '{"country": "US"}'
    assert saved_node.attributes["tags"] == ["a", "b"]
    assert saved_node.attributes["count"] == 1
    assert saved_edge.attributes["context"] == '{"source": "demo"}'
    assert saved_edge.attributes["scores"] == [1, 2]
    assert saved_edge.attributes["active"] is True


def test_patch_falkor_property_serialization_wraps_graphiti_bulk_writer(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_add_nodes_and_edges_bulk(
        driver,
        episodic_nodes,
        episodic_edges,
        entity_nodes,
        entity_edges,
        embedder,
    ):
        captured["entity_nodes"] = entity_nodes
        captured["entity_edges"] = entity_edges

    monkeypatch.setattr(runtime_graphiti_module, "add_nodes_and_edges_bulk", fake_add_nodes_and_edges_bulk)
    monkeypatch.setattr(bulk_utils_module, "add_nodes_and_edges_bulk", fake_add_nodes_and_edges_bulk)
    monkeypatch.setattr(providers_module, "_FALKOR_PATCHED", False)

    patch_falkor_property_serialization()

    node = SimpleNamespace(attributes={"profile": {"country": "US"}, "tags": ["a", "b"], "count": 1})
    edge = SimpleNamespace(attributes={"context": {"source": "demo"}, "scores": [1, 2], "active": True})

    import asyncio

    asyncio.run(runtime_graphiti_module.add_nodes_and_edges_bulk(None, [], [], [node], [edge], None))

    saved_node = captured["entity_nodes"][0]
    saved_edge = captured["entity_edges"][0]

    assert saved_node.attributes["profile"] == '{"country": "US"}'
    assert saved_node.attributes["tags"] == ["a", "b"]
    assert saved_node.attributes["count"] == 1
    assert saved_edge.attributes["context"] == '{"source": "demo"}'
    assert saved_edge.attributes["scores"] == [1, 2]
    assert saved_edge.attributes["active"] is True


@pytest.mark.asyncio
async def test_patch_graphiti_edge_resolution_runtime_bounds_concurrency_and_degrades_timeouts(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_semaphore_gather(*coroutines, max_coroutines=None):
        captured["max_coroutines"] = max_coroutines
        return []

    async def fake_search(*args, **kwargs):
        raise TimeoutError("edge search timed out")

    monkeypatch.setattr(providers_module.edge_operations_module, "semaphore_gather", fake_semaphore_gather)
    monkeypatch.setattr(providers_module.edge_operations_module, "search", fake_search)
    monkeypatch.setattr(providers_module, "_GRAPHITI_EDGE_RUNTIME_PATCHED", False)

    providers_module.patch_graphiti_edge_resolution_runtime()

    result = await providers_module.edge_operations_module.search(None, "fact", None, None, None)
    await providers_module.edge_operations_module.semaphore_gather("a", "b")

    assert result.edges == []
    assert result.nodes == []
    assert captured["max_coroutines"] == providers_module.EDGE_RESOLUTION_MAX_CONCURRENCY
