"""Tests for the MiroFish graph-service client."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "vendor" / "MiroFish" / "backend" / "app"

PACKAGE_PATHS = {
    "vendor": ROOT_DIR / "vendor",
    "vendor.MiroFish": ROOT_DIR / "vendor" / "MiroFish",
    "vendor.MiroFish.backend": ROOT_DIR / "vendor" / "MiroFish" / "backend",
    "vendor.MiroFish.backend.app": APP_DIR,
    "vendor.MiroFish.backend.app.services": APP_DIR / "services",
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


def test_graph_backend_client_builds_snapshot_url():
    module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.graph_backend_client",
        "services/graph_backend_client.py",
    )

    client = module.GraphBackendClient("http://graph-service:8001/")

    assert client._url("/graphs/demo/snapshot") == "http://graph-service:8001/graphs/demo/snapshot"


def test_graph_backend_client_routes_all_supported_graph_requests():
    module = _load_mirofish_module(
        "vendor.MiroFish.backend.app.services.graph_backend_client",
        "services/graph_backend_client.py",
    )

    captured_requests: list[tuple[str, str, dict[str, str], dict[str, object] | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = None
        if request.content:
            payload = json.loads(request.content.decode("utf-8"))
        captured_requests.append(
            (
                request.method,
                request.url.path,
                dict(request.url.params),
                payload,
            )
        )

        if request.method == "GET":
            return httpx.Response(200, json={"path": request.url.path, "params": dict(request.url.params)})

        return httpx.Response(202, json={"path": request.url.path, "payload": payload})

    transport = httpx.MockTransport(handler)
    client = module.GraphBackendClient(
        "http://graph-service:8001",
        transport=transport,
    )

    assert client.build_graph("demo", {"graph_name": "Demo"})["path"] == "/graphs/demo/build"
    assert client.get_job("job-123")["path"] == "/jobs/job-123"
    assert client.get_snapshot("demo")["path"] == "/graphs/demo/snapshot"
    assert client.get_entities("demo", {"entity_type": "Person"})["params"] == {"entity_type": "Person"}
    assert client.get_entity_detail("demo", "node-1")["path"] == "/graphs/demo/entities/node-1"
    assert client.search("demo", {"query": "market"})["path"] == "/graphs/demo/search"
    assert client.append_episodes("demo", {"episodes": []})["path"] == "/graphs/demo/episodes"

    assert captured_requests == [
        ("POST", "/graphs/demo/build", {}, {"graph_name": "Demo"}),
        ("GET", "/jobs/job-123", {}, None),
        ("GET", "/graphs/demo/snapshot", {}, None),
        ("GET", "/graphs/demo/entities", {"entity_type": "Person"}, None),
        ("GET", "/graphs/demo/entities/node-1", {}, None),
        ("POST", "/graphs/demo/search", {}, {"query": "market"}),
        ("POST", "/graphs/demo/episodes", {}, {"episodes": []}),
    ]
