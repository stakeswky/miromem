"""Memory interface for OASIS simulation agents.

Provides each agent with a scoped view of EverMemOS, allowing them
to store observations, recall past experiences, and query the
knowledge graph — all within the context of a running simulation.
"""

from __future__ import annotations

import logging
from typing import Any

from miromem.bridge.memory_client import EverMemClient
from miromem.bridge.models import EverMemType, SearchMethod
from miromem.config.settings import MiroMemConfig, load_config

logger = logging.getLogger(__name__)


class AgentMemoryProvider:
    """Per-agent memory facade used inside simulation loops.

    Each agent gets an instance scoped to its ``agent_id`` and the
    current ``simulation_id``.  The provider exposes high-level
    operations that the simulation runner or agent logic can call
    without knowing EverMemOS internals.
    """

    def __init__(
        self,
        agent_id: str,
        simulation_id: str,
        config: MiroMemConfig | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.simulation_id = simulation_id
        self._group_id = f"sim:{simulation_id}"
        self._client = EverMemClient(config=config or load_config())

    # -- Recall --

    async def recall(
        self,
        query: str,
        *,
        method: str = SearchMethod.hybrid,
        top_k: int = 5,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search the agent's memories relevant to *query*."""
        return await self._client.search_memories(
            query=query,
            user_id=self.agent_id,
            method=method,
            memory_type=memory_type,
            top_k=top_k,
        )

    async def get_all(
        self,
        *,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve all memories for this agent, optionally filtered by type."""
        return await self._client.get_memories(
            user_id=self.agent_id,
            memory_type=memory_type,
            group_id=self._group_id,
        )

    async def get_profile(self) -> dict[str, Any]:
        """Return the agent's Profile memory (persona, traits, etc.)."""
        profiles = await self._client.get_memories(
            user_id=self.agent_id,
            memory_type=EverMemType.profile.value,
        )
        if not profiles:
            return {"agent_id": self.agent_id}
        merged: dict[str, Any] = {"agent_id": self.agent_id}
        for p in profiles:
            merged.update(p.get("metadata", {}))
        return merged

    # -- Store --

    async def observe(
        self,
        content: str,
        *,
        memory_type: str = EverMemType.episodic.value,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store a new observation / experience."""
        return await self._client.store_memory(
            user_id=self.agent_id,
            message=content,
            role="agent",
            group_id=self._group_id,
            memory_type=memory_type,
            metadata={
                "simulation_id": self.simulation_id,
                **(metadata or {}),
            },
        )

    async def record_action(
        self,
        action_type: str,
        content: str,
        *,
        target_agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a discrete agent action as an EventLog."""
        meta: dict[str, Any] = {
            "action_type": action_type,
            "simulation_id": self.simulation_id,
            **(metadata or {}),
        }
        if target_agent_id:
            meta["target_agent_id"] = target_agent_id
        return await self._client.store_memory(
            user_id=self.agent_id,
            message=content,
            role="agent",
            group_id=self._group_id,
            memory_type=EverMemType.event_log.value,
            metadata=meta,
        )

    # -- Context builder --

    async def get_agent_context(
        self,
        agent_id: str | None = None,
        sim_id: str | None = None,
        query: str | None = None,
    ) -> str:
        """Retrieve combined context for an agent, formatted for LLM injection.

        Combines: profile memory + recent episodic memories + relevant
        foresight predictions into a single context string.

        *agent_id* and *sim_id* default to the instance's values if omitted.
        """
        aid = agent_id or self.agent_id
        # Temporarily swap if caller overrides
        orig_agent, orig_sim = self.agent_id, self.simulation_id
        if agent_id:
            self.agent_id = aid
        if sim_id:
            self.simulation_id = sim_id
            self._group_id = f"sim:{sim_id}"

        sections: list[str] = []

        # 1. Profile
        profile = await self.get_profile()
        if profile and len(profile) > 1:
            profile_lines = [f"  {k}: {v}" for k, v in profile.items() if k != "agent_id"]
            sections.append("[Profile]\n" + "\n".join(profile_lines))

        # 2. Episodic memories (recent or query-relevant)
        episodic = await self.recall(
            query or "recent events",
            memory_type=EverMemType.episodic.value,
            top_k=5,
        )
        if episodic:
            lines = [f"  - {h.get('content', '')}" for h in episodic]
            sections.append("[Recent Memories]\n" + "\n".join(lines))

        # 3. Foresight predictions
        foresight = await self.recall(
            query or "predictions",
            memory_type=EverMemType.foresight.value,
            top_k=3,
        )
        if foresight:
            lines = [f"  - {h.get('content', '')}" for h in foresight]
            sections.append("[Foresight]\n" + "\n".join(lines))

        # Restore originals
        self.agent_id, self.simulation_id = orig_agent, orig_sim
        self._group_id = f"sim:{orig_sim}"

        return "\n\n".join(sections)

    async def record_agent_thought(
        self,
        agent_id: str | None = None,
        sim_id: str | None = None,
        thought: str = "",
    ) -> dict[str, Any]:
        """Store an agent's internal reasoning as an episodic memory."""
        aid = agent_id or self.agent_id
        sid = sim_id or self.simulation_id
        return await self._client.store_memory(
            user_id=aid,
            message=thought,
            role="agent",
            group_id=f"sim:{sid}",
            memory_type=EverMemType.episodic.value,
            metadata={
                "simulation_id": sid,
                "memory_subtype": "thought",
            },
        )

    async def build_context(
        self,
        situation: str,
        *,
        max_memories: int = 10,
    ) -> str:
        """Build a text context block from relevant memories for LLM injection.

        Returns a formatted string suitable for inserting into an agent's
        system prompt or context window.
        """
        hits = await self.recall(situation, top_k=max_memories)
        if not hits:
            return ""
        lines = [f"[Memory {i+1}] {h.get('content', '')}" for i, h in enumerate(hits)]
        return "\n".join(lines)

    async def update_agent_profile(
        self,
        agent_id: str | None = None,
        updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Push profile updates to EverMemOS for this agent."""
        aid = agent_id or self.agent_id
        current = await self.get_profile()
        current.update(updates or {})
        bio = current.get("bio", current.get("name", aid))
        return await self._client.store_memory(
            user_id=aid,
            message=bio,
            role="system",
            memory_type=EverMemType.profile.value,
            metadata=current,
        )