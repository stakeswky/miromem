"""Drop-in replacement for ``zep_cloud.ZepClient`` routing to EverMemOS.

Usage in MiroFish code::

    # Before:
    # from zep_cloud import ZepClient
    # zep = ZepClient(api_key=...)

    # After:
    from miromem.bridge.zep_adapter import ZepAdapter
    zep = ZepAdapter()
"""

from __future__ import annotations

import logging
from typing import Any

from miromem.bridge.memory_client import EverMemClient
from miromem.bridge.models import ZepMessage, ZepSearchResult, ZepSession
from miromem.config.settings import MiroMemConfig, load_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-namespace classes (mimic zep_cloud client structure)
# ---------------------------------------------------------------------------


class _MemoryNamespace:
    """``zep.memory.*`` methods."""

    def __init__(self, client: EverMemClient) -> None:
        self._c = client

    async def add(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """Store messages — equivalent to ``zep.memory.add(session_id, messages)``."""
        for msg in messages:
            zep_msg = ZepMessage(
                role=msg.get("role", msg.get("role_type", "human")),
                content=msg.get("content", ""),
                metadata=msg.get("metadata", {}),
            )
            await self._c.store_memory(
                user_id=session_id,
                message=zep_msg.content,
                role=zep_msg.role,
                group_id=msg.get("group_id"),
                metadata=zep_msg.metadata,
            )

    async def search(
        self,
        session_id: str,
        query: str,
        *,
        limit: int = 10,
        search_type: str = "hybrid",
        memory_type: str | None = None,
    ) -> list[ZepSearchResult]:
        """Search memories — equivalent to ``zep.memory.search(...)``."""
        hits = await self._c.search_memories(
            query=query,
            user_id=session_id,
            method=search_type,
            memory_type=memory_type,
            top_k=limit,
        )
        return [ZepSearchResult.from_evermemos(h) for h in hits]

    async def get(self, session_id: str) -> list[ZepMessage]:
        """Retrieve all messages — equivalent to ``zep.memory.get(session_id)``."""
        raw = await self._c.get_memories(user_id=session_id)
        results: list[ZepMessage] = []
        for item in raw:
            meta = item.get("metadata", {})
            results.append(
                ZepMessage(
                    uuid=meta.get("zep_uuid", ""),
                    role=meta.get("role", "ai"),
                    content=item.get("content", ""),
                    metadata=meta,
                )
            )
        return results

    async def get_session(self, session_id: str) -> ZepSession:
        """Get session metadata."""
        data = await self._c.get_conversation_meta(user_id=session_id)
        return ZepSession.from_evermemos({**data, "session_id": session_id})


class _GraphNamespace:
    """``zep.graph.*`` methods — placeholder for Knowledge Graph extension."""

    def __init__(self, client: EverMemClient) -> None:
        self._c = client

    async def add(self, group_id: str, data: str, **kwargs: Any) -> dict[str, Any]:
        """Add data to the knowledge graph.

        Currently a placeholder — will delegate to the KG extension API
        once Agent 3 implements ``/api/v1/graph``.
        """
        logger.warning("graph.add is a placeholder — KG extension not yet wired")
        return {"status": "pending", "group_id": group_id}


class _UserNamespace:
    """``zep.user.*`` methods."""

    def __init__(self, client: EverMemClient) -> None:
        self._c = client

    async def get(self, user_id: str) -> dict[str, Any]:
        """Get user profile — reads Profile-type memories from EverMemOS."""
        profiles = await self._c.get_memories(user_id=user_id, memory_type="Profile")
        if not profiles:
            return {"user_id": user_id}
        merged_meta: dict[str, Any] = {}
        for p in profiles:
            merged_meta.update(p.get("metadata", {}))
        return {"user_id": user_id, "metadata": merged_meta}


# ---------------------------------------------------------------------------
# Main adapter
# ---------------------------------------------------------------------------


class ZepAdapter:
    """Drop-in replacement for ``zep_cloud.ZepClient``.

    Exposes the same namespace structure (``memory``, ``graph``, ``user``)
    but routes all calls through :class:`EverMemClient` to EverMemOS.
    """

    def __init__(self, config: MiroMemConfig | None = None, **_kwargs: Any) -> None:
        cfg = config or load_config()
        self._client = EverMemClient(config=cfg)
        self.memory = _MemoryNamespace(self._client)
        self.graph = _GraphNamespace(self._client)
        self.user = _UserNamespace(self._client)

    async def close(self) -> None:
        """No-op — httpx clients are created per-request."""

    async def __aenter__(self) -> ZepAdapter:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()