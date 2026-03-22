"""Shared pytest fixtures for MiroMem test suite."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock EverMemOS HTTP client
# ---------------------------------------------------------------------------

def _sample_memory(content: str, memory_type: str = "EpisodicMemory", **extra_meta: Any) -> dict[str, Any]:
    return {
        "id": f"mem-{hash(content) % 10000:04d}",
        "content": content,
        "memory_type": memory_type,
        "score": 0.85,
        "metadata": {"role": "agent", "created_at": "2026-03-20T12:00:00", **extra_meta},
    }


@pytest.fixture()
def mock_evermemos_client() -> AsyncMock:
    """Async mock of ``EverMemClient`` returning canned responses."""
    client = AsyncMock()
    client.store_memory.return_value = {"id": "mem-new-001", "status": "created"}
    client.search_memories.return_value = [
        _sample_memory("Agent posted about market trends", zep_uuid="z1"),
        _sample_memory("Agent liked a bearish analysis", zep_uuid="z2"),
    ]
    client.get_memories.return_value = [
        _sample_memory("Profile data", "Profile", name="Alice", personality="analytical"),
        _sample_memory("Round 1 summary", "MemCell"),
    ]
    client.delete_memories.return_value = {"deleted": 2}
    client.get_conversation_meta.return_value = {
        "session_id": "sess-001",
        "user_id": "agent-001",
        "created_at": "2026-03-20T10:00:00",
    }
    client.save_conversation_meta.return_value = {"status": "ok"}
    client.health_check.return_value = {"status": "ok"}
    return client


# ---------------------------------------------------------------------------
# Mock MongoDB (motor-compatible)
# ---------------------------------------------------------------------------

class _FakeCursor:
    """Minimal async cursor for motor mocks."""

    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = list(docs)
        self._sort_field: str | None = None
        self._limit_n: int | None = None

    def sort(self, field: str, direction: int = -1) -> _FakeCursor:
        self._sort_field = field
        return self

    def limit(self, n: int) -> _FakeCursor:
        self._limit_n = n
        return self

    def __aiter__(self):
        docs = self._docs
        if self._limit_n:
            docs = docs[: self._limit_n]
        return _FakeAsyncIter(docs)


class _FakeAsyncIter:
    def __init__(self, items: list) -> None:
        self._it = iter(items)

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeCollection:
    """Minimal motor collection mock supporting insert/find/update/delete."""

    def __init__(self) -> None:
        self._docs: list[dict[str, Any]] = []

    async def insert_one(self, doc: dict) -> MagicMock:
        self._docs.append(dict(doc))
        r = MagicMock()
        r.inserted_id = doc.get("id", "fake-id")
        return r

    async def insert_many(self, docs: list[dict]) -> MagicMock:
        self._docs.extend(dict(d) for d in docs)
        r = MagicMock()
        r.inserted_ids = [d.get("id") for d in docs]
        return r

    async def find_one(self, query: dict) -> dict | None:
        for doc in self._docs:
            if all(doc.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                return dict(doc)
        return None

    def find(self, query: dict | None = None) -> _FakeCursor:
        if not query:
            return _FakeCursor(self._docs)
        matched = []
        for doc in self._docs:
            if "$or" in (query or {}):
                if any(
                    all(doc.get(k) == v for k, v in clause.items() if not isinstance(v, dict))
                    for clause in query["$or"]
                ):
                    matched.append(doc)
            elif "$in" in str(query):
                matched.append(doc)  # simplified
            else:
                if all(doc.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                    matched.append(doc)
        return _FakeCursor(matched)

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> MagicMock:
        doc = await self.find_one(query)
        if doc and "$set" in update:
            doc.update(update["$set"])
        elif upsert and "$set" in update:
            self._docs.append(update["$set"])
        r = MagicMock()
        r.modified_count = 1 if doc else 0
        return r

    async def delete_one(self, query: dict) -> MagicMock:
        for i, doc in enumerate(self._docs):
            if all(doc.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                self._docs.pop(i)
                r = MagicMock()
                r.deleted_count = 1
                return r
        r = MagicMock()
        r.deleted_count = 0
        return r

    async def delete_many(self, query: dict) -> MagicMock:
        r = MagicMock()
        r.deleted_count = 0
        return r

    async def create_index(self, *args, **kwargs) -> str:
        return "fake_index"


class FakeDatabase:
    """Motor-compatible database mock using in-memory collections."""

    def __init__(self) -> None:
        self._collections: dict[str, _FakeCollection] = {}

    def __getitem__(self, name: str) -> _FakeCollection:
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]

    def __getattr__(self, name: str) -> _FakeCollection:
        return self[name]


@pytest.fixture()
def mock_mongodb() -> FakeDatabase:
    return FakeDatabase()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_memories() -> list[dict[str, Any]]:
    return [
        _sample_memory("Core belief: markets are cyclical", "MemCell"),
        _sample_memory("Attended earnings call for ACME Corp", "EpisodicMemory"),
        _sample_memory("Prediction: tech sector correction in Q2", "Foresight"),
        _sample_memory("Agent posted bullish analysis", "EventLog", action_type="CREATE_POST"),
        _sample_memory("Analyst with 10yr experience", "Profile", name="Bob", occupation="analyst"),
    ]


@pytest.fixture()
def sample_entities() -> dict[str, list[dict[str, Any]]]:
    from miromem.graph.models import Edge, Entity, GraphFact

    e1 = Entity(id="e1", name="ACME Corp", entity_type="Company", description="Tech company")
    e2 = Entity(id="e2", name="Bob", entity_type="Person", description="Senior analyst")
    edge = Edge(id="ed1", source_entity_id="e1", target_entity_id="e2", relation_type="employs")
    fact = GraphFact(id="f1", subject_entity_id="e1", predicate="sector", object_value="Technology")
    return {"entities": [e1, e2], "edge": edge, "fact": fact}


@pytest.fixture()
def sample_simulation() -> dict[str, Any]:
    return {
        "simulation_id": "sim-test-001",
        "project_id": "proj-001",
        "agent_ids": ["agent-alice", "agent-bob"],
        "profiles": {
            "agent-alice": {
                "name": "Alice",
                "age": 30,
                "personality": "analytical",
                "bio": "Data scientist",
                "interests": ["AI", "finance"],
            },
            "agent-bob": {
                "name": "Bob",
                "age": 45,
                "personality": "contrarian",
                "bio": "Veteran trader",
                "interests": ["macro", "commodities"],
            },
        },
        "round_summary": "Round 1: agents debated market outlook",
    }