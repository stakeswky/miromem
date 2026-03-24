"""Tests for graph-service configuration loading."""

from __future__ import annotations

from miromem.graph_service.core.config import GraphServiceSettings


def test_graph_service_settings_load_graphiti_fields(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    monkeypatch.setenv("GRAPH_SERVICE_PORT", "8010")
    monkeypatch.setenv("FALKORDB_HOST", "falkor")

    settings = GraphServiceSettings()

    assert settings.graph_backend == "graphiti"
    assert settings.graph_service_port == 8010
    assert settings.falkordb_host == "falkor"
