# Graphiti Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Zep Cloud graph backend with a self-hosted Graphiti + FalkorDB service while preserving the existing MiroFish simulation flow and Thinker compatibility boundary.

**Architecture:** The implementation adds a standalone internal `graph_service` package backed by Graphiti Core and FalkorDB, plus a thin MiroFish backend client that switches graph operations behind a `GRAPH_BACKEND` feature flag. MiroFish frontend and Thinker continue to interact with the existing simulation and graph lifecycle contracts; the backend swap remains internal and snapshot-first.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, Graphiti Core, FalkorDB, Redis, httpx, pytest, Docker Compose

---

## File Map

### New Python files

- `graph_service/__init__.py`: export the graph-service app package
- `graph_service/app.py`: FastAPI app for graph-service
- `graph_service/models.py`: request, response, job, metadata, and snapshot models
- `graph_service/api/__init__.py`: API package exports
- `graph_service/api/graphs.py`: graph build, append, snapshot, entities, and search routes
- `graph_service/api/jobs.py`: job status routes
- `graph_service/api/health.py`: dependency health and readiness routes
- `graph_service/core/__init__.py`: core package exports
- `graph_service/core/config.py`: graph-service env/config loading
- `graph_service/core/errors.py`: graph-service specific exceptions
- `graph_service/core/providers.py`: LLM, embedding, reranker, and Falkor provider factories
- `graph_service/core/graphiti_factory.py`: Graphiti instance bootstrap using FalkorDB and external providers
- `graph_service/domain/__init__.py`: domain package exports
- `graph_service/domain/schema_compiler.py`: ontology JSON -> Graphiti `entity_types`, `edge_types`, `edge_type_map`
- `graph_service/domain/episode_builder.py`: document chunks and simulation actions -> Graphiti episodes
- `graph_service/domain/snapshot_serializer.py`: Graphiti nodes/edges -> MiroFish frontend-compatible snapshot shape
- `graph_service/domain/query_service.py`: entity filtering, detail lookup, and fact search composition
- `graph_service/storage/__init__.py`: storage package exports
- `graph_service/storage/job_store.py`: job persistence and state transitions
- `graph_service/storage/snapshot_store.py`: snapshot persistence and stale metadata
- `graph_service/storage/graph_metadata_store.py`: graph build stats and metadata persistence
- `graph_service/workers/__init__.py`: worker package exports
- `graph_service/workers/build_worker.py`: build graph job execution
- `graph_service/workers/append_worker.py`: append-episodes job execution
- `graph_service/workers/snapshot_worker.py`: debounced snapshot refresh execution
- `graph_service/Dockerfile`: graph-service container image
- `tests/test_graph_service_config.py`: graph-service config and factory tests
- `tests/test_graph_service_jobs.py`: job state transition tests
- `tests/test_graphiti_schema_compiler.py`: ontology compilation tests
- `tests/test_graphiti_snapshot_serializer.py`: snapshot serialization contract tests
- `tests/test_graph_service_api.py`: FastAPI API tests for graph-service
- `tests/test_mirofish_graph_backend_client.py`: MiroFish-side client tests
- `tests/test_mirofish_graphiti_switch.py`: feature-flagged backend switch tests

### Modified Python files

- `pyproject.toml`: add Graphiti Falkor dependency and any missing runtime packages
- `docker-compose.yaml`: add FalkorDB and graph-service containers and wiring
- `.env.template`: add `GRAPH_*` and `FALKORDB_*` env vars
- `README.md`: document graph-service deployment, config, rollout, and rollback
- `vendor/MiroFish/backend/app/config.py`: add `GRAPH_BACKEND` and `GRAPH_SERVICE_BASE_URL`, remove hard requirement on `ZEP_API_KEY`
- `vendor/MiroFish/backend/app/services/graph_builder.py`: swap Zep graph build logic for graph-service client calls behind feature flag
- `vendor/MiroFish/backend/app/services/zep_entity_reader.py`: refactor into a graph backend reader backed by graph-service when `GRAPH_BACKEND=graphiti`
- `vendor/MiroFish/backend/app/services/oasis_profile_generator.py`: route graph enrichment search through graph-service when `GRAPH_BACKEND=graphiti`
- `vendor/MiroFish/backend/app/services/zep_graph_memory_updater.py`: replace direct Zep writes with graph-service append calls when `GRAPH_BACKEND=graphiti`

