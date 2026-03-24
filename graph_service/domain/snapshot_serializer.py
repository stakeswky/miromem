"""Serialize Graphiti graph data into the frontend snapshot contract."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any


def _get_value(item: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a mapping or an object."""
    if isinstance(item, Mapping):
        if key in item:
            return item[key]
        if key == "uuid" and "uuid_" in item:
            return item["uuid_"]
        return default

    if hasattr(item, key):
        return getattr(item, key)
    if key == "uuid" and hasattr(item, "uuid_"):
        return getattr(item, "uuid_")
    return default


def _serialize_datetime(value: Any) -> str | None:
    """Normalize datetimes to ISO-8601 strings."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def serialize_node(node: Any) -> dict[str, Any]:
    """Serialize a Graphiti entity node into the frontend node shape."""
    return {
        "uuid": str(_get_value(node, "uuid", "")),
        "name": str(_get_value(node, "name", "") or ""),
        "labels": list(_get_value(node, "labels", []) or []),
        "summary": str(_get_value(node, "summary", "") or ""),
        "attributes": dict(_get_value(node, "attributes", {}) or {}),
        "created_at": _serialize_datetime(_get_value(node, "created_at")),
    }


def serialize_edge(edge: Any, node_names: Mapping[str, str]) -> dict[str, Any]:
    """Serialize a Graphiti entity edge into the frontend edge shape."""
    source_node_uuid = str(_get_value(edge, "source_node_uuid", "") or "")
    target_node_uuid = str(_get_value(edge, "target_node_uuid", "") or "")
    edge_name = str(_get_value(edge, "name", "") or "")
    fact_type = str(_get_value(edge, "fact_type", edge_name) or "")
    raw_episodes = _get_value(edge, "episodes", None)
    if raw_episodes is None:
        raw_episodes = _get_value(edge, "episode_ids", []) or []
    episodes = [str(episode) for episode in raw_episodes]

    return {
        "uuid": str(_get_value(edge, "uuid", "")),
        "name": edge_name,
        "fact": str(_get_value(edge, "fact", "") or ""),
        "fact_type": fact_type,
        "source_node_uuid": source_node_uuid,
        "target_node_uuid": target_node_uuid,
        "source_node_name": node_names.get(source_node_uuid, ""),
        "target_node_name": node_names.get(target_node_uuid, ""),
        "attributes": dict(_get_value(edge, "attributes", {}) or {}),
        "created_at": _serialize_datetime(_get_value(edge, "created_at")),
        "valid_at": _serialize_datetime(_get_value(edge, "valid_at")),
        "invalid_at": _serialize_datetime(_get_value(edge, "invalid_at")),
        "expired_at": _serialize_datetime(_get_value(edge, "expired_at")),
        "episodes": episodes,
    }


def serialize_snapshot(
    *,
    nodes: list[Any],
    edges: list[Any],
    graph_id: str,
    stale: bool,
    last_refreshed_at: str | None = None,
) -> dict[str, Any]:
    """Return the stable frontend graph snapshot payload."""
    serialized_nodes = [serialize_node(node) for node in nodes]
    node_names = {node["uuid"]: node["name"] for node in serialized_nodes}
    serialized_edges = [serialize_edge(edge, node_names) for edge in edges]

    return {
        "graph_id": graph_id,
        "node_count": len(serialized_nodes),
        "edge_count": len(serialized_edges),
        "stale": stale,
        "last_refreshed_at": last_refreshed_at,
        "nodes": serialized_nodes,
        "edges": serialized_edges,
    }
