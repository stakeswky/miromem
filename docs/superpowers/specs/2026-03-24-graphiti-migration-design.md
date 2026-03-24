# Graphiti Migration Design

Date: 2026-03-24
Status: Drafted and approved in interactive design review

## Goal

Replace the current Zep Cloud-backed graph integration with a self-hosted, open-source Graphiti service backed by FalkorDB, while keeping the existing MiroFish simulation flow and frontend contracts stable.

The migration should eliminate Zep quota pressure, preserve the existing `graph/build -> simulation/create -> prepare -> start` user flow, and create a clean backend boundary that can support future graph backends without exposing Graphiti internals to MiroFish or the frontend.

## Primary Decision

Implement Graphiti as an internal, standalone `graph-service` that MiroFish backend calls over internal APIs.

### Why this architecture

- It creates a durable service boundary between simulation orchestration and graph infrastructure.
- It avoids coupling MiroFish backend directly to Graphiti internals.
- It allows FalkorDB, Graphiti configuration, provider selection, and future backend swaps to evolve independently.
- It keeps existing frontend and simulation API contracts stable.

## Product and Technical Constraints

The design is based on the following confirmed constraints:

- Thinker orchestration is already being implemented and must remain compatible.
- Thinker stays outside the simulation loop and only enriches inputs before the normal simulation entry path.
- Graphiti is an internal graph backend replacement, not a new frontend-facing product.
- LLM and embedding can depend on external API providers.
- FalkorDB is the preferred graph database backend.
- Reranker support is optional in v1.
- Existing MiroFish flow semantics should remain stable for:
  - graph build
  - simulation create
  - simulation prepare
  - simulation start

## Thinker Compatibility

Graphiti migration must explicitly preserve compatibility with the existing Thinker design.

### Compatibility rules

- Thinker remains upstream of graph build and simulation preparation.
- Thinker materializes improved seed text, topics, and simulation prompt only.
- Thinker must not need to know about Graphiti, FalkorDB, graph snapshots, or graph backend implementation details.
- Graphiti migration must not change the external meaning of the existing flow that Thinker feeds:
  - `graph/build`
  - `simulation/create`
  - `simulation/prepare`
  - `simulation/start`
- Graphiti migration must not require Thinker-specific branches inside graph ingestion or graph query logic.

### Shared file overlap to manage carefully

Both efforts may touch:

- `config/settings.py`
- `gateway/app.py`
- `README.md`
- `.env.template`

To avoid drift:

- Thinker-specific configuration must continue to use `THINKER_*`
- Graphiti-specific configuration must use `GRAPH_*`
- Gateway changes should be additive and router-local
- Graphiti should not require frontend routing assumptions that bypass Gateway if Thinker depends on Gateway-first integration

## Scope

### In scope

- Add a new internal `graph-service`
- Use Graphiti Core as the graph engine
- Use FalkorDB as the graph storage backend
- Use external LLM APIs for Graphiti extraction
- Use external embedding APIs for Graphiti embeddings
- Optionally support reranker APIs
- Replace MiroFish backend's direct `zep_cloud` usage with an internal graph-service client
- Preserve current frontend graph and simulation API shapes where practical
- Add graph snapshot generation for stable frontend rendering
- Add feature-flagged migration path and rollback support

### Out of scope for v1

- Rewriting the MiroFish frontend graph visualization
- Replacing Thinker orchestration
- Making Graphiti a public internet-facing API
- Multi-tenant user management beyond the existing project/simulation model
- Fully removing Zep on day one without a controlled feature-flagged migration

## Architecture

### High-level layout

- `mirofish-backend`
  - continues to own project lifecycle, simulation lifecycle, and frontend-facing APIs
  - stops calling `zep_cloud` directly
  - calls `graph-service` for graph build, graph reads, search, and append operations

- `graph-service`
  - owns Graphiti orchestration
  - owns FalkorDB connectivity
  - owns provider integration for LLM, embedding, and optional reranker
  - owns graph snapshots, graph metadata, and graph-related jobs

- `FalkorDB`
  - stores graph entities, edges, episodes, and related Graphiti graph structures

- external providers
  - main LLM provider for entity/relationship extraction
  - embedding provider for vector generation
  - optional reranker provider for improved retrieval ranking

### Why an internal graph-service instead of direct Graphiti embedding in MiroFish

Embedding Graphiti directly in MiroFish backend would reduce initial components, but it would tightly couple graph engine lifecycle, provider configuration, and storage concerns to simulation backend logic. The service boundary is the better long-term fit because the user explicitly values future-proofing and because Thinker is already introducing another Gateway-native subsystem that should not inherit graph engine concerns.

