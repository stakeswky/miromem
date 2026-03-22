"""Bidirectional sync between OASIS agent profiles and EverMemOS Profile Memory.

MiroFish generates rich agent personas via ``oasis_profile_generator``.
This module keeps those profiles in sync with EverMemOS so that:
- Profiles created in MiroFish are persisted as Profile memories.
- Profile updates from simulation (trait drift, opinion changes) are
  written back to EverMemOS.
- On simulation start, the latest Profile memory is loaded to hydrate
  the agent's persona.
"""

from __future__ import annotations

import logging
from typing import Any

from miromem.bridge.memory_client import EverMemClient
from miromem.bridge.models import EverMemType
from miromem.config.settings import MiroMemConfig, load_config

logger = logging.getLogger(__name__)


# Standard profile fields that map between MiroFish and EverMemOS
_PROFILE_FIELDS = (
    "name",
    "age",
    "gender",
    "occupation",
    "personality",
    "interests",
    "political_leaning",
    "social_style",
    "bio",
)


class ProfileSync:
    """Bidirectional profile synchronisation."""

    def __init__(self, config: MiroMemConfig | None = None) -> None:
        self._client = EverMemClient(config=config or load_config())

    # -- MiroFish → EverMemOS --

    async def push_profile(
        self,
        agent_id: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Push a MiroFish agent profile into EverMemOS as a Profile memory."""
        bio = profile.get("bio", profile.get("name", agent_id))
        metadata = {k: profile[k] for k in _PROFILE_FIELDS if k in profile}
        # Include any extra fields not in the standard set
        for k, v in profile.items():
            if k not in metadata and k not in ("id", "_id"):
                metadata[k] = v

        return await self._client.store_memory(
            user_id=agent_id,
            message=bio,
            role="system",
            memory_type=EverMemType.profile.value,
            metadata=metadata,
        )

    async def push_profiles_batch(
        self,
        profiles: dict[str, dict[str, Any]],
    ) -> int:
        """Push multiple agent profiles. Returns count of successful writes."""
        ok = 0
        for agent_id, profile in profiles.items():
            try:
                await self.push_profile(agent_id, profile)
                ok += 1
            except Exception:
                logger.warning("Failed to push profile for %s", agent_id, exc_info=True)
        logger.info("Pushed %d/%d profiles to EverMemOS", ok, len(profiles))
        return ok

    # -- EverMemOS → MiroFish --

    async def pull_profile(self, agent_id: str) -> dict[str, Any]:
        """Pull the latest Profile memory from EverMemOS for an agent.

        Returns a dict compatible with MiroFish's agent profile format.
        If no profile exists, returns a minimal stub.
        """
        memories = await self._client.get_memories(
            user_id=agent_id,
            memory_type=EverMemType.profile.value,
        )
        if not memories:
            return {"agent_id": agent_id}

        # Merge all profile memories (latest wins for duplicate keys)
        merged: dict[str, Any] = {"agent_id": agent_id}
        for mem in memories:
            meta = mem.get("metadata", {})
            merged.update(meta)
            if "content" in mem and "bio" not in merged:
                merged["bio"] = mem["content"]
        return merged

    async def pull_profiles_batch(
        self,
        agent_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Pull profiles for multiple agents."""
        result: dict[str, dict[str, Any]] = {}
        for agent_id in agent_ids:
            try:
                result[agent_id] = await self.pull_profile(agent_id)
            except Exception:
                logger.warning("Failed to pull profile for %s", agent_id, exc_info=True)
                result[agent_id] = {"agent_id": agent_id}
        return result

    # -- Incremental update --

    async def update_profile(
        self,
        agent_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply incremental updates to an agent's profile.

        Pulls the current profile, merges *updates*, and pushes back.
        """
        current = await self.pull_profile(agent_id)
        current.update(updates)
        return await self.push_profile(agent_id, current)

    # -- Diff detection --

    async def has_changed(
        self,
        agent_id: str,
        local_profile: dict[str, Any],
    ) -> bool:
        """Check whether the remote profile differs from *local_profile*."""
        remote = await self.pull_profile(agent_id)
        for key in _PROFILE_FIELDS:
            if local_profile.get(key) != remote.get(key):
                return True
        return False

    # -- Spec-aligned aliases --

    async def sync_to_evermemos(
        self,
        oasis_profiles: dict[str, dict[str, Any]],
    ) -> int:
        """Store OASIS agent profiles as Profile memories in EverMemOS.

        Takes a dict of ``{agent_id: profile_dict}`` as produced by
        ``oasis_profile_generator.py`` and pushes each to EverMemOS.
        Maps OASIS fields (name, personality, bio, traits) to EverMemOS
        profile format.  Returns count of successful writes.
        """
        return await self.push_profiles_batch(oasis_profiles)

    async def sync_from_evermemos(
        self,
        agent_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Read evolved profiles from EverMemOS and convert to OASIS format.

        Returns ``{agent_id: oasis_compatible_profile}``.
        """
        return await self.pull_profiles_batch(agent_ids)

    @staticmethod
    def merge_profiles(
        oasis_profile: dict[str, Any],
        evermemos_profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge a fresh OASIS-generated profile with existing EverMemOS data.

        Strategy: base attributes (name, age, gender, occupation) come from
        *oasis_profile*; learned/evolved traits (personality, interests,
        political_leaning, social_style) are preserved from *evermemos_profile*
        if present; everything else falls back to *oasis_profile*.
        """
        _LEARNED_FIELDS = {"personality", "interests", "political_leaning", "social_style"}
        _BASE_FIELDS = {"name", "age", "gender", "occupation", "bio"}

        merged: dict[str, Any] = {}
        # Start with all oasis fields
        merged.update(oasis_profile)
        # Overlay learned traits from EverMemOS if they exist
        for field in _LEARNED_FIELDS:
            if field in evermemos_profile:
                merged[field] = evermemos_profile[field]
        # Preserve any extra EverMemOS-only keys (e.g. evolved attributes)
        for k, v in evermemos_profile.items():
            if k not in merged and k not in ("agent_id", "id", "_id"):
                merged[k] = v
        return merged