### Notes about deliberate non-overlap

- Do not modify `gateway/app.py` for Graphiti v1 unless a later operational need requires Gateway-level proxying.
- Do not add Graphiti-specific semantics to Thinker modules.
- Keep all Thinker configuration names under `THINKER_*`.
- Keep all Graphiti configuration names under `GRAPH_*` and `FALKORDB_*`.

## Execution Workspace

All implementation work should happen in a dedicated worktree under `.worktrees/`, not in the current dirty root checkout.

### Task 0: Create the Isolated Worktree

**Files:**
- Modify: none
- Test: none

- [ ] **Step 1: Create a dedicated worktree**

Run:

```bash
git worktree add .worktrees/graphiti-migration -b feat/graphiti-migration
```

Expected: Git creates `.worktrees/graphiti-migration` on a new branch.

- [ ] **Step 2: Install project dependencies inside the worktree**

Run:

```bash
cd .worktrees/graphiti-migration
python -m pip install -e ".[dev]"
npm --prefix vendor/MiroFish/frontend install
```

Expected: editable install succeeds and frontend dependencies install cleanly.

- [ ] **Step 3: Capture the backend baseline before changing code**

Run:

```bash
python -m pytest tests/test_gateway_polymarket_proxy.py tests/test_simulation_memory.py tests/test_mirofish_simulation_config_generator.py -v
```

Expected: PASS, confirming the worktree is healthy before the graph backend swap.

### Task 1: Add Graph-Service Config, Models, and Job Store

**Files:**
- Create: `graph_service/__init__.py`
- Create: `graph_service/models.py`
- Create: `graph_service/core/__init__.py`
- Create: `graph_service/core/config.py`
- Create: `graph_service/storage/__init__.py`
- Create: `graph_service/storage/job_store.py`
- Create: `tests/test_graph_service_config.py`
- Create: `tests/test_graph_service_jobs.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing config and job-store tests**

```python
from miromem.graph_service.core.config import GraphServiceSettings
from miromem.graph_service.storage.job_store import InMemoryGraphJobStore


