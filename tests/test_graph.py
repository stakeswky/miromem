"""Tests for miromem.graph — GraphStore, EntityExtractor, GraphRAG."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miromem.graph.models import Edge, Entity, GraphFact, SubGraph


# ===================================================================
# GraphStore CRUD tests
# ===================================================================


@pytest.mark.asyncio
class TestGraphStoreCRUD:
    async def test_add_and_get_entity(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        ent = Entity(id="e1", name="ACME", entity_type="Company", description="Tech co")
        await store.add_entity(ent)

        result = await store.get_entity("e1")
        assert result is not None
        assert result.name == "ACME"

    async def test_get_entity_by_name(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        ent = Entity(id="e1", name="ACME", entity_type="Company")
        await store.add_entity(ent)

        result = await store.get_entity_by_name("ACME")
        assert result is not None
        assert result.id == "e1"

    async def test_update_entity(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        ent = Entity(id="e1", name="ACME", entity_type="Company")
        await store.add_entity(ent)

        updated = await store.update_entity("e1", description="Updated desc")
        assert updated is not None

    async def test_delete_entity(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        ent = Entity(id="e1", name="ACME", entity_type="Company")
        await store.add_entity(ent)

        assert await store.delete_entity("e1") is True
        assert await store.get_entity("e1") is None

    async def test_delete_nonexistent_entity(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        assert await store.delete_entity("nope") is False

    async def test_add_and_get_edge(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        edge = Edge(id="ed1", source_entity_id="e1", target_entity_id="e2", relation_type="employs")
        await store.add_edge(edge)

        edges = await store.get_edges_for_entity("e1")
        assert len(edges) == 1
        assert edges[0].relation_type == "employs"

    async def test_delete_edge(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        edge = Edge(id="ed1", source_entity_id="e1", target_entity_id="e2", relation_type="employs")
        await store.add_edge(edge)

        assert await store.delete_edge("ed1") is True
        assert await store.delete_edge("ed1") is False

    async def test_add_and_get_fact(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        fact = GraphFact(id="f1", subject_entity_id="e1", predicate="sector", object_value="Tech")
        await store.add_fact(fact)

        facts = await store.get_facts_for_entity("e1")
        assert len(facts) == 1
        assert facts[0].predicate == "sector"


# ===================================================================
# Graph traversal tests
# ===================================================================


@pytest.mark.asyncio
class TestGraphTraversal:
    async def _setup_graph(self, mock_mongodb):
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        e1 = Entity(id="e1", name="A", entity_type="Node")
        e2 = Entity(id="e2", name="B", entity_type="Node")
        e3 = Entity(id="e3", name="C", entity_type="Node")
        await store.add_entities_batch([e1, e2, e3])
        await store.add_edge(Edge(id="ed1", source_entity_id="e1", target_entity_id="e2", relation_type="links"))
        await store.add_edge(Edge(id="ed2", source_entity_id="e2", target_entity_id="e3", relation_type="links"))
        return store

    async def test_get_neighbors(self, mock_mongodb):
        store = await self._setup_graph(mock_mongodb)
        sg = await store.get_neighbors("e1", depth=1)
        entity_ids = {e.id for e in sg.entities}
        assert "e1" in entity_ids
        assert "e2" in entity_ids

    async def test_find_path(self, mock_mongodb):
        store = await self._setup_graph(mock_mongodb)
        path = await store.find_path("e1", "e3", max_depth=3)
        assert path is not None
        assert path[0] == "e1"
        assert path[-1] == "e3"

    async def test_find_path_no_connection(self, mock_mongodb):
        store = await self._setup_graph(mock_mongodb)
        # e3 -> e1 has no path in directed sense with max_depth=0
        path = await store.find_path("e3", "e1", max_depth=0)
        assert path is None

    async def test_get_subgraph(self, mock_mongodb):
        store = await self._setup_graph(mock_mongodb)
        sg = await store.get_subgraph(["e1", "e3"], depth=1)
        entity_ids = {e.id for e in sg.entities}
        assert "e1" in entity_ids
        assert "e3" in entity_ids


# ===================================================================
# EntityExtractor tests (mocked LLM)
# ===================================================================


@pytest.mark.asyncio
class TestEntityExtractor:
    async def test_extract_entities_and_edges(self):
        from miromem.graph.entity_extractor import EntityExtractor

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '{"entities": [{"name": "ACME", "entity_type": "Company", "description": "Tech firm"},'
            '{"name": "Bob", "entity_type": "Person", "description": "Engineer"}],'
            '"edges": [{"source": "ACME", "target": "Bob", "relation_type": "employs"}]}'
        )

        with patch("miromem.graph.entity_extractor.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            extractor = EntityExtractor()
            entities, edges = await extractor.extract("ACME employs Bob as an engineer.")

        assert len(entities) == 2
        assert entities[0].name == "ACME"
        assert len(edges) == 1
        assert edges[0].relation_type == "employs"

    async def test_extract_handles_invalid_json(self):
        from miromem.graph.entity_extractor import EntityExtractor

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json"

        with patch("miromem.graph.entity_extractor.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            extractor = EntityExtractor()
            entities, edges = await extractor.extract("some text")

        assert entities == []
        assert edges == []


# ===================================================================
# GraphRAG tests (mocked vector search)
# ===================================================================


@pytest.mark.asyncio
class TestGraphRAG:
    async def test_search_with_name_fallback(self, mock_mongodb):
        from miromem.graph.graph_rag import GraphRAG
        from miromem.graph.graph_store import GraphStore

        store = GraphStore(db=mock_mongodb)
        e1 = Entity(id="e1", name="ACME Corp", entity_type="Company", description="Tech")
        await store.add_entity(e1)

        with patch("miromem.graph.entity_extractor.AsyncOpenAI"):
            rag = GraphRAG(store=store)

        # Mock httpx to simulate vector search failure (triggers name fallback)
        with patch("miromem.graph.graph_rag.httpx.AsyncClient") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.side_effect = Exception("connection refused")
            mock_httpx.return_value = mock_client

            sg = await rag.search("ACME")

        assert len(sg.entities) >= 1
        assert sg.entities[0].name == "ACME Corp"