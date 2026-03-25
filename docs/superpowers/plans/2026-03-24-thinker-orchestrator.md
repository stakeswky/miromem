# Thinker Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Gateway-native Thinker orchestration layer that enriches user research directions for upload and Polymarket flows, then feeds normalized results back into the existing MiroFish simulation entry path.

**Architecture:** The implementation keeps Thinker outside the simulation loop. MiroMem adds native FastAPI endpoints, an in-process job registry, provider-backed orchestration, backend-side file extraction, and a materialization step. MiroFish frontend calls those Gateway endpoints, lets the user edit/adopt/retry/skip the suggestions, then continues through the existing pending-upload and Process flow. `topic_only` is API-only in v1; the MiroFish UI integration covers upload and Polymarket.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, asyncio, httpx/OpenAI SDK, pytest, Vue 3, Vite, Axios

---

## File Map

### New Python files

- `thinker/__init__.py`: export Thinker router and public helpers
- `thinker/models.py`: Pydantic request/response and job/result schemas
- `thinker/jobs.py`: in-memory job registry, state transitions, retry/skip handling
- `thinker/materializer.py`: normalize job results into MiroFish-consumable payloads
- `thinker/orchestrator.py`: mode-specific research execution for `topic_only`, `upload`, and `polymarket`
- `thinker/file_ingest.py`: extract text from uploaded PDF/MD/TXT files inside Gateway
- `thinker/providers/__init__.py`: provider exports
- `thinker/providers/llm_provider.py`: main LLM provider interface and external API-backed implementation
- `thinker/providers/search_provider.py`: search provider interface and Serper-style implementation
- `thinker/providers/scrape_provider.py`: scrape/summary provider interface and Jina-style implementation
- `thinker/providers/polymarket_provider.py`: normalize Polymarket event payloads for orchestration

### Modified Python files

- `config/settings.py`: add Thinker configuration and provider-related env loading
- `gateway/app.py`: register Thinker router
- `README.md`: document Thinker workflow and env vars
- `.env.template`: document Thinker env vars
- `pyproject.toml`: add Gateway-side upload parsing dependencies

### New test files

- `tests/test_thinker_jobs.py`: job registry, states, retry/skip rules
- `tests/test_thinker_orchestrator.py`: provider-backed orchestration by mode
- `tests/test_gateway_thinker_api.py`: FastAPI endpoint behavior with mocked orchestrator

### New frontend files

- `vendor/MiroFish/frontend/src/api/thinker.js`: Axios wrapper for Thinker endpoints
- `vendor/MiroFish/frontend/src/utils/thinker.js`: job polling helpers and synthetic seed file builders

### Modified frontend files

- `vendor/MiroFish/frontend/src/api/index.js`: point all frontend API traffic at Gateway
- `vendor/MiroFish/frontend/vite.config.js`: proxy `/api` to Gateway during local dev
- `vendor/MiroFish/frontend/src/views/Home.vue`: Thinker toggle, job creation, polling, adopt/retry/skip flows
- `vendor/MiroFish/frontend/src/store/pendingUpload.js`: carry materialized Thinker output into `Process.vue`

## Execution Workspace

All implementation work should happen in a dedicated worktree under `.worktrees/`, not in the current dirty root checkout.

### Task 0: Create the Isolated Worktree

**Files:**
- Modify: none
- Test: none

- [ ] **Step 1: Create a dedicated worktree**

Run:

```bash
git worktree add .worktrees/thinker-orchestrator -b feat/thinker-orchestrator
```

Expected: Git creates `.worktrees/thinker-orchestrator` on a new branch.

- [ ] **Step 2: Install project dependencies inside the worktree**

Run:

```bash
cd .worktrees/thinker-orchestrator
python -m pip install -e ".[dev]"
npm --prefix vendor/MiroFish/frontend install
```

Expected: editable install succeeds with pytest dependencies available, and frontend dependencies are installed for later Vite builds.

- [ ] **Step 3: Capture the baseline before changing code**

Run:

```bash
python -m pytest tests/test_gateway_polymarket_proxy.py tests/test_simulation_memory.py -v
```

Expected: existing targeted tests pass, confirming the worktree is healthy.

### Task 1: Add Thinker Config, Schemas, and Job Registry

**Files:**
- Create: `thinker/__init__.py`
- Create: `thinker/models.py`
- Create: `thinker/jobs.py`
- Modify: `config/settings.py`
- Test: `tests/test_thinker_jobs.py`

- [ ] **Step 1: Write the failing job-registry and config tests**

```python
import pytest

from miromem.thinker.jobs import InMemoryThinkerJobStore
from miromem.config.settings import load_config


def test_job_store_creates_pending_job():
    store = InMemoryThinkerJobStore()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")
    assert job.status == "created"
    assert job.mode == "topic_only"


def test_failed_job_can_be_retried_but_succeeded_job_cannot():
    store = InMemoryThinkerJobStore()
    job = store.create_job(mode="topic_only", research_direction="Fed outlook")
    store.mark_failed(job.job_id, error_code="upstream_error", error_message="timeout")
    retried = store.retry_job(job.job_id)
    assert retried.status == "created"


def test_load_config_includes_thinker_settings(monkeypatch):
    monkeypatch.setenv("THINKER_LLM_BASE_URL", "https://api.example.com/v1")
    config = load_config()
    assert config.thinker.llm_base_url == "https://api.example.com/v1"
```

- [ ] **Step 2: Run the new tests to verify the failure mode**

Run:

```bash
python -m pytest tests/test_thinker_jobs.py -v
```

Expected: FAIL because the `miromem.thinker` package and Thinker config do not exist yet.

- [ ] **Step 3: Implement the minimal Thinker config and registry**

```python
@dataclass
class ThinkerConfig:
    llm_api_key: str = field(default_factory=lambda: os.getenv("THINKER_LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("THINKER_LLM_BASE_URL", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("THINKER_LLM_MODEL", ""))


class InMemoryThinkerJobStore:
    def create_job(self, *, mode: str, research_direction: str, **payload) -> ThinkerJob:
        ...
```

Implementation notes:

- Keep `ThinkerJob` as a focused Pydantic model in `thinker/models.py`
- Support `created`, `running`, `succeeded`, `failed`, `materialized`, and `skipped`
- Do not introduce Redis or Mongo persistence in v1

- [ ] **Step 4: Run tests until the new registry/config cases pass**

Run:

```bash
python -m pytest tests/test_thinker_jobs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the completed unit**

```bash
git add config/settings.py thinker/__init__.py thinker/models.py thinker/jobs.py tests/test_thinker_jobs.py
git commit -m "feat: add thinker job models and config"
```

### Task 2: Add the Gateway Thinker Router Skeleton

**Files:**
- Create: `thinker/api.py`
- Modify: `gateway/app.py`
- Test: `tests/test_gateway_thinker_api.py`

- [ ] **Step 1: Write the failing API tests for create, status, and materialize**

```python
from fastapi.testclient import TestClient

from miromem.gateway.app import app


