"""Graph data models for entity-relationship knowledge graph."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class Entity(BaseModel):
    """A node in the knowledge graph."""

    id: str = Field(default_factory=_uuid)
    name: str
    entity_type: str
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    source_doc_id: str | None = None
    embedding_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Edge(BaseModel):
    """A directed relationship between two entities."""

    id: str = Field(default_factory=_uuid)
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    description: str = ""
    weight: float = 1.0
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class GraphFact(BaseModel):
    """A structured fact extracted from the graph (SPO triple or SP-value)."""

    id: str = Field(default_factory=_uuid)
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None = None
    object_value: str | None = None
    confidence: float = 1.0
    source: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class SubGraph(BaseModel):
    """A subset of the graph returned by queries."""

    entities: list[Entity] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


class GraphQuery(BaseModel):
    """Parameters for a graph search."""

    query: str
    entity_types: list[str] = Field(default_factory=list)
    max_depth: int = 2
    limit: int = 10