## Service Boundaries

### MiroFish backend responsibilities

- Create graph build requests
- Poll graph job status
- Read frontend-ready graph snapshots
- Read filtered entities and entity detail
- Perform graph search for profile enrichment
- Append simulation actions as graph episodes
- Keep project and simulation metadata in the current business objects

### Graph-service responsibilities

- Compile ontology JSON into Graphiti runtime schema objects
- Convert documents and actions into Graphiti episodes
- Execute Graphiti ingestion and search
- Generate and store frontend-ready graph snapshots
- Maintain graph metadata and async job state
- Apply retry, timeout, degradation, and fallback policy for external providers

## Internal Module Layout

Recommended new service structure:

- `graph_service/api/`
  - `graphs.py`
  - `jobs.py`
  - `health.py`
- `graph_service/core/`
  - `config.py`
  - `providers.py`
  - `graphiti_factory.py`
  - `errors.py`
- `graph_service/domain/`
  - `schema_compiler.py`
  - `episode_builder.py`
  - `snapshot_serializer.py`
  - `query_service.py`
- `graph_service/storage/`
  - `job_store.py`
  - `snapshot_store.py`
  - `graph_metadata_store.py`
- `graph_service/workers/`
  - `build_worker.py`
  - `append_worker.py`
  - `snapshot_worker.py`

## Data Model Mapping

The migration preserves existing MiroFish business identifiers while changing graph backend semantics internally.

### Identifier mapping

- `project_id`
  - remains a MiroFish business identifier
  - does not become a Graphiti object id

- `graph_id`
  - remains the graph identifier exposed to MiroFish and the frontend
  - internally maps to Graphiti `group_id`
  - should retain a stable MiroFish-style format, such as `mirofish_<hex>`

- `simulation_id`
  - remains a simulation lifecycle identifier
  - is not reused as the graph partition id
  - may be attached to appended episodes as metadata or source description

- `entity_uuid`
  - comes from Graphiti/FalkorDB-backed entities
  - continues to be returned to MiroFish as `uuid`

### Frontend graph snapshot shape

The frontend should continue receiving a stable shape close to the current API:

- `nodes[]`
  - `uuid`
  - `name`
  - `labels`
  - `summary`
  - `attributes`
  - `created_at`

- `edges[]`
  - `uuid`
  - `name`
  - `fact`
  - `fact_type`
  - `source_node_uuid`
  - `target_node_uuid`
  - `source_node_name`
  - `target_node_name`
  - `attributes`
  - `created_at`
  - `valid_at`
  - `invalid_at`
  - `expired_at`
  - `episodes`

This requires a dedicated snapshot serializer instead of leaking Graphiti's raw models upward.

## Ontology Strategy

Current MiroFish ontology generation already emits enough structure to drive Graphiti:

- `entity_types[].name`
- `entity_types[].attributes[]`
- `edge_types[].name`
- `edge_types[].attributes[]`
- `edge_types[].source_targets[]`

### Runtime compilation approach

The new `schema_compiler` module should convert current ontology JSON into:

- `entity_types: dict[str, type[BaseModel]]`
- `edge_types: dict[str, type[BaseModel]]`
- `edge_type_map: dict[tuple[str, str], list[str]]`

### Important semantic difference from Zep

Current Zep flow:

1. create graph
2. set ontology on graph
3. ingest data

Graphiti flow:

1. create graph id/group id
2. compile ontology into runtime schema objects
3. pass schema objects during `add_episode` or `add_episode_bulk`

This means ontology is a build-time and append-time input rather than a persisted remote graph setting.

## API Contract for Graph-Service

The graph-service should not simply expose Graphiti's stock server routes. It should expose routes aligned with MiroFish's needs.

### `POST /graphs`

Create a graph container and return `graph_id`.

Response:

```json
{
  "graph_id": "mirofish_xxx",
  "status": "created"
}
```

### `POST /graphs/{graph_id}/build`

Start graph build from document text and ontology.

Request:

```json
{
  "project_id": "proj_xxx",
  "graph_name": "Unnamed Project",
  "document_text": "...",
  "chunk_size": 500,
  "chunk_overlap": 50,
  "ontology": {
    "entity_types": [],
    "edge_types": []
  }
}
```

Response:

```json
{
  "job_id": "graph_job_xxx",
  "status": "queued"
}
```

### `POST /graphs/{graph_id}/episodes`

Append simulation or other event episodes to an existing graph.

