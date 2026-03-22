"""Data model mapping between Zep Cloud and EverMemOS formats."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EverMemType(str, Enum):
    """EverMemOS memory types."""

    mem_cell = "MemCell"
    episodic = "EpisodicMemory"
    foresight = "Foresight"
    event_log = "EventLog"
    profile = "Profile"


class SearchMethod(str, Enum):
    """EverMemOS retrieval methods."""

    keyword = "keyword"
    vector = "vector"
    hybrid = "hybrid"
    rrf = "rrf"
    agentic = "agentic"


# ---------------------------------------------------------------------------
# Zep-compatible models (what MiroFish code expects)
# ---------------------------------------------------------------------------


class ZepMessage(BaseModel):
    """A single chat message in Zep format."""

    uuid: str = Field(default_factory=lambda: uuid4().hex)
    role: str  # "human" | "ai" | "system"
    role_type: str = ""  # Zep role_type, mapped from role
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    token_count: int = 0

    def to_evermemos_payload(self, user_id: str, group_id: str | None = None) -> dict[str, Any]:
        """Convert to EverMemOS memory creation payload."""
        payload: dict[str, Any] = {
            "user_id": user_id,
            "content": self.content,
            "memory_type": EverMemType.episodic.value,
            "metadata": {
                **self.metadata,
                "role": self.role,
                "zep_uuid": self.uuid,
                "created_at": self.created_at.isoformat(),
            },
        }
        if group_id:
            payload["group_id"] = group_id
        return payload


class ZepSearchResult(BaseModel):
    """A single search result in Zep format."""

    message: ZepMessage | None = None
    summary: str | None = None
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    dist: float = 0.0  # Zep distance metric

    @classmethod
    def from_evermemos(cls, hit: dict[str, Any]) -> ZepSearchResult:
        """Build from an EverMemOS search result dict."""
        meta = hit.get("metadata", {})
        return cls(
            message=ZepMessage(
                uuid=meta.get("zep_uuid", uuid4().hex),
                role=meta.get("role", "ai"),
                content=hit.get("content", ""),
                metadata=meta,
                created_at=datetime.fromisoformat(meta["created_at"]) if "created_at" in meta else datetime.utcnow(),
            ),
            summary=hit.get("summary"),
            score=hit.get("score", 0.0),
            dist=1.0 - hit.get("score", 0.0),
            metadata=meta,
        )


class ZepEntity(BaseModel):
    """An entity extracted from Zep's knowledge graph."""

    name: str
    entity_type: str = "UNKNOWN"
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_evermemos_payload(self, user_id: str) -> dict[str, Any]:
        """Convert to EverMemOS Profile memory."""
        return {
            "user_id": user_id,
            "content": self.description or self.name,
            "memory_type": EverMemType.profile.value,
            "metadata": {
                "entity_name": self.name,
                "entity_type": self.entity_type,
                **self.attributes,
            },
        }


class ZepEdge(BaseModel):
    """A relationship between two entities."""

    source: str
    target: str
    relation: str
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_evermemos_payload(self, user_id: str) -> dict[str, Any]:
        """Convert to EverMemOS EventLog memory."""
        return {
            "user_id": user_id,
            "content": f"{self.source} --[{self.relation}]--> {self.target}",
            "memory_type": EverMemType.event_log.value,
            "metadata": {
                "source_entity": self.source,
                "target_entity": self.target,
                "relation": self.relation,
                "weight": self.weight,
                **self.metadata,
            },
        }


class ZepFact(BaseModel):
    """A fact / event extracted by Zep, maps to EverMemOS EventLog."""

    uuid: str = Field(default_factory=lambda: uuid4().hex)
    fact: str
    rating: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    valid_at: datetime | None = None
    invalid_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_evermemos_payload(self, user_id: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "content": self.fact,
            "memory_type": EverMemType.event_log.value,
            "metadata": {
                "zep_uuid": self.uuid,
                "rating": self.rating,
                "valid_at": self.valid_at.isoformat() if self.valid_at else None,
                "invalid_at": self.invalid_at.isoformat() if self.invalid_at else None,
                **self.metadata,
            },
        }


class ZepSession(BaseModel):
    """A Zep session, maps to EverMemOS conversation metadata."""

    session_id: str
    user_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_evermemos_meta(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            **self.metadata,
        }

    @classmethod
    def from_evermemos(cls, data: dict[str, Any]) -> ZepSession:
        return cls(
            session_id=data.get("session_id", ""),
            user_id=data.get("user_id", ""),
            metadata={k: v for k, v in data.items() if k not in ("session_id", "user_id", "created_at")},
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
        )