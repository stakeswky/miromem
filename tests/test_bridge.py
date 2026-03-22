"""Tests for miromem.bridge — EverMemClient, ZepAdapter, and model conversions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from miromem.bridge.models import (
    EverMemType,
    ZepEntity,
    ZepFact,
    ZepMessage,
    ZepSearchResult,
    ZepSession,
)


# ===================================================================
# Model conversion tests
# ===================================================================


class TestZepMessage:
    def test_to_evermemos_payload(self):
        msg = ZepMessage(role="human", content="Hello world")
        payload = msg.to_evermemos_payload(user_id="u1", group_id="g1")

        assert payload["user_id"] == "u1"
        assert payload["content"] == "Hello world"
        assert payload["memory_type"] == EverMemType.episodic.value
        assert payload["group_id"] == "g1"
        assert payload["metadata"]["role"] == "human"

    def test_to_evermemos_payload_no_group(self):
        msg = ZepMessage(role="ai", content="Response")
        payload = msg.to_evermemos_payload(user_id="u1")
        assert "group_id" not in payload


class TestZepSearchResult:
    def test_from_evermemos(self):
        hit = {
            "content": "Some memory",
            "score": 0.9,
            "metadata": {"role": "agent", "created_at": "2026-03-20T12:00:00"},
        }
        result = ZepSearchResult.from_evermemos(hit)

        assert result.message is not None
        assert result.message.content == "Some memory"
        assert result.score == 0.9
        assert result.dist == pytest.approx(0.1)
        assert result.message.role == "agent"

class TestZepEntity:
    def test_to_evermemos_payload(self):
        ent = ZepEntity(name="ACME", entity_type="Company", description="Tech firm")
        payload = ent.to_evermemos_payload(user_id="u1")
        assert payload["memory_type"] == EverMemType.profile.value
        assert payload["metadata"]["entity_name"] == "ACME"


class TestZepFact:
    def test_to_evermemos_payload(self):
        fact = ZepFact(fact="ACME stock rose 5%", rating=0.8)
        payload = fact.to_evermemos_payload(user_id="u1")
        assert payload["memory_type"] == EverMemType.event_log.value
        assert payload["content"] == "ACME stock rose 5%"
        assert payload["metadata"]["rating"] == 0.8


class TestZepSession:
    def test_roundtrip(self):
        data = {"session_id": "s1", "user_id": "u1", "created_at": "2026-03-20T10:00:00", "extra": "val"}
        session = ZepSession.from_evermemos(data)
        assert session.session_id == "s1"
        assert session.metadata["extra"] == "val"

        meta = session.to_evermemos_meta()
        assert meta["session_id"] == "s1"


# ===================================================================
# EverMemClient tests (mocked HTTP)
# ===================================================================


@pytest.mark.asyncio
class TestEverMemClient:
    async def test_store_memory(self, mock_evermemos_client):
        result = await mock_evermemos_client.store_memory(
            user_id="u1", message="test", role="human",
        )
        assert result["status"] == "created"
        mock_evermemos_client.store_memory.assert_awaited_once()

    async def test_search_memories(self, mock_evermemos_client):
        results = await mock_evermemos_client.search_memories(
            query="market", user_id="u1",
        )
        assert len(results) == 2
        assert "content" in results[0]

    async def test_get_memories(self, mock_evermemos_client):
        results = await mock_evermemos_client.get_memories(user_id="u1")
        assert len(results) == 2

    async def test_delete_memories(self, mock_evermemos_client):
        result = await mock_evermemos_client.delete_memories(user_id="u1")
        assert result["deleted"] == 2

    async def test_health_check(self, mock_evermemos_client):
        result = await mock_evermemos_client.health_check()
        assert result["status"] == "ok"


# ===================================================================
# ZepAdapter tests
# ===================================================================


@pytest.mark.asyncio
class TestZepAdapter:
    async def test_memory_add(self, mock_evermemos_client):
        from miromem.bridge.zep_adapter import ZepAdapter

        adapter = ZepAdapter.__new__(ZepAdapter)
        adapter._client = mock_evermemos_client

        from miromem.bridge.zep_adapter import _MemoryNamespace
        adapter.memory = _MemoryNamespace(mock_evermemos_client)

        await adapter.memory.add("sess-1", [
            {"role": "human", "content": "Hello"},
            {"role": "ai", "content": "Hi there"},
        ])
        assert mock_evermemos_client.store_memory.await_count == 2

    async def test_memory_search(self, mock_evermemos_client):
        from miromem.bridge.zep_adapter import _MemoryNamespace

        ns = _MemoryNamespace(mock_evermemos_client)
        results = await ns.search("sess-1", "market trends", limit=5)
        assert len(results) == 2
        assert results[0].message is not None

    async def test_memory_get(self, mock_evermemos_client):
        from miromem.bridge.zep_adapter import _MemoryNamespace

        ns = _MemoryNamespace(mock_evermemos_client)
        messages = await ns.get("sess-1")
        assert len(messages) == 2

    async def test_user_get(self, mock_evermemos_client):
        from miromem.bridge.zep_adapter import _UserNamespace

        ns = _UserNamespace(mock_evermemos_client)
        user = await ns.get("agent-001")
        assert user["user_id"] == "agent-001"