Request:

```json
{
  "simulation_id": "sim_xxx",
  "episodes": [
    {
      "name": "Twitter action batch",
      "content": "Agent A: reposted Agent B's post",
      "reference_time": "2026-03-24T12:00:00Z",
      "source": "text",
      "source_description": "simulation:twitter"
    }
  ]
}
```

Response:

```json
{
  "job_id": "append_job_xxx",
  "status": "queued"
}
```

### `GET /graphs/{graph_id}`

Return graph metadata and build statistics.

### `GET /graphs/{graph_id}/snapshot`

Return frontend-ready `nodes/edges` snapshot.

Response should support:

- `stale: bool`
- `last_refreshed_at`
- `node_count`
- `edge_count`
- `nodes`
- `edges`

### `GET /graphs/{graph_id}/entities`

Return filtered entities, optionally by entity type.

### `GET /graphs/{graph_id}/entities/{entity_id}`

Return a single entity and its context.

### `POST /graphs/{graph_id}/search`

Return fact-oriented and related-node-oriented search results for profile generation and graph analysis.

### `GET /jobs/{job_id}`

Return job status and result metadata.

## Job and Worker Model

The graph-service should execute graph operations asynchronously.

### Job types

- `build_graph`
- `append_episodes`
- `refresh_snapshot`

### Job states

- `queued`
- `running`
- `completed`
- `failed`
- `degraded`

### Degraded semantics

`degraded` means the service remains healthy enough for the main flow to continue, but one or more quality-enhancing operations could not complete. Examples:

- reranker unavailable
- snapshot refresh failed but previous snapshot still available
- append retries still pending but main simulation should continue

## Ingestion Flow

### Build graph flow

1. MiroFish backend requests `POST /graphs/{graph_id}/build`
2. graph-service records a job and returns `job_id`
3. worker compiles ontology into runtime schema
4. worker chunks document text
5. worker converts chunks into Graphiti episodes
6. worker performs initial ingestion, preferably via `add_episode_bulk`
7. worker generates a graph snapshot
8. worker stores metadata:
  - `chunk_count`
  - `node_count`
  - `edge_count`
  - `last_built_at`

### Append episodes flow

1. MiroFish backend batches simulation actions and sends them to `POST /graphs/{graph_id}/episodes`
2. graph-service records a queued append job
3. worker consumes append jobs in graph order
4. worker appends episodes sequentially for the same graph
5. snapshot refresh is triggered through debounce rules

### Why append writes must be graph-serial

Graphiti's temporal fact and invalidation semantics depend on episode ordering. Concurrent, unordered writes to the same graph would reduce consistency and make graph state harder to reason about during simulation playback.

## Snapshot Strategy

Snapshots are a required abstraction, not an optimization.

### Why snapshots are required

- Frontend graph rendering needs stable, simple node/edge structures
- Frontend should not trigger deep Graphiti/Falkor traversal on every refresh
- Snapshots provide graceful degradation when providers or refresh workers fail
- Snapshot caching is the cleanest way to avoid repeating the Zep-era pattern of constant remote graph polling

### Snapshot behavior

- build completion generates a full snapshot
- append events trigger debounced snapshot refresh
- read endpoints prefer the last successful snapshot
- if refresh fails, continue serving the previous snapshot with `stale=true`

## Configuration Design

Graphiti-specific configuration should be isolated from Thinker and general simulation config.

### Graph database config

- `GRAPH_BACKEND=falkordb`
- `FALKORDB_HOST`
- `FALKORDB_PORT`
- `FALKORDB_USERNAME`
- `FALKORDB_PASSWORD`
- `FALKORDB_DATABASE`
- `GRAPH_DEFAULT_SNAPSHOT_TTL`
- `GRAPH_APPEND_BATCH_SIZE`
- `GRAPH_SNAPSHOT_DEBOUNCE_SECONDS`

### Graph LLM config

- `GRAPH_LLM_API_KEY`
- `GRAPH_LLM_BASE_URL`
- `GRAPH_LLM_MODEL`
- `GRAPH_LLM_SMALL_MODEL`
- `GRAPH_LLM_TEMPERATURE`
- `GRAPH_LLM_MAX_TOKENS`

### Graph embedding config

- `GRAPH_EMBEDDING_API_KEY`
- `GRAPH_EMBEDDING_BASE_URL`
- `GRAPH_EMBEDDING_MODEL`
- `GRAPH_EMBEDDING_DIM`

### Graph reranker config