def test_create_thinker_job_returns_job_id():
    client = TestClient(app)
    response = client.post("/api/v1/thinker/jobs", json={
        "mode": "topic_only",
        "research_direction": "Fed outlook",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "created"


def test_missing_job_returns_404():
    client = TestClient(app)
    response = client.get("/api/v1/thinker/jobs/missing")
    assert response.status_code == 404
```

- [ ] **Step 2: Run the API tests and confirm they fail**

Run:

```bash
python -m pytest tests/test_gateway_thinker_api.py -v
```

Expected: FAIL because the router is not registered and the endpoints do not exist.

- [ ] **Step 3: Implement the minimal router and include it in the Gateway**

```python
router = APIRouter(prefix="/api/v1/thinker", tags=["thinker"])


@router.post("/jobs")
async def create_job(body: ThinkerJobCreateRequest) -> ThinkerJobCreateResponse:
    job = _get_job_store().create_job(...)
    return ThinkerJobCreateResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> ThinkerJobStatusResponse:
    ...
```

Implementation notes:

- Materialize may return a placeholder payload in this task
- Use module-level dependency getters, matching the existing Graph/Evolution style
- Register the router in `gateway/app.py` with `app.include_router(thinker_router)`

- [ ] **Step 4: Re-run the API tests**

Run:

```bash
python -m pytest tests/test_gateway_thinker_api.py -v
```

Expected: PASS for the skeleton behavior.

- [ ] **Step 5: Commit the completed router skeleton**

```bash
git add thinker/api.py gateway/app.py tests/test_gateway_thinker_api.py
git commit -m "feat: add thinker gateway endpoints"
```

### Task 3: Add External Provider Abstractions and Topic-Only Orchestration

**Files:**
- Create: `thinker/providers/__init__.py`
- Create: `thinker/providers/llm_provider.py`
- Create: `thinker/providers/search_provider.py`
- Create: `thinker/providers/scrape_provider.py`
- Create: `thinker/providers/polymarket_provider.py`
- Create: `thinker/orchestrator.py`
- Modify: `thinker/api.py`
- Modify: `thinker/jobs.py`
- Test: `tests/test_thinker_orchestrator.py`
- Test: `tests/test_gateway_thinker_api.py`

- [ ] **Step 1: Write the failing topic-only orchestration test**

```python
import pytest

from miromem.thinker.orchestrator import ThinkerOrchestrator


@pytest.mark.asyncio
async def test_topic_only_job_produces_topics_seed_and_prompt():
    orchestrator = ThinkerOrchestrator(
        llm_provider=FakeLLMProvider(),
        search_provider=FakeSearchProvider(),
        scrape_provider=FakeScrapeProvider(),
        polymarket_provider=FakePolymarketProvider(),
    )
    result = await orchestrator.run(
        mode="topic_only",
        research_direction="Will the Fed keep tightening in Q3?",
    )
    assert result.expanded_topics
    assert result.enriched_seed_text
    assert result.suggested_simulation_prompt
```

- [ ] **Step 2: Run the orchestration test to verify it fails**

Run:

```bash
python -m pytest tests/test_thinker_orchestrator.py -v
```

Expected: FAIL because the orchestrator and provider interfaces do not exist yet.

- [ ] **Step 3: Implement provider protocols, concrete external API adapters, and topic-only orchestration**

```python
class LLMProvider(Protocol):
    async def generate_research_bundle(self, *, research_direction: str, evidence: list[str]) -> ThinkerResult:
        ...


class ThinkerOrchestrator:
    async def run(self, *, mode: str, research_direction: str, **payload) -> ThinkerResult:
        if mode == "topic_only":
            evidence = await self._collect_topic_evidence(research_direction)
            return await self.llm_provider.generate_research_bundle(
                research_direction=research_direction,
                evidence=evidence,
            )
        raise ValueError(f"Unsupported mode: {mode}")
```

Implementation notes:

- Keep provider methods narrow and async
- Implement real default providers in this task:
  - `llm_provider.py`: OpenAI-compatible chat/completions client using `THINKER_LLM_*`
  - `search_provider.py`: HTTP client using `THINKER_SEARCH_*`
  - `scrape_provider.py`: HTTP client using `THINKER_SCRAPE_*`
- Trigger background execution from the API layer with `asyncio.create_task`, then store the result in `InMemoryThinkerJobStore`
- If a required provider is misconfigured or unavailable, mark the job `failed` with structured fields:
  - `error_code`
  - `error_message`
  - `retryable`
  - `can_continue_without_thinker`

- [ ] **Step 4: Add and run a failed-job API test for the error shape**

Run:

```bash
python -m pytest tests/test_gateway_thinker_api.py -k failed -v
```

Expected: PASS with the exact failed-job response shape locked down.

- [ ] **Step 5: Re-run the orchestrator test**

Run:

```bash
python -m pytest tests/test_thinker_orchestrator.py -v
```

Expected: PASS for `topic_only`.

- [ ] **Step 6: Commit the topic-only orchestration unit**

```bash
git add thinker/providers thinker/orchestrator.py thinker/api.py thinker/jobs.py tests/test_thinker_orchestrator.py tests/test_gateway_thinker_api.py
git commit -m "feat: add thinker topic orchestration"
```

### Task 4: Add Gateway-Side File Ingestion and Extend Upload/Polymarket Modes

**Files:**
- Modify: `pyproject.toml`
- Create: `thinker/file_ingest.py`
- Modify: `thinker/orchestrator.py`
- Modify: `thinker/providers/polymarket_provider.py`
- Modify: `thinker/api.py`
- Modify: `thinker/models.py`
- Test: `tests/test_thinker_orchestrator.py`
- Test: `tests/test_gateway_thinker_api.py`

- [ ] **Step 1: Write the failing upload and polymarket tests**

```python
@pytest.mark.asyncio
async def test_upload_mode_prefers_uploaded_text_as_evidence():
    result = await orchestrator.run(
        mode="upload",
        research_direction="Fed outlook",
        seed_text="Uploaded memo text",
        uploaded_files=[{"name": "fed.pdf", "text": "Uploaded memo text"}],
    )
    assert "Uploaded memo text" in result.meta["evidence_preview"]


@pytest.mark.asyncio
async def test_polymarket_mode_normalizes_selected_event():
    result = await orchestrator.run(
        mode="polymarket",
        research_direction="Election pricing drift",
        polymarket_event={"title": "Will X win?", "description": "Market event"},
    )
    assert result.references
```

- [ ] **Step 2: Run the orchestrator tests and verify the new failures**

Run:

```bash
python -m pytest tests/test_thinker_orchestrator.py -v
```

Expected: FAIL for the new modes.

- [ ] **Step 3: Implement backend-side upload extraction and mode-specific normalization**

```python
if mode == "upload":
    extracted = await file_ingest.extract_uploads(files)
    evidence = self._collect_uploaded_evidence(seed_text=seed_text, uploaded_files=extracted)
elif mode == "polymarket":
    normalized = await self.polymarket_provider.normalize_event(polymarket_event)
    evidence = [normalized.summary]
```

Implementation notes:

- `POST /api/v1/thinker/jobs` must accept multipart form data for `mode=upload`
- File extraction belongs to Gateway/backend in v1, not the browser
- `thinker/file_ingest.py` should support the same upload types MiroFish already accepts: PDF, MD, TXT
- Add `python-multipart` and `PyMuPDF` to the root project dependencies in `pyproject.toml`
- Use simple text-file fallback handling in `thinker/file_ingest.py` for MD/TXT rather than introducing a second parsing stack
- `polymarket` must not fetch the event list again; it should normalize the already-selected event payload
- Keep `ThinkerResult.references` populated for both modes

- [ ] **Step 4: Reinstall the editable package after changing `pyproject.toml`**

Run:

```bash
python -m pip install -e ".[dev]"
```

Expected: the worktree environment picks up the new PDF parsing dependency before tests run.

- [ ] **Step 5: Add a multipart upload API test and run the affected test slice**

Run:

```bash
python -m pytest tests/test_gateway_thinker_api.py tests/test_thinker_orchestrator.py -v
```

Expected: PASS for upload multipart handling and all three orchestration modes.

- [ ] **Step 6: Commit the upload/polymarket mode work**

```bash
git add pyproject.toml thinker/file_ingest.py thinker/orchestrator.py thinker/providers/polymarket_provider.py thinker/api.py thinker/models.py tests/test_thinker_orchestrator.py tests/test_gateway_thinker_api.py
git commit -m "feat: support thinker upload and polymarket modes"
```

### Task 5: Implement Materialization and Explicit Retry/Skip Actions

**Files:**
- Create: `thinker/materializer.py`
- Modify: `thinker/api.py`
- Modify: `thinker/jobs.py`
- Modify: `thinker/models.py`
- Test: `tests/test_gateway_thinker_api.py`
- Test: `tests/test_thinker_jobs.py`

- [ ] **Step 1: Write the failing tests for materialize, retry, and skip**

```python
def test_materialize_allows_user_edits():
    client = TestClient(app)
    job_id = create_succeeded_job()
    response = client.post("/api/v1/thinker/materialize", json={
        "job_id": job_id,
        "adopted": {
            "expanded_topics": ["Fed", "inflation"],
            "enriched_seed_text": "edited seed",
            "suggested_simulation_prompt": "edited prompt",
        },
    })
    assert response.json()["payload"]["final_seed_text"] == "edited seed"


def test_retry_recreates_failed_job():
    ...


def test_skip_marks_job_as_skipped():
    ...
```

- [ ] **Step 2: Run the API and job tests to confirm failure**

Run:

```bash
python -m pytest tests/test_thinker_jobs.py tests/test_gateway_thinker_api.py -v
```

Expected: FAIL because materializer and explicit retry/skip actions are not implemented.

- [ ] **Step 3: Implement the materializer and action endpoints**

```python
class ThinkerMaterializer:
    def materialize(self, *, result: ThinkerResult, adopted: ThinkerAdoptedInput) -> MaterializedThinkerPayload:
        return MaterializedThinkerPayload(
            final_seed_text=adopted.enriched_seed_text or result.enriched_seed_text,
            final_topics=adopted.expanded_topics or result.expanded_topics,
            final_simulation_requirement=adopted.suggested_simulation_prompt or result.suggested_simulation_prompt,
        )
```

Implementation notes:

- Add `POST /api/v1/thinker/jobs/{job_id}/retry`
- Add `POST /api/v1/thinker/jobs/{job_id}/skip`
- These two endpoints are required to satisfy the approved failure behavior, even though the spec summarized them under failure handling rather than the API section

- [ ] **Step 4: Re-run the affected tests**

Run:

```bash
python -m pytest tests/test_thinker_jobs.py tests/test_gateway_thinker_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the materialization and action flow**

```bash
git add thinker/materializer.py thinker/api.py thinker/jobs.py thinker/models.py tests/test_thinker_jobs.py tests/test_gateway_thinker_api.py
git commit -m "feat: add thinker materialize retry and skip flows"
```

### Task 6: Document Thinker Configuration and Workflow

**Files:**
- Modify: `.env.template`
- Modify: `README.md`
- Modify: `vendor/MiroFish/frontend/src/api/index.js`
- Modify: `vendor/MiroFish/frontend/vite.config.js`

- [ ] **Step 1: Add Thinker env vars to `.env.template` and fix the frontend base URL contract**

```dotenv
THINKER_LLM_API_KEY=
THINKER_LLM_BASE_URL=
THINKER_LLM_MODEL=
THINKER_SEARCH_API_KEY=
THINKER_SEARCH_BASE_URL=
THINKER_SCRAPE_API_KEY=
THINKER_SCRAPE_BASE_URL=
VITE_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 2: Point frontend API traffic and Vite dev proxy to Gateway**

```javascript
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
})
```

```javascript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
  }
}
```

Implementation notes:

- All frontend API requests must target Gateway
- Preserve existing `/api/...` paths so MiroFish proxied endpoints and native Thinker endpoints coexist
- Avoid `/api/api/...` by keeping `VITE_API_BASE_URL` at the host root, not the `/api` prefix
- Update the Axios request setup so `FormData` upload requests are not forced to `Content-Type: application/json`

- [ ] **Step 3: Document the new Gateway endpoints and flow in `README.md`**

Add concise documentation for:

- Thinker job creation and status polling
- upload and Polymarket integration points
- retry/skip behavior

- [ ] **Step 4: Run the backend and frontend config verification slice**

Run:

```bash
python -m pytest tests/test_thinker_jobs.py tests/test_gateway_thinker_api.py tests/test_thinker_orchestrator.py -v
npm --prefix vendor/MiroFish/frontend run build
```

Expected: PASS, confirming docs/config edits did not break imports or env loading.

- [ ] **Step 5: Commit the documentation and routing unit**

```bash
git add .env.template README.md vendor/MiroFish/frontend/src/api/index.js vendor/MiroFish/frontend/vite.config.js
git commit -m "docs: document thinker configuration"
```

### Task 7: Add Frontend Thinker API and Utility Helpers

**Files:**
- Create: `vendor/MiroFish/frontend/src/api/thinker.js`
- Create: `vendor/MiroFish/frontend/src/utils/thinker.js`
- Modify: `vendor/MiroFish/frontend/src/store/pendingUpload.js`

- [ ] **Step 1: Implement the frontend API wrapper**

```javascript
import service from './index'