def test_graph_service_settings_load_graphiti_fields(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    monkeypatch.setenv("GRAPH_SERVICE_PORT", "8010")
    monkeypatch.setenv("FALKORDB_HOST", "falkor")
    settings = GraphServiceSettings()
    assert settings.graph_backend == "graphiti"
    assert settings.graph_service_port == 8010
    assert settings.falkordb_host == "falkor"


def test_job_store_tracks_degraded_state():
    store = InMemoryGraphJobStore()
    job = store.create_job(job_type="build_graph", graph_id="mirofish_test")
    store.mark_degraded(job.job_id, reason="reranker_unavailable")
    current = store.get_job(job.job_id)
    assert current.status == "degraded"
    assert current.degraded_reason == "reranker_unavailable"
```

- [ ] **Step 2: Run the new tests to confirm the failure mode**

Run:

```bash
python -m pytest tests/test_graph_service_config.py tests/test_graph_service_jobs.py -v
```

Expected: FAIL because the graph-service package and settings do not exist yet.

- [ ] **Step 3: Add the minimal settings and job models**

```python
class GraphServiceSettings(BaseSettings):
    graph_backend: str = "graphiti"
    graph_service_port: int = 8001
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    graph_llm_api_key: str = ""
    graph_llm_base_url: str = ""
    graph_embedding_api_key: str = ""
```

```python
class GraphJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"
```

Implementation notes:

- Keep the job store in-memory for v1, but shape its interface so Redis-backed persistence can be added later without changing callers.
- Add `graphiti-core[falkordb]` to project dependencies in `pyproject.toml`.

- [ ] **Step 4: Run the tests until the settings and job-store cases pass**

Run:

```bash
python -m pytest tests/test_graph_service_config.py tests/test_graph_service_jobs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the completed foundation**

```bash
git add pyproject.toml graph_service/__init__.py graph_service/models.py graph_service/core/__init__.py graph_service/core/config.py graph_service/storage/__init__.py graph_service/storage/job_store.py tests/test_graph_service_config.py tests/test_graph_service_jobs.py
git commit -m "feat: add graph service config and job store"
```

### Task 2: Add Provider Factories and Graphiti Bootstrap

**Files:**
- Create: `graph_service/core/providers.py`
- Create: `graph_service/core/graphiti_factory.py`
- Modify: `tests/test_graph_service_config.py`

- [ ] **Step 1: Write the failing factory tests for FalkorDB, LLM, and embedder creation**

```python
from miromem.graph_service.core.providers import build_embedder, build_graph_driver, build_llm_client
from miromem.graph_service.core.config import GraphServiceSettings


def test_build_graph_driver_uses_falkor(monkeypatch):
    settings = GraphServiceSettings(
        falkordb_host="falkor",
        falkordb_port=6379,
        falkordb_database="mirofish_graphs",
    )
    driver = build_graph_driver(settings)
    assert driver.provider.value == "falkordb"


def test_build_embedder_uses_openai_compatible_settings():
    settings = GraphServiceSettings(
        graph_embedding_api_key="key",
        graph_embedding_base_url="https://embed.example.com/v1",
        graph_embedding_model="Qwen/Qwen3-Embedding-0.6B",
        graph_embedding_dim=1024,
    )
    embedder = build_embedder(settings)
    assert embedder.config.embedding_model == "Qwen/Qwen3-Embedding-0.6B"
```

- [ ] **Step 2: Run the factory tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_graph_service_config.py -v
```

Expected: FAIL because provider bootstrap helpers are not implemented.

- [ ] **Step 3: Implement Graphiti bootstrap helpers**

```python
def build_graph_driver(settings: GraphServiceSettings):
    return FalkorDriver(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
        username=settings.falkordb_username or None,
        password=settings.falkordb_password or None,
        database=settings.falkordb_database,
    )


def build_embedder(settings: GraphServiceSettings):
    return OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=settings.graph_embedding_api_key,
            base_url=settings.graph_embedding_base_url,
            embedding_model=settings.graph_embedding_model,
            embedding_dim=settings.graph_embedding_dim,
        )
    )
```

Implementation notes:

- Use OpenAI-compatible clients for LLM and embedding.
- Keep reranker optional. If it is unconfigured, return `None` and mark search-level degradation later instead of failing startup.

- [ ] **Step 4: Run the factory tests**

Run:

```bash
python -m pytest tests/test_graph_service_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the provider wiring**

```bash
git add graph_service/core/providers.py graph_service/core/graphiti_factory.py tests/test_graph_service_config.py
git commit -m "feat: add graphiti provider bootstrap"
```

### Task 3: Compile Ontology JSON into Graphiti Runtime Schema

**Files:**
- Create: `graph_service/domain/__init__.py`
- Create: `graph_service/domain/schema_compiler.py`
- Create: `tests/test_graphiti_schema_compiler.py`

- [ ] **Step 1: Write the failing ontology compiler tests**

```python
from miromem.graph_service.domain.schema_compiler import compile_ontology


def test_compile_ontology_returns_entity_and_edge_maps():
    ontology = {
        "entity_types": [
            {"name": "Politician", "attributes": [{"name": "party", "description": "party", "type": "text"}]}
        ],
        "edge_types": [
            {
                "name": "ENDORSES",
                "attributes": [{"name": "endorsement_type", "description": "type", "type": "text"}],
                "source_targets": [{"source": "Politician", "target": "Politician"}],
            }
        ],
    }
    compiled = compile_ontology(ontology)
    assert "Politician" in compiled.entity_types
    assert "ENDORSES" in compiled.edge_types
    assert compiled.edge_type_map[("Politician", "Politician")] == ["ENDORSES"]
```

