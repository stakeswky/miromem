"""Agent evolution engine — cross-simulation memory injection and tracking."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from miromem.bridge.memory_client import EverMemClient
from miromem.config.settings import load_config
from miromem.evolution.sim_memory_store import SimMemoryStore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentEvolution:
    """Retrieves and ranks historical memories for injection into new simulations."""

    def __init__(
        self,
        store: SimMemoryStore | None = None,
        evermem_client: EverMemClient | None = None,
    ) -> None:
        self._cfg = load_config()
        self._store = store or SimMemoryStore()
        self._evermem = evermem_client or EverMemClient()

    # --- Memory injection ---

    async def inject_historical_memory(
        self,
        agent_id: str,
        agent_identity: str,
        sim_context: str,
        *,
        top_k: int = 10,
        weights: dict[str, float] | None = None,
    ) -> str:
        """Retrieve and rank historical memories for a new simulation.

        Returns a formatted context string ready for prompt injection.
        """
        w = weights or {"relevance": 0.5, "decay": 0.3, "importance": 0.2}

        # 1. Fetch cross-sim memories for this agent
        raw_memories = await self._store.query_historical_memories(
            agent_identity, limit=top_k * 3,
        )

        if not raw_memories:
            return ""

        # 2. Enrich with EverMemOS search for relevance scoring
        relevance_scores: dict[str, float] = {}
        try:
            search_results = await self._evermem.search_memories(
                query=sim_context,
                user_id=agent_id,
                method="hybrid",
                top_k=top_k * 3,
            )
            for hit in search_results:
                mid = hit.get("metadata", {}).get("memory_id") or hit.get("id", "")
                relevance_scores[mid] = hit.get("score", 0.0)
        except Exception:
            pass  # graceful degradation — rank by importance + decay only

        # 3. Fetch foresight memories for predictive injection
        foresight_context = ""
        try:
            foresight_hits = await self._evermem.search_memories(
                query=sim_context,
                user_id=agent_id,
                memory_type="Foresight",
                top_k=3,
            )
            if foresight_hits:
                lines = [h.get("content", "") for h in foresight_hits if h.get("content")]
                if lines:
                    foresight_context = "\n[Foresight Predictions]\n" + "\n".join(f"- {l}" for l in lines)
        except Exception:
            pass

        # 4. Rank
        now = _utcnow()
        scored = self.rank_memories(raw_memories, relevance_scores, now, w)
        top = scored[:top_k]

        # 5. Format
        lines = ["[Historical Memory Context]"]
        for mem in top:
            lines.append(f"- (importance={mem['importance']:.2f}) {mem['memory_id']}")
        if foresight_context:
            lines.append(foresight_context)

        return "\n".join(lines)

    # --- Scoring helpers ---

    @staticmethod
    def compute_time_decay(memory_age_hours: float, half_life: float = 168.0) -> float:
        """Exponential decay: returns value in (0, 1]. half_life defaults to 1 week."""
        if memory_age_hours <= 0:
            return 1.0
        return math.exp(-0.693 * memory_age_hours / half_life)

    @staticmethod
    def rank_memories(
        memories: list[dict[str, Any]],
        relevance_scores: dict[str, float],
        now: datetime,
        weights: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Combine relevance, time decay, and importance into a final score."""
        w_rel = weights.get("relevance", 0.5)
        w_dec = weights.get("decay", 0.3)
        w_imp = weights.get("importance", 0.2)

        for mem in memories:
            rel = relevance_scores.get(mem.get("memory_id", ""), 0.0)
            created = mem.get("created_at")
            if isinstance(created, datetime):
                age_h = (now - created).total_seconds() / 3600
            else:
                age_h = 0.0
            decay = AgentEvolution.compute_time_decay(age_h)
            imp = mem.get("importance", 0.5)
            mem["_score"] = w_rel * rel + w_dec * decay + w_imp * imp

        memories.sort(key=lambda m: m.get("_score", 0), reverse=True)
        return memories

    # --- Evolution summary ---

    async def get_evolution_summary(self, agent_identity: str) -> dict[str, Any]:
        """Summarise how an agent has evolved across simulations."""
        memories = await self._store.query_historical_memories(
            agent_identity, limit=100,
        )
        if not memories:
            return {"agent_identity": agent_identity, "simulations": 0, "summary": "No history."}

        sim_ids = sorted({m["sim_id"] for m in memories})
        topic_counts: dict[str, int] = {}
        for m in memories:
            for t in m.get("topic_tags", []):
                topic_counts[t] = topic_counts.get(t, 0) + 1

        return {
            "agent_identity": agent_identity,
            "simulations": len(sim_ids),
            "sim_ids": sim_ids,
            "total_memories": len(memories),
            "top_topics": dict(sorted(topic_counts.items(), key=lambda x: -x[1])[:10]),
        }
