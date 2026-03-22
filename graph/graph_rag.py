"""Graph-enhanced retrieval-augmented generation (GraphRAG)."""

from __future__ import annotations

import logging

import httpx

from miromem.config.settings import load_config
from miromem.graph.entity_extractor import EntityExtractor
from miromem.graph.graph_store import GraphStore
from miromem.graph.models import Entity, SubGraph

logger = logging.getLogger(__name__)


def _chunk_text(text: str, chunk_size: int = 512) -> list[str]:
    """Split *text* into roughly *chunk_size*-character chunks on sentence boundaries."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # try to break on sentence boundary
        if end < len(text):
            for sep in (". ", ".\n", "\n\n", "\n"):
                idx = text.rfind(sep, start, end)
                if idx > start:
                    end = idx + len(sep)
                    break
        chunks.append(text[start:end])
        start = end
    return chunks


class GraphRAG:
    """Combines graph structure with semantic vector search for richer retrieval."""

    def __init__(
        self,
        store: GraphStore | None = None,
        extractor: EntityExtractor | None = None,
    ) -> None:
        self._cfg = load_config()
        self._store = store or GraphStore()
        self._extractor = extractor or EntityExtractor()
        self._evermemos_url = self._cfg.evermemos.base_url

    async def build_from_documents(
        self, texts: list[str], *, chunk_size: int = 512
    ) -> SubGraph:
        """Chunk texts, extract entities/edges, and persist to graph store."""
        all_entities: list[Entity] = []
        all_edges = []

        for text in texts:
            for chunk in _chunk_text(text, chunk_size):
                entities, edges = await self._extractor.extract(chunk)
                if entities:
                    await self._store.add_entities_batch(entities)
                    all_entities.extend(entities)
                if edges:
                    await self._store.add_edges_batch(edges)
                    all_edges.extend(edges)

        return SubGraph(entities=all_entities, edges=all_edges)

    async def search(self, query: str, *, top_k: int = 10) -> SubGraph:
        """Hybrid search: vector similarity on entity descriptions + graph expansion.

        1. Call EverMemOS vector search to find semantically similar entities.
        2. Expand each hit via graph traversal for structural context.
        """
        # Step 1: vector similarity via EverMemOS search endpoint
        seed_ids: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._evermemos_url}/memories/search",
                    json={"query": query, "top_k": top_k, "collection": "graph_entities"},
                )
                if resp.status_code == 200:
                    for hit in resp.json().get("results", []):
                        eid = hit.get("metadata", {}).get("entity_id") or hit.get("id")
                        if eid:
                            seed_ids.append(eid)
        except Exception:
            logger.warning("EverMemOS vector search unavailable, falling back to name match")

        # Fallback: text match on entity names if vector search returned nothing
        if not seed_ids:
            cursor = self._store.entities.find(
                {"$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                ]},
            ).limit(top_k)
            async for doc in cursor:
                seed_ids.append(doc["id"])

        if not seed_ids:
            return SubGraph()

        # Step 2: expand via graph traversal
        return await self._store.get_subgraph(seed_ids[:top_k], depth=1)

    async def get_entity_context(self, entity_name: str) -> str:
        """Return a formatted context string for an entity and its neighborhood."""
        entity = await self._store.get_entity_by_name(entity_name)
        if not entity:
            return f"No entity found with name '{entity_name}'."

        subgraph = await self._store.get_neighbors(entity.id, depth=1)
        facts = await self._store.get_facts_for_entity(entity.id)

        lines = [f"Entity: {entity.name} ({entity.entity_type})", f"  {entity.description}"]

        if facts:
            lines.append("Facts:")
            for f in facts:
                obj = f.object_value or f.object_entity_id or "?"
                lines.append(f"  - {f.predicate}: {obj} (confidence={f.confidence:.2f})")

        if subgraph.edges:
            lines.append("Relationships:")
            entity_map = {e.id: e.name for e in subgraph.entities}
            for edge in subgraph.edges:
                src = entity_map.get(edge.source_entity_id, edge.source_entity_id)
                tgt = entity_map.get(edge.target_entity_id, edge.target_entity_id)
                lines.append(f"  - {src} --[{edge.relation_type}]--> {tgt}")

        return "\n".join(lines)