- [ ] **Step 2: Run the schema tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_graphiti_schema_compiler.py -v
```

Expected: FAIL because the compiler module does not exist yet.

- [ ] **Step 3: Implement the compiler using dynamic Pydantic models**

```python
CompiledOntology = NamedTuple(
    "CompiledOntology",
    [("entity_types", dict[str, type[BaseModel]]), ("edge_types", dict[str, type[BaseModel]]), ("edge_type_map", dict[tuple[str, str], list[str]])],
)
```

Implementation notes:

- Reuse the current ontology JSON semantics from `vendor/MiroFish/backend/app/services/ontology_generator.py`.
- Preserve attribute descriptions in generated `Field(...)` definitions.
- Keep class names and edge names deterministic so snapshots remain stable between builds.

- [ ] **Step 4: Run the compiler tests**

Run:

```bash
python -m pytest tests/test_graphiti_schema_compiler.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the compiler**

```bash
git add graph_service/domain/__init__.py graph_service/domain/schema_compiler.py tests/test_graphiti_schema_compiler.py
git commit -m "feat: compile ontology for graphiti"
```

### Task 4: Add Episode Building, Build Worker, and Graph Build API

**Files:**
- Create: `graph_service/domain/episode_builder.py`
- Create: `graph_service/storage/graph_metadata_store.py`
- Create: `graph_service/workers/__init__.py`
- Create: `graph_service/workers/build_worker.py`
- Create: `graph_service/api/__init__.py`
- Create: `graph_service/api/graphs.py`
- Create: `graph_service/api/jobs.py`
- Create: `graph_service/api/health.py`
- Create: `graph_service/app.py`
- Create: `tests/test_graph_service_api.py`

- [ ] **Step 1: Write the failing build-job API tests**

```python
from fastapi.testclient import TestClient

from miromem.graph_service.app import app


def test_build_graph_returns_job_id():
    client = TestClient(app)
    response = client.post("/graphs/mirofish_demo/build", json={
        "project_id": "proj_demo",
        "graph_name": "Demo",
        "document_text": "Gavin Newsom is running.",
        "chunk_size": 500,
        "chunk_overlap": 50,
        "ontology": {"entity_types": [], "edge_types": []},
    })
    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_job_status_endpoint_returns_job_payload():
    client = TestClient(app)
    response = client.get("/jobs/missing")
    assert response.status_code == 404
```

- [ ] **Step 2: Run the API tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_graph_service_api.py -v
```

Expected: FAIL because the graph-service app and routes do not exist yet.

- [ ] **Step 3: Implement build request models, routes, and a minimal queued job path**

```python
@router.post("/graphs/{graph_id}/build", status_code=202)
async def build_graph(graph_id: str, body: GraphBuildRequest) -> GraphJobResponse:
    job = job_store.create_job(job_type="build_graph", graph_id=graph_id, metadata={"project_id": body.project_id})
    build_worker.enqueue(job.job_id, graph_id=graph_id, request=body)
    return GraphJobResponse(job_id=job.job_id, status=job.status)
```

Implementation notes:

- The first pass can use an in-process queue.
- Build worker must call the schema compiler and `Graphiti.add_episode_bulk`.
- Build metadata must record `chunk_count`, `node_count`, `edge_count`, and `last_built_at`.

- [ ] **Step 4: Run the API tests**

Run:

```bash
python -m pytest tests/test_graph_service_api.py -v
```

Expected: PASS for create-job and get-job behavior.

- [ ] **Step 5: Commit the initial graph-service API**

```bash
git add graph_service/domain/episode_builder.py graph_service/storage/graph_metadata_store.py graph_service/workers/__init__.py graph_service/workers/build_worker.py graph_service/api/__init__.py graph_service/api/graphs.py graph_service/api/jobs.py graph_service/api/health.py graph_service/app.py tests/test_graph_service_api.py
git commit -m "feat: add graph service build api"
```

### Task 5: Add Snapshot Serialization and Query Endpoints

**Files:**
- Create: `graph_service/domain/snapshot_serializer.py`
- Create: `graph_service/domain/query_service.py`
- Create: `graph_service/storage/snapshot_store.py`
- Create: `graph_service/workers/snapshot_worker.py`
- Create: `tests/test_graphiti_snapshot_serializer.py`
- Modify: `graph_service/api/graphs.py`
- Modify: `tests/test_graph_service_api.py`

- [ ] **Step 1: Write the failing snapshot serializer and query tests**

```python
from miromem.graph_service.domain.snapshot_serializer import serialize_snapshot


