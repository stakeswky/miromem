"""Tests for the MiroFish graph backend feature flag switch."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


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


class _FakeGraphBackendClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.build_calls: list[tuple[str, dict[str, object]]] = []
        self.snapshot_calls: list[str] = []
        self.entity_calls: list[tuple[str, dict[str, object]]] = []
        self.detail_calls: list[tuple[str, str]] = []

    def build_graph(self, graph_id: str, payload: dict[str, object]) -> dict[str, object]:
        self.build_calls.append((graph_id, payload))
        return {"job_id": "job-123", "status": "queued"}

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
