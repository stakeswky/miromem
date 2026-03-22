"""MongoDB-backed entity-relationship graph storage using motor."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from miromem.config.settings import load_config
from miromem.graph.models import Edge, Entity, GraphFact, SubGraph


class GraphStore:
    """Async graph storage backed by MongoDB collections."""

    def __init__(self, db: AsyncIOMotorDatabase | None = None) -> None:
        if db is not None:
            self._db = db
        else:
            cfg = load_config()
            client: AsyncIOMotorClient = AsyncIOMotorClient(cfg.infra.mongodb_uri)
            self._db = client[cfg.infra.mongodb_db]

        self.entities = self._db["graph_entities"]
        self.edges = self._db["graph_edges"]
        self.facts = self._db["graph_facts"]

    async def ensure_indexes(self) -> None:
        """Create indexes for efficient lookups."""
        await self.entities.create_index("id", unique=True)
        await self.entities.create_index("name")
        await self.entities.create_index("entity_type")
        await self.edges.create_index("id", unique=True)
        await self.edges.create_index("source_entity_id")
        await self.edges.create_index("target_entity_id")
        await self.facts.create_index("id", unique=True)
        await self.facts.create_index("subject_entity_id")

    # --- Entity CRUD ---

    async def add_entity(self, entity: Entity) -> Entity:
        await self.entities.insert_one(entity.model_dump())
        return entity

    async def get_entity(self, entity_id: str) -> Entity | None:
        doc = await self.entities.find_one({"id": entity_id})
        return Entity(**doc) if doc else None

    async def get_entity_by_name(self, name: str) -> Entity | None:
        doc = await self.entities.find_one({"name": name})
        return Entity(**doc) if doc else None

    async def update_entity(self, entity_id: str, **fields) -> Entity | None:
        fields["updated_at"] = datetime.now(timezone.utc)
        await self.entities.update_one({"id": entity_id}, {"$set": fields})
        return await self.get_entity(entity_id)

    async def delete_entity(self, entity_id: str) -> bool:
        r = await self.entities.delete_one({"id": entity_id})
        if r.deleted_count:
            # cascade: remove connected edges and facts
            await self.edges.delete_many(
                {"$or": [{"source_entity_id": entity_id}, {"target_entity_id": entity_id}]}
            )
            await self.facts.delete_many({"subject_entity_id": entity_id})
            return True
        return False

    async def add_entities_batch(self, entities: list[Entity]) -> list[Entity]:
        if entities:
            await self.entities.insert_many([e.model_dump() for e in entities])
        return entities

    # --- Edge CRUD ---

    async def add_edge(self, edge: Edge) -> Edge:
        await self.edges.insert_one(edge.model_dump())
        return edge

    async def get_edges_for_entity(self, entity_id: str) -> list[Edge]:
        cursor = self.edges.find(
            {"$or": [{"source_entity_id": entity_id}, {"target_entity_id": entity_id}]}
        )
        return [Edge(**doc) async for doc in cursor]

    async def delete_edge(self, edge_id: str) -> bool:
        r = await self.edges.delete_one({"id": edge_id})
        return r.deleted_count > 0

    async def add_edges_batch(self, edges: list[Edge]) -> list[Edge]:
        if edges:
            await self.edges.insert_many([e.model_dump() for e in edges])
        return edges

    # --- Fact CRUD ---

    async def add_fact(self, fact: GraphFact) -> GraphFact:
        await self.facts.insert_one(fact.model_dump())
        return fact

    async def get_facts_for_entity(self, entity_id: str) -> list[GraphFact]:
        cursor = self.facts.find({"subject_entity_id": entity_id})
        return [GraphFact(**doc) async for doc in cursor]

    # --- Graph Traversal ---

    async def get_neighbors(self, entity_id: str, depth: int = 1) -> SubGraph:
        """BFS traversal returning entities and edges within *depth* hops."""
        visited_ids: set[str] = set()
        collected_edges: list[Edge] = []
        queue: deque[tuple[str, int]] = deque([(entity_id, 0)])

        while queue:
            current_id, d = queue.popleft()
            if current_id in visited_ids:
                continue
            visited_ids.add(current_id)

            if d < depth:
                edges = await self.get_edges_for_entity(current_id)
                for edge in edges:
                    collected_edges.append(edge)
                    neighbor = (
                        edge.target_entity_id
                        if edge.source_entity_id == current_id
                        else edge.source_entity_id
                    )
                    if neighbor not in visited_ids:
                        queue.append((neighbor, d + 1))

        entities: list[Entity] = []
        for eid in visited_ids:
            ent = await self.get_entity(eid)
            if ent:
                entities.append(ent)

        return SubGraph(entities=entities, edges=collected_edges)

    async def find_path(
        self, source_id: str, target_id: str, max_depth: int = 3
    ) -> list[str] | None:
        """BFS shortest path between two entities. Returns entity id list or None."""
        visited: set[str] = set()
        queue: deque[tuple[str, list[str]]] = deque([(source_id, [source_id])])

        while queue:
            current, path = queue.popleft()
            if current == target_id:
                return path
            if len(path) > max_depth:
                continue
            if current in visited:
                continue
            visited.add(current)

            edges = await self.get_edges_for_entity(current)
            for edge in edges:
                neighbor = (
                    edge.target_entity_id
                    if edge.source_entity_id == current
                    else edge.source_entity_id
                )
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

        return None

    async def get_subgraph(self, entity_ids: list[str], depth: int = 1) -> SubGraph:
        """Return the union subgraph around multiple seed entities."""
        all_entities: dict[str, Entity] = {}
        all_edges: dict[str, Edge] = {}

        for eid in entity_ids:
            sg = await self.get_neighbors(eid, depth=depth)
            for ent in sg.entities:
                all_entities[ent.id] = ent
            for edge in sg.edges:
                all_edges[edge.id] = edge

        return SubGraph(
            entities=list(all_entities.values()),
            edges=list(all_edges.values()),
        )