def test_serialize_snapshot_matches_mirofish_contract():
    payload = serialize_snapshot(nodes=[], edges=[], graph_id="mirofish_demo", stale=False)
    assert payload["graph_id"] == "mirofish_demo"
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["stale"] is False
```

```python
def test_snapshot_endpoint_returns_frontend_shape(client):
    response = client.get("/graphs/mirofish_demo/snapshot")
    assert response.status_code == 200
    assert "nodes" in response.json()
    assert "edges" in response.json()
```

- [ ] **Step 2: Run the serializer and API tests to confirm failure**

Run:

```bash
python -m pytest tests/test_graphiti_snapshot_serializer.py tests/test_graph_service_api.py -v
```

Expected: FAIL because snapshot storage and serializer logic do not exist.

- [ ] **Step 3: Implement snapshot-first graph reads**

```python
def serialize_snapshot(*, nodes: list[EntityNode], edges: list[EntityEdge], graph_id: str, stale: bool, last_refreshed_at: str | None = None) -> dict[str, Any]:
    return {
        "graph_id": graph_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "stale": stale,
        "last_refreshed_at": last_refreshed_at,
        "nodes": [...],
        "edges": [...],
    }
```

Implementation notes:

- `/graphs/{graph_id}/snapshot` should return the last successful snapshot even if a fresh rebuild failed.
- `/graphs/{graph_id}/entities`, `/entities/{entity_id}`, and `/search` should be built on top of query-service, not route-local logic.
- Query-service should use Graphiti entity and edge reads by `group_id`.

- [ ] **Step 4: Run the serializer and API tests**

Run:

```bash
python -m pytest tests/test_graphiti_snapshot_serializer.py tests/test_graph_service_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the read-path implementation**

```bash
git add graph_service/domain/snapshot_serializer.py graph_service/domain/query_service.py graph_service/storage/snapshot_store.py graph_service/workers/snapshot_worker.py graph_service/api/graphs.py tests/test_graphiti_snapshot_serializer.py tests/test_graph_service_api.py
git commit -m "feat: add graph snapshot and query endpoints"
```

### Task 6: Add MiroFish Graph Backend Client and Switch Graph Build/Read Paths

**Files:**
- Create: `vendor/MiroFish/backend/app/services/graph_backend_client.py`
- Create: `tests/test_mirofish_graph_backend_client.py`
- Create: `tests/test_mirofish_graphiti_switch.py`
- Modify: `vendor/MiroFish/backend/app/config.py`
- Modify: `vendor/MiroFish/backend/app/services/graph_builder.py`
- Modify: `vendor/MiroFish/backend/app/services/zep_entity_reader.py`

- [ ] **Step 1: Write the failing client and feature-flag tests**

```python
from vendor.MiroFish.backend.app.services.graph_backend_client import GraphBackendClient


def test_graph_backend_client_builds_snapshot_url():
    client = GraphBackendClient("http://graph-service:8001")
    assert client._url("/graphs/demo/snapshot") == "http://graph-service:8001/graphs/demo/snapshot"
```

```python
def test_graph_builder_uses_graph_service_when_feature_flag_enabled(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    from vendor.MiroFish.backend.app.config import Config
    assert Config.GRAPH_BACKEND == "graphiti"
```

- [ ] **Step 2: Run the backend-switch tests to confirm they fail**

Run:

```bash
python -m pytest tests/test_mirofish_graph_backend_client.py tests/test_mirofish_graphiti_switch.py -v
```

