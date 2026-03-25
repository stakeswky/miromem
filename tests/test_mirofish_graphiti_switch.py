"""Tests for the MiroFish graph backend feature flag switch."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "vendor" / "MiroFish" / "backend" / "app"

PACKAGE_PATHS = {
    "vendor": ROOT_DIR / "vendor",
    "vendor.MiroFish": ROOT_DIR / "vendor" / "MiroFish",
    "vendor.MiroFish.backend": ROOT_DIR / "vendor" / "MiroFish" / "backend",
    "vendor.MiroFish.backend.app": APP_DIR,
    "vendor.MiroFish.backend.app.services": APP_DIR / "services",
    "vendor.MiroFish.backend.app.models": APP_DIR / "models",
    "vendor.MiroFish.backend.app.utils": APP_DIR / "utils",
}


def _load_mirofish_module(module_name: str, relative_path: str):
    for name in list(sys.modules):
        if name.startswith("vendor.MiroFish.backend.app"):
            sys.modules.pop(name)

    for package_name, package_path in PACKAGE_PATHS.items():
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_path)]
        sys.modules[package_name] = package

    module_path = APP_DIR / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_fake_external_modules() -> None:
    openai_module = types.ModuleType("openai")

    class _FakeOpenAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=lambda *call_args, **call_kwargs: None,
                )
            )

    openai_module.OpenAI = _FakeOpenAI
    sys.modules["openai"] = openai_module

    zep_cloud_module = types.ModuleType("zep_cloud")
    zep_cloud_client_module = types.ModuleType("zep_cloud.client")

    class _FakeZep:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.graph = types.SimpleNamespace(
                add=lambda **call_kwargs: None,
                search=lambda **call_kwargs: types.SimpleNamespace(edges=[], nodes=[]),
            )

    zep_cloud_client_module.Zep = _FakeZep
    zep_cloud_module.client = zep_cloud_client_module
    sys.modules["zep_cloud"] = zep_cloud_module
    sys.modules["zep_cloud.client"] = zep_cloud_client_module


class _FakeGraphBackendClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.build_calls: list[tuple[str, dict[str, object]]] = []
        self.job_calls: list[str] = []
        self.snapshot_calls: list[str] = []
        self.entity_calls: list[tuple[str, dict[str, object]]] = []
        self.detail_calls: list[tuple[str, str]] = []
        self.search_calls: list[tuple[str, dict[str, object]]] = []
        self.append_calls: list[tuple[str, dict[str, object]]] = []
        self.search_response: dict[str, object] = {
            "facts": ["Alice is campaigning in California."],
            "node_summaries": ["California: A state"],
            "context": "facts and nodes",
        }
        self.append_error: Exception | None = None
        self.job_statuses: list[str] = ["completed"]

    def build_graph(self, graph_id: str, payload: dict[str, object]) -> dict[str, object]:
        self.build_calls.append((graph_id, payload))
        return {"job_id": "job-123", "status": "queued"}

    def get_job(self, job_id: str) -> dict[str, object]:
        self.job_calls.append(job_id)
        status = self.job_statuses.pop(0) if self.job_statuses else "completed"
        return {"job_id": job_id, "status": status}

    def get_snapshot(self, graph_id: str) -> dict[str, object]:
        self.snapshot_calls.append(graph_id)
        return {
            "graph_id": graph_id,
            "node_count": 1,
            "edge_count": 1,
            "nodes": [
                {
                    "uuid": "node-1",
                    "name": "Alice",
                    "labels": ["Entity", "Person"],
                    "summary": "Market analyst",
                    "attributes": {"country": "US"},
                    "created_at": "2026-03-24T12:00:00+00:00",
                }
            ],
            "edges": [
                {
                    "uuid": "edge-1",
                    "name": "KNOWS",
                    "fact": "Alice follows Bob",
                    "fact_type": "KNOWS",
                    "source_node_uuid": "node-1",
                    "target_node_uuid": "node-2",
                    "source_node_name": "Alice",
                    "target_node_name": "Bob",
                    "attributes": {},
                    "created_at": "2026-03-24T12:05:00+00:00",
                    "valid_at": None,
                    "invalid_at": None,
                    "expired_at": None,
                    "episodes": [],
                }
            ],
        }

    def get_entities(self, graph_id: str, params: dict[str, object] | None = None) -> dict[str, object]:
        self.entity_calls.append((graph_id, params or {}))
        return {
            "entities": [
                {
                    "uuid": "node-1",
                    "name": "Alice",
                    "labels": ["Entity", "Person"],
                    "summary": "Market analyst",
                    "attributes": {"country": "US"},
                    "related_edges": [
                        {
                            "direction": "outgoing",
                            "edge_name": "KNOWS",
                            "fact": "Alice follows Bob",
                            "target_node_uuid": "node-2",
                        }
                    ],
                    "related_nodes": [
                        {
                            "uuid": "node-2",
                            "name": "Bob",
                            "labels": ["Entity", "Person"],
                            "summary": "Trader",
                        }
                    ],
                }
            ],
            "entity_types": ["Person"],
            "total_count": 1,
            "filtered_count": 1,
        }

    def get_entity_detail(self, graph_id: str, entity_id: str) -> dict[str, object]:
        self.detail_calls.append((graph_id, entity_id))
        return {
            "uuid": entity_id,
            "name": "Alice",
            "labels": ["Entity", "Person"],
            "summary": "Market analyst",
            "attributes": {"country": "US"},
            "related_edges": [
                {
                    "direction": "outgoing",
                    "edge_name": "KNOWS",
                    "fact": "Alice follows Bob",
                    "target_node_uuid": "node-2",
                }
            ],
            "related_nodes": [
                {
                    "uuid": "node-2",
                    "name": "Bob",
                    "labels": ["Entity", "Person"],
                    "summary": "Trader",
                }
            ],
        }

    def search(self, graph_id: str, payload: dict[str, object]) -> dict[str, object]:
        self.search_calls.append((graph_id, payload))
        return self.search_response

    def append_episodes(self, graph_id: str, payload: dict[str, object]) -> dict[str, object]:
        self.append_calls.append((graph_id, payload))
        if self.append_error is not None:
            raise self.append_error
        return {"job_id": "append-job-123", "status": "queued"}


def test_env_template_and_readme_document_graphiti_rollout_contract() -> None:
    env_template = Path(".env.template").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "GRAPH_BACKEND" in env_template
    assert "GRAPH_SERVICE_BASE_URL" in env_template
    assert "FALKORDB_HOST" in env_template

    assert "GRAPH_BACKEND=graphiti" in readme
    assert "GRAPH_BACKEND=zep" in readme
    assert "graph-service" in readme
    assert "Thinker remains upstream and unchanged" in readme


def test_config_defaults_to_zep_backend(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.delenv("GRAPH_BACKEND", raising=False)
    monkeypatch.delenv("GRAPH_SERVICE_BASE_URL", raising=False)
    monkeypatch.delenv("ZEP_API_KEY", raising=False)

    config_module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.config",
        "config.py",
    )

    assert config_module.Config.GRAPH_BACKEND == "zep"
    assert config_module.Config.GRAPH_SERVICE_BASE_URL == "http://graph-service:8001"
    assert config_module.Config.validate() == ["ZEP_API_KEY 未配置"]


def test_graph_builder_uses_graph_service_when_feature_flag_enabled(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    monkeypatch.setenv("GRAPH_SERVICE_BASE_URL", "http://graph-service:8001")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.delenv("ZEP_API_KEY", raising=False)

    config_module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.config",
        "config.py",
    )
    _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.graph_backend_client",
        "services/graph_backend_client.py",
    )
    graph_builder_module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.graph_builder",
        "services/graph_builder.py",
    )

    fake_client = _FakeGraphBackendClient(config_module.Config.GRAPH_SERVICE_BASE_URL)
    monkeypatch.setattr(
        graph_builder_module,
        "GraphBackendClient",
        lambda base_url: fake_client,
    )

    builder = graph_builder_module.GraphBuilderService()
    graph_id = builder.create_graph("Demo Graph")
    builder.set_ontology(
        graph_id,
        {"entity_types": [{"name": "Person", "attributes": []}], "edge_types": []},
    )

    job_ids = builder.add_text_batches(
        graph_id,
        ["Alice follows Bob.", "Bob watches markets."],
        batch_size=2,
    )
    builder._wait_for_episodes(job_ids)
    graph_data = builder.get_graph_data(graph_id)

    assert config_module.Config.GRAPH_BACKEND == "graphiti"
    assert job_ids == ["job-123"]
    assert fake_client.build_calls[0][0] == graph_id
    assert fake_client.build_calls[0][1]["graph_name"] == "Demo Graph"
    assert fake_client.build_calls[0][1]["ontology"]["entity_types"][0]["name"] == "Person"
    assert "Alice follows Bob." in fake_client.build_calls[0][1]["document_text"]
    assert graph_data["graph_id"] == graph_id
    assert graph_data["node_count"] == 1
    assert graph_data["edge_count"] == 1


def test_graph_builder_waits_for_graph_service_job_completion(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    monkeypatch.setenv("GRAPH_SERVICE_BASE_URL", "http://graph-service:8001")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.delenv("ZEP_API_KEY", raising=False)

    config_module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.config",
        "config.py",
    )
    _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.graph_backend_client",
        "services/graph_backend_client.py",
    )
    graph_builder_module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.graph_builder",
        "services/graph_builder.py",
    )

    fake_client = _FakeGraphBackendClient(config_module.Config.GRAPH_SERVICE_BASE_URL)
    fake_client.job_statuses = ["running", "completed"]
    monkeypatch.setattr(
        graph_builder_module,
        "GraphBackendClient",
        lambda base_url: fake_client,
    )
    monkeypatch.setattr(graph_builder_module.time, "sleep", lambda seconds: None)

    builder = graph_builder_module.GraphBuilderService()
    graph_id = builder.create_graph("Demo Graph")
    builder.set_ontology(
        graph_id,
        {"entity_types": [{"name": "Person", "attributes": []}], "edge_types": []},
    )

    job_ids = builder.add_text_batches(
        graph_id,
        ["Alice follows Bob."],
        batch_size=1,
    )
    builder._wait_for_episodes(job_ids)

    assert job_ids == ["job-123"]
    assert fake_client.job_calls == ["job-123", "job-123"]


def test_zep_entity_reader_uses_graph_service_when_feature_flag_enabled(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    monkeypatch.setenv("GRAPH_SERVICE_BASE_URL", "http://graph-service:8001")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.delenv("ZEP_API_KEY", raising=False)

    _load_mirofish_module(
        "vendor.MiroFish.backend.app.config",
        "config.py",
    )
    _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.graph_backend_client",
        "services/graph_backend_client.py",
    )
    reader_module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.zep_entity_reader",
        "services/zep_entity_reader.py",
    )

    fake_client = _FakeGraphBackendClient("http://graph-service:8001")
    monkeypatch.setattr(
        reader_module,
        "GraphBackendClient",
        lambda base_url: fake_client,
    )

    reader = reader_module.ZepEntityReader()
    filtered = reader.filter_defined_entities(
        graph_id="mirofish_demo",
        defined_entity_types=["Person"],
        enrich_with_edges=True,
    )
    entity = reader.get_entity_with_context("mirofish_demo", "node-1")

    assert fake_client.entity_calls == [("mirofish_demo", {"entity_type": "Person"})]
    assert fake_client.detail_calls == [("mirofish_demo", "node-1")]
    assert filtered.to_dict()["filtered_count"] == 1
    assert filtered.entities[0].name == "Alice"
    assert entity is not None
    assert entity.name == "Alice"
    assert entity.related_nodes[0]["name"] == "Bob"


def test_profile_generator_uses_graph_service_search_when_graphiti_enabled(monkeypatch):
    _install_fake_external_modules()
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    monkeypatch.setenv("GRAPH_SERVICE_BASE_URL", "http://graph-service:8001")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.delenv("ZEP_API_KEY", raising=False)

    _load_mirofish_module(
        "vendor.MiroFish.backend.app.config",
        "config.py",
    )
    profile_module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.oasis_profile_generator",
        "services/oasis_profile_generator.py",
    )

    fake_client = _FakeGraphBackendClient("http://graph-service:8001")
    fake_client.search_response = {
        "facts": ["Alice supports carbon pricing."],
        "node_summaries": ["Bob: A campaign adviser"],
        "context": "facts and nodes",
    }
    monkeypatch.setattr(
        profile_module,
        "GraphBackendClient",
        lambda base_url: fake_client,
        raising=False,
    )

    generator = profile_module.OasisProfileGenerator(graph_id="mirofish_demo")
    entity = profile_module.EntityNode(
        uuid="node-1",
        name="Alice",
        labels=["Entity", "Person"],
        summary="Market analyst",
        attributes={},
    )

    payload = generator._search_zep_for_entity(entity)

    assert fake_client.search_calls == [
        (
            "mirofish_demo",
            {
                "query": "关于Alice的所有信息、活动、事件、关系和背景",
                "limit": 30,
                "center_node_uuid": "node-1",
            },
        )
    ]
    assert payload == {
        "facts": ["Alice supports carbon pricing."],
        "node_summaries": ["Bob: A campaign adviser"],
        "context": "facts and nodes",
    }


def test_graph_memory_updater_degrades_without_stopping_simulation(monkeypatch):
    _install_fake_external_modules()
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    monkeypatch.setenv("GRAPH_SERVICE_BASE_URL", "http://graph-service:8001")
    monkeypatch.delenv("ZEP_API_KEY", raising=False)

    _load_mirofish_module(
        "vendor.MiroFish.backend.app.config",
        "config.py",
    )
    updater_module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.zep_graph_memory_updater",
        "services/zep_graph_memory_updater.py",
    )

    fake_client = _FakeGraphBackendClient("http://graph-service:8001")
    fake_client.append_error = RuntimeError("graph append unavailable")
    monkeypatch.setattr(
        updater_module,
        "GraphBackendClient",
        lambda base_url: fake_client,
        raising=False,
    )

    updater = updater_module.ZepGraphMemoryUpdater(graph_id="mirofish_demo")
    activity = updater_module.AgentActivity(
        platform="twitter",
        agent_id=1,
        agent_name="Alice",
        action_type="CREATE_POST",
        action_args={"content": "Hello markets"},
        round_num=1,
        timestamp="2026-03-24T12:00:00Z",
    )

    updater._send_batch_activities([activity], "twitter")
    stats = updater.get_stats()

    assert len(fake_client.append_calls) == updater.MAX_RETRIES
    assert fake_client.append_calls[0] == (
        "mirofish_demo",
        {
            "episodes": [
                {
                    "name": "Twitter action batch",
                    "content": "Alice: 发布了一条帖子：「Hello markets」",
                    "reference_time": "2026-03-24T12:00:00Z",
                    "source": "text",
                    "source_description": "simulation:twitter",
                }
            ]
        },
    )
    assert stats["batches_sent"] == 0
    assert stats["items_sent"] == 0
    assert stats["failed_count"] == 1
