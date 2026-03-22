"""Simulation lifecycle memory hooks.

These hooks are called at key points during a MiroFish simulation run
to read/write memories through EverMemOS via the bridge layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from miromem.bridge.memory_client import EverMemClient
from miromem.bridge.models import EverMemType
from miromem.config.settings import MiroMemConfig, load_config

logger = logging.getLogger(__name__)


@dataclass
class SimulationContext:
    """Identifies a running simulation for memory scoping."""

    simulation_id: str
    project_id: str
    round_number: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def group_id(self) -> str:
        """EverMemOS group_id scoping memories to this simulation."""
        return f"sim:{self.simulation_id}"


class SimulationMemoryHooks:
    """Lifecycle hooks that wire EverMemOS into each simulation phase."""

    def __init__(self, config: MiroMemConfig | None = None) -> None:
        self._client = EverMemClient(config=config or load_config())

    # -- Round start: inject relevant memories into agent context --

    async def on_round_start(
        self,
        ctx: SimulationContext,
        agent_ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Retrieve relevant memories for each agent at the start of a round.

        Returns a mapping of ``{agent_id: [memory_dicts]}`` that the
        simulation runner should inject into each agent's context window.
        """
        ctx.round_number += 0  # caller sets this before invoking
        memories_by_agent: dict[str, list[dict[str, Any]]] = {}

        for agent_id in agent_ids:
            try:
                hits = await self._client.search_memories(
                    query=f"round:{ctx.round_number} simulation context",
                    user_id=agent_id,
                    method="hybrid",
                    top_k=10,
                )
                memories_by_agent[agent_id] = hits
            except Exception:
                logger.warning("Failed to retrieve memories for agent %s", agent_id, exc_info=True)
                memories_by_agent[agent_id] = []

        logger.info(
            "on_round_start sim=%s round=%d agents=%d",
            ctx.simulation_id,
            ctx.round_number,
            len(agent_ids),
        )
        return memories_by_agent

    # -- Agent action: persist actions in real-time --

    async def on_agent_action(
        self,
        ctx: SimulationContext,
        agent_id: str,
        action_type: str,
        content: str,
        *,
        target_agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an agent action (post, like, follow, reply, etc.) to EverMemOS."""
        action_meta: dict[str, Any] = {
            "action_type": action_type,
            "simulation_id": ctx.simulation_id,
            "round": ctx.round_number,
            **(metadata or {}),
        }
        if target_agent_id:
            action_meta["target_agent_id"] = target_agent_id

        try:
            await self._client.store_memory(
                user_id=agent_id,
                message=content,
                role="agent",
                group_id=ctx.group_id,
                memory_type=EverMemType.event_log.value,
                metadata=action_meta,
            )
        except Exception:
            logger.warning("Failed to store action for agent %s: %s", agent_id, action_type, exc_info=True)

    # -- Round end: trigger memory consolidation --

    async def on_round_end(
        self,
        ctx: SimulationContext,
        agent_ids: list[str],
        round_summary: str = "",
    ) -> None:
        """Trigger MemCell extraction and memory consolidation at round end."""
        for agent_id in agent_ids:
            try:
                await self._client.store_memory(
                    user_id=agent_id,
                    message=round_summary or f"Round {ctx.round_number} completed",
                    role="system",
                    group_id=ctx.group_id,
                    memory_type=EverMemType.mem_cell.value,
                    metadata={
                        "simulation_id": ctx.simulation_id,
                        "round": ctx.round_number,
                        "hook": "round_end",
                    },
                )
            except Exception:
                logger.warning("Failed round-end consolidation for agent %s", agent_id, exc_info=True)

        logger.info("on_round_end sim=%s round=%d", ctx.simulation_id, ctx.round_number)

    # -- Simulation end: generate summary memories --

    async def on_simulation_end(
        self,
        ctx: SimulationContext,
        agent_ids: list[str],
        simulation_summary: str = "",
    ) -> None:
        """Generate Episodic + Foresight summary memories at simulation end."""
        for agent_id in agent_ids:
            # Episodic summary
            try:
                await self._client.store_memory(
                    user_id=agent_id,
                    message=simulation_summary or f"Simulation {ctx.simulation_id} completed",
                    role="system",
                    group_id=ctx.group_id,
                    memory_type=EverMemType.episodic.value,
                    metadata={
                        "simulation_id": ctx.simulation_id,
                        "total_rounds": ctx.round_number,
                        "hook": "simulation_end",
                        "summary_type": "episodic",
                    },
                )
            except Exception:
                logger.warning("Failed episodic summary for agent %s", agent_id, exc_info=True)

            # Foresight — forward-looking prediction based on simulation
            try:
                await self._client.store_memory(
                    user_id=agent_id,
                    message=f"[Foresight] Based on simulation {ctx.simulation_id}: {simulation_summary}",
                    role="system",
                    group_id=ctx.group_id,
                    memory_type=EverMemType.foresight.value,
                    metadata={
                        "simulation_id": ctx.simulation_id,
                        "total_rounds": ctx.round_number,
                        "hook": "simulation_end",
                        "summary_type": "foresight",
                    },
                )
            except Exception:
                logger.warning("Failed foresight memory for agent %s", agent_id, exc_info=True)

        logger.info("on_simulation_end sim=%s rounds=%d", ctx.simulation_id, ctx.round_number)