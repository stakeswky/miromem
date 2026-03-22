"""Simulation-level memory storage for cross-simulation persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from miromem.bridge.memory_client import EverMemClient
from miromem.config.settings import load_config


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SimMemoryStore:
    """Manages cross-simulation memory tagging and retrieval via MongoDB + EverMemOS."""

    def __init__(
        self,
        db: AsyncIOMotorDatabase | None = None,
        evermem_client: EverMemClient | None = None,
    ) -> None:
        cfg = load_config()
        if db is not None:
            self._db = db
        else:
            client: AsyncIOMotorClient = AsyncIOMotorClient(cfg.infra.mongodb_uri)
            self._db = client[cfg.infra.mongodb_db]

        self._col = self._db["cross_sim_memories"]
        self._sims = self._db["simulations"]
        self._evermem = evermem_client or EverMemClient()

    async def ensure_indexes(self) -> None:
        await self._col.create_index("sim_id")
        await self._col.create_index("agent_id")
        await self._col.create_index("topic_tags")
        await self._col.create_index("importance")
        await self._sims.create_index("sim_id", unique=True)

    # --- Mark memories as cross-sim available ---

    async def mark_cross_sim_available(
        self,
        sim_id: str,
        memory_ids: list[str],
        importance_scores: dict[str, float],
        *,
        agent_id: str = "",
        topic_tags: list[str] | None = None,
    ) -> int:
        """Tag memories from a completed simulation as available for future sims.

        Returns the number of records inserted.
        """
        docs = []
        now = _utcnow()
        for mid in memory_ids:
            docs.append({
                "sim_id": sim_id,
                "memory_id": mid,
                "agent_id": agent_id,
                "importance": importance_scores.get(mid, 0.5),
                "topic_tags": topic_tags or [],
                "created_at": now,
            })
        if docs:
            await self._col.insert_many(docs)
        return len(docs)

    # --- Query historical memories ---

    async def query_historical_memories(
        self,
        agent_identity: str,
        *,
        topic: str | None = None,
        sim_ids: list[str] | None = None,
        time_range: tuple[datetime, datetime] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search cross-sim memories by agent identity, topic, and time range."""
        query: dict[str, Any] = {"agent_id": agent_identity}
        if sim_ids:
            query["sim_id"] = {"$in": sim_ids}
        if topic:
            query["topic_tags"] = topic
        if time_range:
            query["created_at"] = {"$gte": time_range[0], "$lte": time_range[1]}

        cursor = self._col.find(query).sort("importance", -1).limit(limit)
        results: list[dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    # --- Simulation metadata ---

    async def register_simulation(
        self, sim_id: str, *, metadata: dict[str, Any] | None = None
    ) -> None:
        """Record a simulation run."""
        await self._sims.update_one(
            {"sim_id": sim_id},
            {"$set": {"sim_id": sim_id, "metadata": metadata or {}, "created_at": _utcnow()}},
            upsert=True,
        )

    async def get_simulation_summary(self, sim_id: str) -> dict[str, Any]:
        """Aggregated summary of a past simulation's key memories."""
        sim_doc = await self._sims.find_one({"sim_id": sim_id})
        if not sim_doc:
            return {"error": f"Simulation {sim_id} not found"}

        cursor = self._col.find({"sim_id": sim_id}).sort("importance", -1)
        memories: list[dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            memories.append(doc)

        sim_doc.pop("_id", None)
        return {
            "simulation": sim_doc,
            "memory_count": len(memories),
            "top_memories": memories[:10],
            "topic_distribution": self._topic_distribution(memories),
        }

    async def list_simulations(self, limit: int = 50) -> list[dict[str, Any]]:
        """List past simulations ordered by recency."""
        cursor = self._sims.find().sort("created_at", -1).limit(limit)
        results: list[dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    @staticmethod
    def _topic_distribution(memories: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for m in memories:
            for tag in m.get("topic_tags", []):
                counts[tag] = counts.get(tag, 0) + 1
        return counts
