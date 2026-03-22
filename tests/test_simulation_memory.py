"""Tests for miromem.simulation — hooks, agent provider, profile sync."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from miromem.simulation.memory_hooks import SimulationContext, SimulationMemoryHooks
from miromem.simulation.profile_sync import ProfileSync


# ===================================================================
# SimulationMemoryHooks tests
# ===================================================================


@pytest.mark.asyncio
class TestSimulationMemoryHooks:
    def _make_hooks(self, mock_client: AsyncMock) -> SimulationMemoryHooks:
        hooks = SimulationMemoryHooks.__new__(SimulationMemoryHooks)
        hooks._client = mock_client
        return hooks

    def _ctx(self, round_num: int = 1) -> SimulationContext:
        return SimulationContext(
            simulation_id="sim-001", project_id="proj-001", round_number=round_num,
        )

    async def test_on_round_start(self, mock_evermemos_client):
        hooks = self._make_hooks(mock_evermemos_client)
        result = await hooks.on_round_start(self._ctx(), ["agent-a", "agent-b"])

        assert "agent-a" in result
        assert "agent-b" in result
        assert mock_evermemos_client.search_memories.await_count == 2

    async def test_on_agent_action(self, mock_evermemos_client):
        hooks = self._make_hooks(mock_evermemos_client)
        await hooks.on_agent_action(
            self._ctx(), "agent-a", "CREATE_POST", "Bullish on tech",
        )
        mock_evermemos_client.store_memory.assert_awaited_once()
        call_kwargs = mock_evermemos_client.store_memory.call_args.kwargs
        assert call_kwargs["memory_type"] == "EventLog"
        assert call_kwargs["metadata"]["action_type"] == "CREATE_POST"

    async def test_on_round_end(self, mock_evermemos_client):
        hooks = self._make_hooks(mock_evermemos_client)
        await hooks.on_round_end(self._ctx(), ["agent-a"], round_summary="Round 1 done")
        mock_evermemos_client.store_memory.assert_awaited_once()
        call_kwargs = mock_evermemos_client.store_memory.call_args.kwargs
        assert call_kwargs["memory_type"] == "MemCell"

    async def test_on_simulation_end(self, mock_evermemos_client):
        hooks = self._make_hooks(mock_evermemos_client)
        await hooks.on_simulation_end(self._ctx(5), ["agent-a"], simulation_summary="Sim done")
        # 2 calls per agent: episodic + foresight
        assert mock_evermemos_client.store_memory.await_count == 2

    async def test_on_agent_action_error_handling(self, mock_evermemos_client):
        mock_evermemos_client.store_memory.side_effect = Exception("network error")
        hooks = self._make_hooks(mock_evermemos_client)
        # Should not raise
        await hooks.on_agent_action(self._ctx(), "agent-a", "LIKE", "liked a post")


# ===================================================================
# AgentMemoryProvider tests
# ===================================================================


@pytest.mark.asyncio
class TestAgentMemoryProvider:
    def _make_provider(self, mock_client: AsyncMock):
        from miromem.simulation.agent_memory_provider import AgentMemoryProvider

        provider = AgentMemoryProvider.__new__(AgentMemoryProvider)
        provider.agent_id = "agent-a"
        provider.simulation_id = "sim-001"
        provider._group_id = "sim:sim-001"
        provider._client = mock_client
        return provider

    async def test_get_agent_context(self, mock_evermemos_client):
        provider = self._make_provider(mock_evermemos_client)
        context = await provider.get_agent_context()

        assert isinstance(context, str)
        # Should have called search for episodic + foresight, and get for profile
        assert mock_evermemos_client.search_memories.await_count >= 2
        assert mock_evermemos_client.get_memories.await_count >= 1

    async def test_record_agent_thought(self, mock_evermemos_client):
        provider = self._make_provider(mock_evermemos_client)
        result = await provider.record_agent_thought(thought="I think the market will drop")

        mock_evermemos_client.store_memory.assert_awaited_once()
        call_kwargs = mock_evermemos_client.store_memory.call_args.kwargs
        assert call_kwargs["memory_type"] == "EpisodicMemory"
        assert call_kwargs["metadata"]["memory_subtype"] == "thought"

    async def test_recall(self, mock_evermemos_client):
        provider = self._make_provider(mock_evermemos_client)
        results = await provider.recall("market trends")
        assert len(results) == 2

    async def test_build_context(self, mock_evermemos_client):
        provider = self._make_provider(mock_evermemos_client)
        ctx = await provider.build_context("market outlook")
        assert "[Memory 1]" in ctx


# ===================================================================
# ProfileSync tests
# ===================================================================


@pytest.mark.asyncio
class TestProfileSync:
    def _make_sync(self, mock_client: AsyncMock) -> ProfileSync:
        sync = ProfileSync.__new__(ProfileSync)
        sync._client = mock_client
        return sync

    async def test_push_profile(self, mock_evermemos_client):
        sync = self._make_sync(mock_evermemos_client)
        result = await sync.push_profile("agent-a", {
            "name": "Alice", "bio": "Data scientist", "personality": "analytical",
        })
        mock_evermemos_client.store_memory.assert_awaited_once()
        call_kwargs = mock_evermemos_client.store_memory.call_args.kwargs
        assert call_kwargs["memory_type"] == "Profile"

    async def test_pull_profile(self, mock_evermemos_client):
        sync = self._make_sync(mock_evermemos_client)
        profile = await sync.pull_profile("agent-a")
        assert profile["agent_id"] == "agent-a"
        assert "name" in profile  # from mock metadata

    async def test_sync_to_evermemos(self, mock_evermemos_client):
        sync = self._make_sync(mock_evermemos_client)
        count = await sync.sync_to_evermemos({
            "agent-a": {"name": "Alice", "bio": "Scientist"},
            "agent-b": {"name": "Bob", "bio": "Trader"},
        })
        assert count == 2

    async def test_sync_from_evermemos(self, mock_evermemos_client):
        sync = self._make_sync(mock_evermemos_client)
        profiles = await sync.sync_from_evermemos(["agent-a", "agent-b"])
        assert len(profiles) == 2

    def test_merge_profiles(self):
        oasis = {"name": "Alice", "age": 30, "personality": "calm", "bio": "New bio"}
        evermemos = {"name": "Alice", "personality": "evolved-analytical", "interests": ["AI"]}

        merged = ProfileSync.merge_profiles(oasis, evermemos)

        # Base fields from OASIS
        assert merged["age"] == 30
        assert merged["bio"] == "New bio"
        # Learned fields preserved from EverMemOS
        assert merged["personality"] == "evolved-analytical"
        assert merged["interests"] == ["AI"]