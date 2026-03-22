"""Evolution API endpoints (FastAPI router)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from miromem.evolution.agent_evolution import AgentEvolution
from miromem.evolution.foresight_validator import ForesightValidator
from miromem.evolution.sim_memory_store import SimMemoryStore

router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])

_store: SimMemoryStore | None = None
_evolution: AgentEvolution | None = None
_validator: ForesightValidator | None = None


def _get_store() -> SimMemoryStore:
    global _store
    if _store is None:
        _store = SimMemoryStore()
    return _store


def _get_evolution() -> AgentEvolution:
    global _evolution
    if _evolution is None:
        _evolution = AgentEvolution(store=_get_store())
    return _evolution


def _get_validator() -> ForesightValidator:
    global _validator
    if _validator is None:
        _validator = ForesightValidator()
    return _validator


@router.on_event("startup")
async def _startup() -> None:
    await _get_store().ensure_indexes()
    await _get_validator().ensure_indexes()


# --- Request models ---


class InjectRequest(BaseModel):
    agent_id: str
    agent_identity: str
    sim_context: str
    top_k: int = 10


class MarkMemoriesRequest(BaseModel):
    sim_id: str
    memory_ids: list[str]
    importance_scores: dict[str, float] = Field(default_factory=dict)
    agent_id: str = ""
    topic_tags: list[str] = Field(default_factory=list)


# --- Endpoints ---


@router.post("/inject")
async def inject_memories(body: InjectRequest) -> dict[str, Any]:
    """Inject historical memories for a new simulation."""
    context = await _get_evolution().inject_historical_memory(
        agent_id=body.agent_id,
        agent_identity=body.agent_identity,
        sim_context=body.sim_context,
        top_k=body.top_k,
    )
    return {"context": context}


@router.post("/mark")
async def mark_memories(body: MarkMemoriesRequest) -> dict[str, int]:
    """Mark memories as cross-simulation available after a sim ends."""
    count = await _get_store().mark_cross_sim_available(
        sim_id=body.sim_id,
        memory_ids=body.memory_ids,
        importance_scores=body.importance_scores,
        agent_id=body.agent_id,
        topic_tags=body.topic_tags,
    )
    return {"marked": count}


@router.get("/history/{agent_identity}")
async def evolution_history(agent_identity: str) -> dict[str, Any]:
    """Get evolution history for an agent across simulations."""
    return await _get_evolution().get_evolution_summary(agent_identity)


@router.post("/validate/{sim_id}")
async def validate_foresight(sim_id: str) -> dict[str, Any]:
    """Validate foresight predictions for a completed simulation."""
    return await _get_validator().validate_predictions(sim_id)


@router.get("/predictions")
async def prediction_history(
    agent_id: str | None = None,
    topic: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query prediction accuracy history with optional filters."""
    return await _get_validator().get_prediction_history(
        agent_id=agent_id, topic=topic, limit=limit,
    )


@router.get("/simulations")
async def list_simulations(limit: int = 50) -> list[dict[str, Any]]:
    """List past simulations."""
    return await _get_store().list_simulations(limit=limit)


@router.get("/simulations/{sim_id}")
async def simulation_summary(sim_id: str) -> dict[str, Any]:
    """Get summary of a specific simulation."""
    result = await _get_store().get_simulation_summary(sim_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result
