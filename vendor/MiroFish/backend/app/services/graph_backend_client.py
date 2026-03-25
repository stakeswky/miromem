"""HTTP client for the internal graph-service backend."""

from __future__ import annotations

from typing import Any

import httpx


class GraphBackendClient:
    """Thin sync client used by the MiroFish backend graph adapters."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{normalized_path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout, transport=self.transport) as client:
            response = client.request(
                method,
                self._url(path),
                params=params,
                json=payload,
            )
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()

    def build_graph(self, graph_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/graphs/{graph_id}/build", payload=payload)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/jobs/{job_id}")

    def get_snapshot(self, graph_id: str) -> dict[str, Any]:
        return self._request("GET", f"/graphs/{graph_id}/snapshot")

    def get_entities(
        self,
        graph_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request("GET", f"/graphs/{graph_id}/entities", params=params)

    def get_entity_detail(self, graph_id: str, entity_id: str) -> dict[str, Any]:
        return self._request("GET", f"/graphs/{graph_id}/entities/{entity_id}")

    def search(self, graph_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/graphs/{graph_id}/search", payload=payload)

    def append_episodes(self, graph_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/graphs/{graph_id}/episodes", payload=payload)
