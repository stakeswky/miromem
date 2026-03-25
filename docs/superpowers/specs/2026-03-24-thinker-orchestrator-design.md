# Thinker Orchestrator Design

Date: 2026-03-24
Status: Drafted and approved in interactive design review

## Goal

Add an optional `Thinker` enhancement layer to MiroMem/MiroFish so users can enter a research direction, trigger deeper background research, and feed the resulting suggestions back into the existing MiroFish flow before simulation starts.

This design intentionally does not put Thinker inside the simulation loop. Thinker only improves the inputs to the existing `graph/build -> simulation/create -> prepare -> start` pipeline.

## Product Decisions

The implementation is based on the following confirmed decisions:

- Integration strategy: Scheme 2, implement Thinker orchestration in MiroMem Gateway
- Model strategy: use external LLM APIs, not self-hosted MiroThinker model serving
- Interaction strategy: semi-automatic flow
- Failure strategy: if Thinker fails, let the user choose `retry` or `skip`

## Scope

### In scope

- Add native Thinker APIs to MiroMem Gateway
- Support three input modes:
  - `topic_only`
  - `upload`
  - `polymarket`
- Return three user-facing result groups:
  - expanded topics
  - enriched seed material
  - suggested simulation prompt
- Allow MiroFish frontend to:
  - create Thinker jobs
  - poll job status
  - adopt or skip the results
- Keep current MiroFish simulation APIs unchanged in meaning

### Out of scope for v1

- Injecting Thinker directly into simulation rounds
- Automatically writing Thinker outputs into graph memory or long-term memory
- Building a separate queue service or worker fleet
- Replacing native Polymarket listing/detail APIs

## Architecture

Thinker will be implemented as a native MiroMem extension, similar to Graph and Evolution.

### New module layout

- `miromem/thinker/api.py`
  - FastAPI router
  - request validation
  - job creation/status/materialization endpoints
- `miromem/thinker/orchestrator.py`
  - research pipeline orchestration
  - mode-specific execution for `topic_only`, `upload`, and `polymarket`
- `miromem/thinker/providers/`
  - `llm_provider.py`
  - `search_provider.py`
  - `scrape_provider.py`
  - `polymarket_provider.py`
- `miromem/thinker/jobs.py`
  - in-process job registry for v1
  - state transitions and job persistence abstraction
- `miromem/thinker/materializer.py`
  - normalize Thinker output into MiroFish-consumable fields
- `miromem/thinker/models.py`
  - request/response schemas

### Responsibility split

- MiroMem owns Thinker orchestration and output normalization
- MiroFish owns user interaction and existing simulation lifecycle
- External providers own actual research capability

## User Flows

### 1. Upload + Thinker

1. User uploads one or more documents and enters a research direction
2. User enables the Thinker option
3. Frontend creates a Thinker job through MiroMem
4. Thinker extracts or reads the uploaded content, runs research, and produces:
   - expanded topics
   - enriched seed text
   - suggested simulation prompt
   - references
5. User can:
   - adopt the suggestions
   - edit them
   - skip Thinker and continue with original inputs
6. MiroFish continues with the normal pipeline using the chosen final inputs

### 2. Polymarket + Thinker

1. User selects a Polymarket event
2. User enters a research direction
3. User enables the Thinker option
4. Frontend creates a Thinker job using the selected event payload
5. Thinker enriches event background and returns:
   - expanded topics
   - enriched event background
   - suggested simulation prompt
   - references
6. User adopts, edits, retries, or skips
7. MiroFish continues with the normal pipeline

### 3. Topic-only + Thinker

1. User provides only a research direction
2. Thinker expands it into candidate topics and a stronger simulation prompt
3. User decides whether to use the result as the initial seed package

## API Contract

### `POST /api/v1/thinker/jobs`

Create a Thinker research job.

Request:

```json
{
  "mode": "topic_only",
  "research_direction": "Will the Fed continue tightening in Q3?",
  "seed_text": "",
  "uploaded_files": [],
  "polymarket_event": null
}
```

Notes:

- `mode` is one of `topic_only`, `upload`, `polymarket`
- `seed_text` is optional for `upload`
- `uploaded_files` may contain extracted text or file metadata, depending on frontend/backend split
- `polymarket_event` contains normalized event detail payload when `mode=polymarket`

Response:

```json
{
  "job_id": "thinker_xxx",
  "status": "created"
}
```

### `GET /api/v1/thinker/jobs/{job_id}`

Return job state and current result.

Response shape:

```json
{
  "job_id": "thinker_xxx",
  "status": "succeeded",
  "mode": "upload",
  "result": {
    "expanded_topics": ["..."],
    "enriched_seed_text": "...",
    "suggested_simulation_prompt": "...",
    "references": [
      { "title": "...", "url": "...", "source_type": "web" }
    ]
  },
  "error": null,
  "can_continue_without_thinker": true
}
```

### `POST /api/v1/thinker/materialize`

Take a succeeded job plus user edits and produce the final normalized payload for MiroFish.

Request:

```json
{
  "job_id": "thinker_xxx",
  "adopted": {
    "expanded_topics": ["..."],
    "enriched_seed_text": "...",
    "suggested_simulation_prompt": "..."
  }
}
```

Response:

```json
{
  "status": "materialized",
  "payload": {
    "final_seed_text": "...",
    "final_topics": ["..."],
    "final_simulation_requirement": "..."
  }
}
```

## State Machine

Thinker jobs have their own state machine and must not reuse simulation states.

- `created`
- `running`
- `succeeded`
- `failed`
- `materialized`
- `skipped`

Rules:

- `created -> running` when background execution starts
- `running -> succeeded` when usable result is produced
- `running -> failed` when execution ends with error
- `succeeded -> materialized` when the user confirms and normalizes output
- `failed -> created` only through explicit retry
- any pre-materialization state may move to `skipped` by user action

## Provider Strategy

v1 uses external APIs behind replaceable providers.

### Required providers

- Main LLM provider
  - OpenAI-compatible or vendor-specific API
  - used for topic expansion, seed synthesis, and prompt suggestion
- Search provider
  - used to collect evidence for the research direction
- Scrape/summary provider
  - used to normalize page content into compact evidence
- Polymarket provider
  - used to normalize selected event detail into Thinker input

### Provider interface requirements

Each provider should expose narrow async methods with deterministic input/output contracts. The orchestrator should not know vendor-specific request shapes.

## Data Model

### Input shape

- `mode`
- `research_direction`
- `seed_text`
- `uploaded_files`
- `polymarket_event`

### Result shape

- `expanded_topics: list[str]`
- `enriched_seed_text: str`
- `suggested_simulation_prompt: str`
- `references: list[Reference]`
- `meta: dict`

### Error shape

- `error_code`
- `error_message`
- `retryable`
- `can_continue_without_thinker`

## MiroFish Integration

### Frontend

MiroFish frontend should:

- add a Thinker toggle in both upload and Polymarket flows
- create jobs via MiroMem Gateway
- poll status until terminal state
- expose user actions:
  - adopt
  - edit
  - retry
  - skip

### Backend

MiroFish backend does not need to embed Thinker into `/api/simulation/prepare` or `/api/simulation/start` in v1.

Instead, it should consume the normalized payload from `materialize` and pass it into the existing simulation flow as if the user had entered the improved seed and prompt manually.

## Failure Handling

If Thinker fails:

- do not auto-run the original path silently
- return a structured failure response
- allow the frontend to present:
  - retry
  - skip

This matches the confirmed product requirement that Thinker failure should be user-decidable.

## Testing Strategy

### Unit tests

- orchestrator mode selection
- provider failure handling
- result normalization
- state transition validation

### API tests

- create job
- get status
- materialize result
- failed job response
- retry/skip semantics

### End-to-end tests

- upload + Thinker happy path
- upload + Thinker failure + skip
- Polymarket + Thinker happy path
- Polymarket + Thinker failure + retry

## Rollout Plan

### Phase 1

- add `miromem/thinker` module
- add Gateway routes
- implement in-process job manager
- return mocked or stubbed results behind provider abstraction

### Phase 2

- connect external LLM/search/scrape providers
- support `topic_only`
- add tests for orchestration and job status

### Phase 3

- support `upload` and `polymarket`
- wire MiroFish frontend to Thinker APIs
- verify skip/retry flows in browser tests

### Phase 4

- improve output quality and provider configuration
- optionally persist research artifacts for later graph/memory ingestion

## Risks

- External API latency may make research jobs noticeably slower than the native flow
- Provider quotas and failures may create intermittent degraded behavior
- Upload flow may require additional extraction/normalization for larger PDFs
- If output contracts are loose, frontend and backend integration will drift quickly

## Non-goals

- Replacing MiroFish simulation logic
- Building a universal research memory platform in v1
- Achieving source-perfect research provenance in the first iteration

## Recommendation

Implement Thinker as a native Gateway extension with its own job state machine and provider abstraction. Keep MiroFish as the presentation and simulation layer, and only let Thinker produce improved inputs for the existing workflow.
