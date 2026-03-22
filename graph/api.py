"""Knowledge Graph CRUD API endpoints (FastAPI router)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from miromem.graph.graph_store import GraphStore
from miromem.graph.graph_rag import GraphRAG
from miromem.graph.entity_extractor import EntityExtractor
from miromem.graph.models import Edge, Entity, GraphFact, GraphQuery, SubGraph

router = APIRouter(prefix="/api/v1/graph", tags=["knowledge-graph"])

_store: GraphStore | None = None
_rag: GraphRAG | None = None


def _get_store() -> GraphStore:
    global _store
    if _store is None:
        _store = GraphStore()
    return _store


def _get_rag() -> GraphRAG:
    global _rag
    if _rag is None:
        _rag = GraphRAG(store=_get_store())
    return _rag


# --- Lifecycle ---


@router.on_event("startup")
async def _startup() -> None:
    await _get_store().ensure_indexes()


# --- Entity endpoints ---


@router.post("/entities", response_model=Entity)
async def create_entity(entity: Entity) -> Entity:
    return await _get_store().add_entity(entity)


@router.get("/entities/{entity_id}", response_model=Entity)
async def get_entity(entity_id: str) -> Entity:
    ent = await _get_store().get_entity(entity_id)
    if not ent:
        raise HTTPException(404, "Entity not found")
    return ent


class EntityUpdate(BaseModel):
    name: str | None = None
    entity_type: str | None = None
    description: str | None = None
    attributes: dict | None = None


@router.put("/entities/{entity_id}", response_model=Entity)
async def update_entity(entity_id: str, body: EntityUpdate) -> Entity:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    ent = await _get_store().update_entity(entity_id, **fields)
    if not ent:
        raise HTTPException(404, "Entity not found")
    return ent


@router.delete("/entities/{entity_id}")
async def delete_entity(entity_id: str) -> dict:
    ok = await _get_store().delete_entity(entity_id)
    if not ok:
        raise HTTPException(404, "Entity not found")
    return {"deleted": entity_id}


# --- Edge endpoints ---


@router.post("/edges", response_model=Edge)
async def create_edge(edge: Edge) -> Edge:
    return await _get_store().add_edge(edge)


@router.get("/edges/entity/{entity_id}", response_model=list[Edge])
async def get_edges(entity_id: str) -> list[Edge]:
    return await _get_store().get_edges_for_entity(entity_id)


@router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str) -> dict:
    ok = await _get_store().delete_edge(edge_id)
    if not ok:
        raise HTTPException(404, "Edge not found")
    return {"deleted": edge_id}


# --- Fact endpoints ---


@router.post("/facts", response_model=GraphFact)
async def create_fact(fact: GraphFact) -> GraphFact:
    return await _get_store().add_fact(fact)


@router.get("/facts/entity/{entity_id}", response_model=list[GraphFact])
async def get_facts(entity_id: str) -> list[GraphFact]:
    return await _get_store().get_facts_for_entity(entity_id)


# --- Graph traversal endpoints ---


@router.get("/neighbors/{entity_id}", response_model=SubGraph)
async def get_neighbors(entity_id: str, depth: int = 1) -> SubGraph:
    return await _get_store().get_neighbors(entity_id, depth=depth)


@router.get("/path/{source_id}/{target_id}")
async def find_path(source_id: str, target_id: str, max_depth: int = 3) -> dict:
    path = await _get_store().find_path(source_id, target_id, max_depth=max_depth)
    if path is None:
        raise HTTPException(404, "No path found")
    return {"path": path}


@router.post("/subgraph", response_model=SubGraph)
async def get_subgraph(entity_ids: list[str], depth: int = 1) -> SubGraph:
    return await _get_store().get_subgraph(entity_ids, depth=depth)


# --- GraphRAG endpoints ---


@router.post("/search", response_model=SubGraph)
async def search(q: GraphQuery) -> SubGraph:
    return await _get_rag().search(q.query, top_k=q.limit)


@router.get("/context/{entity_name}")
async def entity_context(entity_name: str) -> dict:
    text = await _get_rag().get_entity_context(entity_name)
    return {"context": text}


class IngestRequest(BaseModel):
    texts: list[str]
    chunk_size: int = 512


@router.post("/ingest", response_model=SubGraph)
async def ingest_documents(body: IngestRequest) -> SubGraph:
    return await _get_rag().build_from_documents(body.texts, chunk_size=body.chunk_size)