- `GRAPH_RERANKER_PROVIDER=openai_compat|custom|disabled`
- `GRAPH_RERANKER_API_KEY`
- `GRAPH_RERANKER_BASE_URL`
- `GRAPH_RERANKER_MODEL`
- `GRAPH_RERANKER_TIMEOUT_SECONDS`

### Ownership rule

- `mirofish-backend` should only know `GRAPH_SERVICE_BASE_URL`
- `graph-service` owns all `GRAPH_*` and `FALKORDB_*` configuration
- Thinker continues to own `THINKER_*`

## Provider Integration

The graph-service should use provider factories to keep Graphiti wiring isolated.

### Required factories

- `LLMFactory`
  - produces the Graphiti-compatible extraction LLM client
- `EmbeddingFactory`
  - produces the embedding client
- `RerankerFactory`
  - optional in v1
  - supports:
    - `openai_compat`
    - `custom`
    - `disabled`

### Provider policy

- LLM and embedding are hard dependencies
- reranker is optional in v1
- if reranker is unavailable, search degrades without blocking graph reads or simulation

## MiroFish Backend Migration Surface

These backend integration points should switch from Zep calls to the graph-service client:

- `vendor/MiroFish/backend/app/services/graph_builder.py`
- `vendor/MiroFish/backend/app/services/zep_entity_reader.py`
- `vendor/MiroFish/backend/app/services/oasis_profile_generator.py`
- `vendor/MiroFish/backend/app/services/zep_graph_memory_updater.py`
- `vendor/MiroFish/backend/app/config.py`

### Required compatibility rule

The MiroFish frontend should not need to know whether the graph backend is Zep or Graphiti.

## Feature Flag and Rollback Strategy

Migration must be feature-flagged.

### Recommended backend flag

- `GRAPH_BACKEND=zep|graphiti`

### Migration order

1. Run graph-service independently with FalkorDB and external providers
2. Switch Step 1 graph build to graph-service
3. Switch graph snapshot reads to graph-service
4. Switch Step 2 entity filtering and graph search to graph-service
5. Switch Step 3 dynamic append writes to graph-service
6. Remove `zep_cloud` dependency only after Graphiti path is stable

### Rollback behavior

- if Graphiti path fails in production, switch `GRAPH_BACKEND=zep`
- frontend remains unchanged
- Thinker remains unchanged
- MiroFish backend resumes calling legacy graph backend client

## Testing Strategy

### Unit tests

- ontology compilation
- episode construction
- snapshot serialization
- provider factory configuration
- degradation and fallback policies

### Integration tests

- graph-service with FalkorDB and mocked external providers
- build graph job end-to-end
- append episodes flow
- entities and detail queries
- search behavior with and without reranker

### End-to-end tests

- upload -> graph build -> prepare -> start through MiroFish using `GRAPH_BACKEND=graphiti`
- Thinker-assisted flow should still materialize into the unchanged simulation entry path

### Degradation tests

- LLM timeout during build
- embedding failure during append
- reranker unavailable during search
- snapshot refresh failure with successful stale snapshot fallback

## Observability

The graph-service should expose health, structured logs, and metrics.

### Health checks

- `graph_db`
- `llm`
- `embedding`
- `reranker`
- `queue`

### Metrics

- `build_graph_duration`
- `append_episode_duration`
- `snapshot_refresh_duration`
- `job_queue_depth`
- `snapshot_age_seconds`
- `provider_error_count`
- `provider_rate_limit_count`

### Log fields

- `graph_id`
- `project_id`
- `simulation_id`
- `job_id`
- `provider`
- `degraded_reason`

## Risks

- External provider latency may still make graph build slower than the current optimistic path
- Graphiti extraction quality depends on external model quality and structured output reliability
- Snapshot logic adds another consistency surface that must be tested carefully
- Shared configuration files with Thinker can drift if prefixes and ownership are not enforced
- Dual-backend migration period increases maintenance complexity temporarily

## Non-goals

- Rewriting Thinker around Graphiti
- Exposing Graphiti internals directly to the frontend
- Publicly exposing FalkorDB or Graphiti endpoints to users
- Removing MiroFish's project/simulation business objects
- Replacing simulation logic itself

## Recommendation

Build a standalone internal `graph-service` around Graphiti Core and FalkorDB, keep LLM and embedding provider integration external, preserve the current MiroFish public flow semantics, and enforce a clear compatibility boundary with Thinker. Use a feature-flagged backend swap and snapshot-first frontend serving to migrate safely away from Zep Cloud without coupling future graph infrastructure changes to the simulation product surface.
