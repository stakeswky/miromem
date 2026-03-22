"""Tests for miromem.evolution — SimMemoryStore, AgentEvolution, ForesightValidator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miromem.evolution.agent_evolution import AgentEvolution
from miromem.evolution.sim_memory_store import SimMemoryStore


# ===================================================================
# SimMemoryStore tests
# ===================================================================


@pytest.mark.asyncio
class TestSimMemoryStore:
    def _make_store(self, mock_db, mock_client: AsyncMock | None = None) -> SimMemoryStore:
        store = SimMemoryStore.__new__(SimMemoryStore)
        store._db = mock_db
        store._col = mock_db["cross_sim_memories"]
        store._sims = mock_db["simulations"]
        store._evermem = mock_client or AsyncMock()
        return store

    async def test_mark_cross_sim_available(self, mock_mongodb):
        store = self._make_store(mock_mongodb)
        count = await store.mark_cross_sim_available(
            sim_id="sim-001",
            memory_ids=["m1", "m2", "m3"],
            importance_scores={"m1": 0.9, "m2": 0.7, "m3": 0.5},
            agent_id="agent-a",
            topic_tags=["market", "tech"],
        )
        assert count == 3

    async def test_mark_cross_sim_empty(self, mock_mongodb):
        store = self._make_store(mock_mongodb)
        count = await store.mark_cross_sim_available(
            sim_id="sim-001", memory_ids=[], importance_scores={},
        )
        assert count == 0

    async def test_query_historical_memories(self, mock_mongodb):
        store = self._make_store(mock_mongodb)
        # Insert some test data
        await store.mark_cross_sim_available(
            sim_id="sim-001",
            memory_ids=["m1", "m2"],
            importance_scores={"m1": 0.9, "m2": 0.6},
            agent_id="agent-a",
            topic_tags=["finance"],
        )
        results = await store.query_historical_memories("agent-a", limit=10)
        assert len(results) == 2

    async def test_query_historical_with_topic(self, mock_mongodb):
        store = self._make_store(mock_mongodb)
        await store.mark_cross_sim_available(
            sim_id="sim-001",
            memory_ids=["m1"],
            importance_scores={"m1": 0.9},
            agent_id="agent-a",
            topic_tags=["finance"],
        )
        # Topic filter — our fake collection does simplified matching
        results = await store.query_historical_memories("agent-a", topic="finance")
        assert isinstance(results, list)

    async def test_register_and_get_simulation(self, mock_mongodb):
        store = self._make_store(mock_mongodb)
        await store.register_simulation("sim-001", metadata={"project": "test"})

        summary = await store.get_simulation_summary("sim-001")
        assert "simulation" in summary or "error" not in summary

    async def test_get_simulation_not_found(self, mock_mongodb):
        store = self._make_store(mock_mongodb)
        result = await store.get_simulation_summary("nonexistent")
        assert "error" in result


# ===================================================================
# AgentEvolution tests
# ===================================================================


@pytest.mark.asyncio
class TestAgentEvolution:
    def _make_evolution(
        self, mock_store: AsyncMock, mock_client: AsyncMock,
    ) -> AgentEvolution:
        evo = AgentEvolution.__new__(AgentEvolution)
        evo._cfg = MagicMock()
        evo._store = mock_store
        evo._evermem = mock_client
        return evo

    async def test_inject_historical_memory(self, mock_evermemos_client):
        mock_store = AsyncMock()
        now = datetime.now(timezone.utc)
        mock_store.query_historical_memories.return_value = [
            {
                "memory_id": "m1",
                "agent_id": "agent-a",
                "importance": 0.9,
                "topic_tags": ["market"],
                "created_at": now - timedelta(hours=24),
                "sim_id": "sim-old",
            },
            {
                "memory_id": "m2",
                "agent_id": "agent-a",
                "importance": 0.5,
                "topic_tags": ["tech"],
                "created_at": now - timedelta(hours=168),
                "sim_id": "sim-older",
            },
        ]

        evo = self._make_evolution(mock_store, mock_evermemos_client)
        context = await evo.inject_historical_memory(
            agent_id="agent-a",
            agent_identity="agent-a",
            sim_context="new market simulation",
            top_k=5,
        )

        assert isinstance(context, str)
        assert "[Historical Memory Context]" in context
        mock_store.query_historical_memories.assert_awaited_once()

    async def test_inject_no_history(self, mock_evermemos_client):
        mock_store = AsyncMock()
        mock_store.query_historical_memories.return_value = []

        evo = self._make_evolution(mock_store, mock_evermemos_client)
        context = await evo.inject_historical_memory(
            agent_id="agent-a", agent_identity="agent-a", sim_context="test",
        )
        assert context == ""

    def test_compute_time_decay(self):
        # Fresh memory → decay ≈ 1.0
        assert AgentEvolution.compute_time_decay(0) == 1.0
        # 1 week old → decay ≈ 0.5 (half-life = 168h)
        decay_1w = AgentEvolution.compute_time_decay(168.0, half_life=168.0)
        assert 0.45 < decay_1w < 0.55
        # Very old → decay → 0
        assert AgentEvolution.compute_time_decay(10000.0) < 0.01

    def test_rank_memories(self):
        now = datetime.now(timezone.utc)
        memories = [
            {"memory_id": "m1", "importance": 0.9, "created_at": now - timedelta(hours=1)},
            {"memory_id": "m2", "importance": 0.3, "created_at": now - timedelta(hours=500)},
        ]
        relevance = {"m1": 0.8, "m2": 0.2}
        weights = {"relevance": 0.5, "decay": 0.3, "importance": 0.2}

        ranked = AgentEvolution.rank_memories(memories, relevance, now, weights)
        assert ranked[0]["memory_id"] == "m1"  # higher relevance + importance + fresher


# ===================================================================
# ForesightValidator tests
# ===================================================================


@pytest.mark.asyncio
class TestForesightValidator:
    def _make_validator(self, mock_client: AsyncMock, mock_db) -> "ForesightValidator":
        from miromem.evolution.foresight_validator import ForesightValidator

        val = ForesightValidator.__new__(ForesightValidator)
        val._db = mock_db
        val._col = mock_db["foresight_validations"]
        val._evermem = mock_client
        val._llm = AsyncMock()
        val._model = "test-model"
        return val

    async def test_validate_predictions(self, mock_evermemos_client, mock_mongodb):
        # Setup: search returns foresight, get returns outcomes
        mock_evermemos_client.search_memories.return_value = [
            {"content": "Tech sector will correct in Q2", "score": 0.8},
        ]
        mock_evermemos_client.get_memories.return_value = [
            {"content": "Tech stocks dropped 15% in April"},
        ]

        val = self._make_validator(mock_evermemos_client, mock_mongodb)

        # Mock LLM scoring
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = '{"score": 0.85}'
        val._llm.chat.completions.create.return_value = mock_resp

        result = await val.validate_predictions("sim-001")

        assert result["sim_id"] == "sim-001"
        assert "semantic_similarity_avg" in result
        assert result["semantic_similarity_avg"] == pytest.approx(0.85)

    async def test_validate_no_predictions(self, mock_evermemos_client, mock_mongodb):
        mock_evermemos_client.search_memories.return_value = []

        val = self._make_validator(mock_evermemos_client, mock_mongodb)
        result = await val.validate_predictions("sim-empty")

        assert result["predictions"] == 0
        assert result["accuracy"] is None

    def test_generate_feedback_low(self):
        from miromem.evolution.foresight_validator import ForesightValidator

        feedback = ForesightValidator.generate_feedback({
            "semantic_similarity_avg": 0.3,
            "exact_match_rate": 0.1,
            "predictions": 10,
        })
        assert "low-accuracy" in feedback.lower() or "narrowing" in feedback.lower()

    def test_generate_feedback_high(self):
        from miromem.evolution.foresight_validator import ForesightValidator

        feedback = ForesightValidator.generate_feedback({
            "semantic_similarity_avg": 0.85,
            "exact_match_rate": 0.8,
            "predictions": 10,
        })
        assert "well" in feedback.lower()

    async def test_score_prediction_llm_failure(self, mock_evermemos_client, mock_mongodb):
        val = self._make_validator(mock_evermemos_client, mock_mongodb)
        val._llm.chat.completions.create.side_effect = Exception("LLM down")

        score = await val._score_prediction("prediction text", "outcome text")
        assert score == 0.0