Expected: FAIL because the client and feature flag do not exist.

- [ ] **Step 3: Implement graph backend config and client**

```python
GRAPH_BACKEND = os.environ.get("GRAPH_BACKEND", "zep")
GRAPH_SERVICE_BASE_URL = os.environ.get("GRAPH_SERVICE_BASE_URL", "http://graph-service:8001")
```

```python
class GraphBackendClient:
    def build_graph(self, graph_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_snapshot(self, graph_id: str) -> dict[str, Any]: ...
    def get_entities(self, graph_id: str, params: dict[str, Any]) -> dict[str, Any]: ...
    def get_entity_detail(self, graph_id: str, entity_id: str) -> dict[str, Any]: ...
    def search(self, graph_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def append_episodes(self, graph_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
```

Implementation notes:

- Keep `GRAPH_BACKEND=zep` as the default until rollout is complete.
- `graph_builder.py` should only switch implementation internally; API response shape must remain compatible with the frontend.
- `zep_entity_reader.py` can keep its file name in v1 to minimize import churn, but its implementation should dispatch by backend.

- [ ] **Step 4: Run the client and switch tests**

Run:

```bash
python -m pytest tests/test_mirofish_graph_backend_client.py tests/test_mirofish_graphiti_switch.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the backend switch foundation**

```bash
git add vendor/MiroFish/backend/app/config.py vendor/MiroFish/backend/app/services/graph_backend_client.py vendor/MiroFish/backend/app/services/graph_builder.py vendor/MiroFish/backend/app/services/zep_entity_reader.py tests/test_mirofish_graph_backend_client.py tests/test_mirofish_graphiti_switch.py
git commit -m "feat: add graph backend client and feature flag"
```

### Task 7: Switch Profile Search and Dynamic Graph Append Paths

**Files:**
- Modify: `vendor/MiroFish/backend/app/services/oasis_profile_generator.py`
- Modify: `vendor/MiroFish/backend/app/services/zep_graph_memory_updater.py`
- Modify: `tests/test_mirofish_graphiti_switch.py`

- [ ] **Step 1: Write the failing tests for profile search and append-episode degradation**

```python
def test_profile_generator_uses_graph_service_search_when_graphiti_enabled(monkeypatch):
    monkeypatch.setenv("GRAPH_BACKEND", "graphiti")
    # patch GraphBackendClient.search and assert it is used
```

```python
def test_graph_memory_updater_degrades_without_stopping_simulation(monkeypatch):
    # patch append_episodes to raise once, assert the updater records failure
    # and keeps the caller-facing flow non-fatal
    ...
```

- [ ] **Step 2: Run the switch tests to confirm failure**

Run:

```bash
python -m pytest tests/test_mirofish_graphiti_switch.py -v
```

Expected: FAIL because enrichment search and dynamic append still call Zep directly.

- [ ] **Step 3: Route enrichment search through graph-service**

Implementation notes:

- When `GRAPH_BACKEND=graphiti`, `_search_zep_for_entity()` in `oasis_profile_generator.py` should call `GraphBackendClient.search(...)`.
- Preserve the existing result shape:
  - `facts`
  - `node_summaries`
  - `context`

- [ ] **Step 4: Route simulation graph updates through append jobs**

Implementation notes:

- `zep_graph_memory_updater.py` should batch actions and submit them to `append_episodes`.
- If graph append fails, the updater should log degradation and continue simulation instead of raising a fatal error.
- Do not stop the simulation process because the graph path degraded.

- [ ] **Step 5: Run the switch tests**

Run:

```bash
python -m pytest tests/test_mirofish_graphiti_switch.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the simulation-path switch**

```bash
git add vendor/MiroFish/backend/app/services/oasis_profile_generator.py vendor/MiroFish/backend/app/services/zep_graph_memory_updater.py tests/test_mirofish_graphiti_switch.py
git commit -m "feat: switch profile search and graph append to graph service"
```

### Task 8: Add Docker Compose Wiring, Docs, and Rollout Verification

