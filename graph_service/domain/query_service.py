"""Graph read/query helpers built on top of Graphiti group-scoped reads."""

from __future__ import annotations

from collections.abc import Callable
from inspect import isawaitable
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.errors import GroupsEdgesNotFoundError, GroupsNodesNotFoundError
from graphiti_core.search.search_config import (
    EdgeReranker,
    EdgeSearchConfig,
    EdgeSearchMethod,
    NodeReranker,
    NodeSearchConfig,
    NodeSearchMethod,
    SearchConfig,
)

from miromem.graph_service.domain.snapshot_serializer import serialize_edge, serialize_node


class GraphQueryService:
    """Serve graph entity/detail/search reads through a dedicated abstraction."""

    def __init__(self, *, graphiti_factory: Callable[[], Graphiti]) -> None:
        self._graphiti_factory = graphiti_factory

    async def list_entities(
        self,
        *,
        graph_id: str,
        entity_type: str | None = None,
    ) -> dict[str, Any]:
        nodes, edges = await self._read_graph(graph_id)
        filtered_entities = []
        entity_types_found: set[str] = set()
        node_map = {node.uuid: node for node in nodes}

        for node in nodes:
            custom_labels = _get_custom_labels(node.labels)
            if not custom_labels:
                continue
            if entity_type is not None and entity_type not in custom_labels:
                continue

            entity_types_found.update(custom_labels)
            filtered_entities.append(_serialize_entity(node, node_map, edges))

        return {
            "entities": filtered_entities,
            "entity_types": sorted(entity_types_found),
            "total_count": len(nodes),
            "filtered_count": len(filtered_entities),
        }

    async def get_entity_detail(
        self,
        *,
        graph_id: str,
        entity_id: str,
    ) -> dict[str, Any] | None:
        nodes, edges = await self._read_graph(graph_id)
        node_map = {node.uuid: node for node in nodes}
        node = node_map.get(entity_id)
        if node is None:
            return None
        return _serialize_entity(node, node_map, edges)

    async def search(
        self,
        *,
        graph_id: str,
        query: str,
        limit: int = 10,
        center_node_uuid: str | None = None,
    ) -> dict[str, Any]:
        graphiti = self._graphiti_factory()
        try:
            results = await graphiti.search_(
                query=query,
                config=_build_search_config(limit),
                group_ids=[graph_id],
                center_node_uuid=center_node_uuid,
            )
        finally:
            await _close_graphiti(graphiti)

        serialized_nodes = [serialize_node(node) for node in results.nodes]
        node_names = {node["uuid"]: node["name"] for node in serialized_nodes}
        serialized_edges = [serialize_edge(edge, node_names) for edge in results.edges]
        facts = _dedupe_strings(edge["fact"] for edge in serialized_edges if edge["fact"])
        node_summaries = _dedupe_strings(
            _build_node_summary(node["name"], node["summary"]) for node in serialized_nodes
        )

        context_parts = []
        if facts:
            context_parts.append("Facts:\n" + "\n".join(f"- {fact}" for fact in facts))
        if node_summaries:
            context_parts.append(
                "Related entities:\n" + "\n".join(f"- {summary}" for summary in node_summaries)
            )

        return {
            "facts": facts,
            "node_summaries": node_summaries,
            "context": "\n\n".join(context_parts),
            "nodes": serialized_nodes,
            "edges": serialized_edges,
        }

    async def _read_graph(self, graph_id: str) -> tuple[list[Any], list[Any]]:
        graphiti = self._graphiti_factory()
        try:
            try:
                nodes = await graphiti.nodes.entity.get_by_group_ids([graph_id])
            except GroupsNodesNotFoundError:
                nodes = []

            try:
                edges = await graphiti.edges.entity.get_by_group_ids([graph_id])
            except GroupsEdgesNotFoundError:
                edges = []

            return nodes, edges
        finally:
            await _close_graphiti(graphiti)


def _get_custom_labels(labels: list[str]) -> list[str]:
    return [label for label in labels if label not in {"Entity", "Node"}]


def _serialize_entity(
    node: Any,
    node_map: dict[str, Any],
    edges: list[Any],
) -> dict[str, Any]:
    related_edges = []
    related_node_ids: set[str] = set()

    for edge in edges:
        if edge.source_node_uuid == node.uuid:
            related_edges.append(
                {
                    "direction": "outgoing",
                    "edge_name": edge.name or "",
                    "fact": edge.fact or "",
                    "target_node_uuid": edge.target_node_uuid,
                }
            )
            related_node_ids.add(edge.target_node_uuid)
        elif edge.target_node_uuid == node.uuid:
            related_edges.append(
                {
                    "direction": "incoming",
                    "edge_name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                }
            )
            related_node_ids.add(edge.source_node_uuid)

    related_nodes = [
        {
            "uuid": related_node.uuid,
            "name": related_node.name or "",
            "labels": list(related_node.labels or []),
            "summary": related_node.summary or "",
        }
        for related_node_id in sorted(related_node_ids)
        if (related_node := node_map.get(related_node_id)) is not None
    ]

    return {
        "uuid": node.uuid,
        "name": node.name or "",
        "labels": list(node.labels or []),
        "summary": node.summary or "",
        "attributes": dict(node.attributes or {}),
        "related_edges": related_edges,
        "related_nodes": related_nodes,
    }


def _build_search_config(limit: int) -> SearchConfig:
    return SearchConfig(
        edge_config=EdgeSearchConfig(
            search_methods=[
                EdgeSearchMethod.bm25,
                EdgeSearchMethod.cosine_similarity,
            ],
            reranker=EdgeReranker.rrf,
        ),
        node_config=NodeSearchConfig(
            search_methods=[
                NodeSearchMethod.bm25,
                NodeSearchMethod.cosine_similarity,
            ],
            reranker=NodeReranker.rrf,
        ),
        limit=limit,
    )


def _build_node_summary(name: str, summary: str) -> str:
    if name and summary:
        return f"{name}: {summary}"
    return name or summary


def _dedupe_strings(values: list[str] | Any) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


async def _close_graphiti(graphiti: Any) -> None:
    close = getattr(graphiti, "close", None)
    if close is None:
        return
    result = close()
    if isawaitable(result):
        await result