export const createThinkerJob = (data) => service.post('/api/v1/thinker/jobs', data)
export const getThinkerJob = (jobId) => service.get(`/api/v1/thinker/jobs/${jobId}`)
export const materializeThinkerJob = (data) => service.post('/api/v1/thinker/materialize', data)
export const retryThinkerJob = (jobId) => service.post(`/api/v1/thinker/jobs/${jobId}/retry`)
export const skipThinkerJob = (jobId) => service.post(`/api/v1/thinker/jobs/${jobId}/skip`)
```

Implementation notes:

- `createThinkerJob` must accept either JSON payloads or `FormData`
- For `FormData`, let Axios set the multipart boundary automatically instead of forcing JSON headers

- [ ] **Step 2: Add utility helpers for polling, draft hydration, and synthetic seed-file creation**

```javascript
export function buildThinkerSeedFile(materialized) {
  return new File([materialized.final_seed_text], 'thinker_enriched_seed.md', {
    type: 'text/markdown'
  })
}

export function toThinkerDraft(result) {
  return {
    expandedTopics: [...result.expanded_topics],
    enrichedSeedText: result.enriched_seed_text,
    suggestedSimulationPrompt: result.suggested_simulation_prompt
  }
}
```

Implementation notes:

- `pendingUpload.js` must carry enough data for `Process.vue` to continue unchanged
- Store only normalized final values, not raw job internals
- Keep helper functions deterministic so `Home.vue` remains readable

- [ ] **Step 3: Verify the frontend still compiles**

Run:

```bash
npm --prefix vendor/MiroFish/frontend install
npm --prefix vendor/MiroFish/frontend run build
```

Expected: Vite build succeeds.

- [ ] **Step 4: Commit the frontend helper layer**

```bash
git add vendor/MiroFish/frontend/src/api/thinker.js vendor/MiroFish/frontend/src/utils/thinker.js vendor/MiroFish/frontend/src/store/pendingUpload.js
git commit -m "feat: add frontend thinker client helpers"
```

### Task 8: Wire the Upload Flow to Thinker

**Files:**
- Modify: `vendor/MiroFish/frontend/src/views/Home.vue`
- Modify: `vendor/MiroFish/frontend/src/store/pendingUpload.js`

- [ ] **Step 1: Add upload-flow Thinker state to `Home.vue`**

Required state:

- `thinkerEnabled`
- `thinkerJobId`
- `thinkerStatus`
- `thinkerResultDraft`
- `thinkerError`

- [ ] **Step 2: Implement upload job creation using multipart FormData**

Implementation outline:

```javascript
if (activeTab.value === 'upload' && thinkerEnabled.value) {
  const payload = new FormData()
  payload.append('mode', 'upload')
  payload.append('research_direction', formData.value.simulationRequirement)
  files.value.forEach(file => payload.append('files', file))
  const job = await createThinkerJob(payload)
  await pollUntilTerminal(job.job_id)
}
```

- [ ] **Step 3: Implement editable draft, adopt, retry, and skip behavior for upload**

Implementation notes:

- When a job succeeds, hydrate `thinkerResultDraft` from the returned result
- The user edits draft fields locally before clicking adopt
- When the user adopts the result, call `materializeThinkerJob`
- Create a synthetic markdown file from `final_seed_text`
- Pass the original uploads plus the synthetic file into `setPendingUpload`
- Overwrite `simulationRequirement` with `final_simulation_requirement`
- Failure state must expose both `retryThinkerJob` and `skipThinkerJob`
- Skip must preserve the original upload files and prompt

- [ ] **Step 4: Rebuild the frontend after the upload integration**

Run:

```bash
npm --prefix vendor/MiroFish/frontend run build
```

Expected: PASS.

- [ ] **Step 5: Commit the upload integration**

```bash
git add vendor/MiroFish/frontend/src/views/Home.vue vendor/MiroFish/frontend/src/store/pendingUpload.js
git commit -m "feat: wire thinker into upload flow"
```

### Task 9: Wire the Polymarket Flow to Thinker

**Files:**
- Modify: `vendor/MiroFish/frontend/src/views/Home.vue`
- Modify: `vendor/MiroFish/frontend/src/utils/thinker.js`

- [ ] **Step 1: Implement the Polymarket Thinker request path**

```javascript
if (activeTab.value === 'polymarket' && thinkerEnabled.value && selectedEvent.value) {
  const job = await createThinkerJob({
    mode: 'polymarket',
    research_direction: formData.value.simulationRequirement,
    polymarket_event: selectedEvent.value
  })
}
```

- [ ] **Step 2: Implement editable draft, adopt, retry, and skip behavior for Polymarket**

Implementation notes:

- Hydrate an editable draft from the succeeded job result before adopt
- For Polymarket, create a synthetic seed file from `final_seed_text`
- Keep the existing generated Polymarket text file as a fallback only when the user skips Thinker
- After adopt, overwrite the final pending-upload prompt with `final_simulation_requirement`, not the pre-Thinker prompt
- Polymarket failure must expose both `retryThinkerJob` and `skipThinkerJob`
- Preserve the current non-Thinker behavior when the toggle is off

- [ ] **Step 3: Rebuild the frontend after the Polymarket integration**

Run:

```bash
npm --prefix vendor/MiroFish/frontend run build
```

Expected: PASS.

- [ ] **Step 4: Commit the Polymarket integration**

```bash
git add vendor/MiroFish/frontend/src/views/Home.vue vendor/MiroFish/frontend/src/utils/thinker.js
git commit -m "feat: wire thinker into polymarket flow"
```

### Task 10: Run End-to-End Verification Before Handoff

**Files:**
- Modify: none
- Test: `tests/test_thinker_jobs.py`
- Test: `tests/test_thinker_orchestrator.py`
- Test: `tests/test_gateway_thinker_api.py`

- [ ] **Step 1: Run the backend Thinker test suite**

Run:

```bash
python -m pytest tests/test_thinker_jobs.py tests/test_thinker_orchestrator.py tests/test_gateway_thinker_api.py -v
```

Expected: PASS.

- [ ] **Step 2: Run the frontend production build**

Run:

```bash
npm --prefix vendor/MiroFish/frontend run build
```

Expected: PASS.

- [ ] **Step 3: Perform browser smoke checks**

Smoke checklist:

- upload flow with Thinker off still reaches `Process`
- upload flow with Thinker on can create a job, poll, edit the draft, adopt, and continue
- upload flow with Thinker failure offers `retry` and `skip`
- Polymarket flow with Thinker off preserves current behavior
- Polymarket flow with Thinker on can create a job, edit the draft, adopt, and continue
- Polymarket flow with Thinker failure offers `retry` and `skip`

- [ ] **Step 4: Run `git status --short` and confirm only intended files changed**

Run:

```bash
git status --short
```

Expected: only Thinker-related backend/frontend/docs/test files appear.

- [ ] **Step 5: Final integration commit**

```bash
git add pyproject.toml thinker config/settings.py gateway/app.py tests/test_thinker_jobs.py tests/test_thinker_orchestrator.py tests/test_gateway_thinker_api.py .env.template README.md vendor/MiroFish/frontend/src/api/index.js vendor/MiroFish/frontend/src/api/thinker.js vendor/MiroFish/frontend/src/utils/thinker.js vendor/MiroFish/frontend/src/store/pendingUpload.js vendor/MiroFish/frontend/src/views/Home.vue vendor/MiroFish/frontend/vite.config.js
git commit -m "feat: add thinker orchestration flow"
```