**Files:**
- Create: `graph_service/Dockerfile`
- Modify: `docker-compose.yaml`
- Modify: `.env.template`
- Modify: `README.md`
- Modify: `tests/test_graph_service_api.py`
- Modify: `tests/test_mirofish_graphiti_switch.py`

- [ ] **Step 1: Add failing operational tests and config expectations**

```python
def test_env_template_mentions_graph_backend_contract():
    text = Path(".env.template").read_text()
    assert "GRAPH_BACKEND" in text
    assert "GRAPH_SERVICE_BASE_URL" in text
    assert "FALKORDB_HOST" in text
```

- [ ] **Step 2: Run the doc/config tests to confirm they fail**

Run:

```bash
python -m pytest tests/test_graph_service_api.py tests/test_mirofish_graphiti_switch.py -v
```

Expected: FAIL because deployment wiring and docs are incomplete.

- [ ] **Step 3: Add graph-service and FalkorDB to Compose**

Implementation notes:

- Add a `falkordb` service to `docker-compose.yaml`.
- Add a `graph-service` service that depends on `falkordb`.
- Set `GRAPH_SERVICE_BASE_URL` on `mirofish`.
- Keep the existing gateway and Thinker paths untouched.

- [ ] **Step 4: Document rollout, rollback, and Thinker compatibility**

Implementation notes:

- `.env.template` must add `GRAPH_*` and `FALKORDB_*` variables only.
- `README.md` must document:
  - graph-service startup
  - feature-flag rollout using `GRAPH_BACKEND=graphiti`
  - rollback using `GRAPH_BACKEND=zep`
  - explicit note that Thinker remains upstream and unchanged

- [ ] **Step 5: Run the final targeted test suite**

Run:

```bash
python -m pytest tests/test_graph_service_config.py tests/test_graph_service_jobs.py tests/test_graphiti_schema_compiler.py tests/test_graphiti_snapshot_serializer.py tests/test_graph_service_api.py tests/test_mirofish_graph_backend_client.py tests/test_mirofish_graphiti_switch.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the deployment and docs slice**

```bash
git add graph_service/Dockerfile docker-compose.yaml .env.template README.md tests/test_graph_service_api.py tests/test_mirofish_graphiti_switch.py
git commit -m "feat: wire graphiti graph service into deployment"
```

### Task 9: Verify End-to-End Rollout in the Worktree Environment

**Files:**
- Modify: none
- Test: manual verification using the running stack

- [ ] **Step 1: Start the full stack with Graphiti enabled**

Run:

```bash
docker compose up -d --build
```

Expected: `falkordb`, `graph-service`, `mirofish`, `gateway`, and supporting services are healthy.

- [ ] **Step 2: Build a graph through the existing frontend/backend path**

Run:

```bash
python scripts/demo.py
```

Expected: the graph build path completes without any `zep_cloud` dependency requirement when `GRAPH_BACKEND=graphiti`.

- [ ] **Step 3: Verify Thinker-facing assumptions remain intact**

Run:

```bash
python -m pytest tests/test_gateway_polymarket_proxy.py tests/test_simulation_memory.py -v
```

Expected: PASS, confirming the Graphiti migration did not regress the upstream simulation entry path Thinker depends on.

- [ ] **Step 4: Verify MiroFish simulation can still prepare and start**

Run:

```bash
python -m pytest tests/test_mirofish_simulation_config_generator.py -v
```

Expected: PASS, confirming graph-backed configuration generation still works.

- [ ] **Step 5: Commit the verified rollout state**

```bash
git add -A
git commit -m "test: verify graphiti migration rollout"
```

## Review Notes

The plan assumes:

- Graphiti remains an internal implementation detail
- Thinker remains upstream and unchanged
- public simulation flow semantics remain stable
- reranker support is optional in v1
- snapshot-first serving is required to avoid repeating the Zep polling/limit pattern

If implementation reveals that a separate queue service is truly necessary, that should be handled as a follow-up plan rather than expanding this one midstream.
