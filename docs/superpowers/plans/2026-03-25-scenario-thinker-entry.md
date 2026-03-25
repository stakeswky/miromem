# Scenario Thinker Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third `现况输入` tab that always uses Thinker to expand `现实方向` into a `现实种子`, then lets the user confirm/edit the generated seed and final prompt before continuing into the existing `Process` flow.

**Architecture:** Reuse the existing Thinker `topic_only -> materialize -> pendingUpload -> Process` pipeline instead of inventing a new backend mode. The implementation is frontend-heavy: add one new tab in `Home.vue`, extend the existing Thinker helper layer for scenario-entry payload assembly, and reuse the current synthetic seed-file handoff to `Process.vue`.

**Tech Stack:** Vue 3, Vite, Axios, existing frontend Thinker helpers, existing Gateway Thinker API, Node smoke script

---

## File Map

### New files

- None required for the first implementation pass

### Modified frontend files

- `vendor/MiroFish/frontend/src/views/Home.vue`
  Add the third `现况输入` tab, its local state machine, and the scenario-entry Thinker flow
- `vendor/MiroFish/frontend/src/utils/thinker.js`
  Add scenario-entry-specific helper functions for payload shaping and draft normalization
- `vendor/MiroFish/frontend/src/store/pendingUpload.js`
  Reuse or extend normalized payload creation so scenario-entry adoption reaches `Process.vue` unchanged
- `vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs`
  Add smoke coverage for scenario-entry helper/store behavior

### Verification targets

- `vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs`
- Browser smoke against `Home.vue`
- `npm --prefix vendor/MiroFish/frontend run build`

## Task 1: Scenario Helper Layer

**Files:**
- Modify: `vendor/MiroFish/frontend/src/utils/thinker.js`
- Modify: `vendor/MiroFish/frontend/src/store/pendingUpload.js`
- Modify: `vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs`

- [ ] **Step 1: Write the failing smoke assertions for scenario-entry helpers**

Add smoke coverage for these behaviors:

- scenario-entry job payload uses `mode: 'topic_only'`
- scenario-entry prompt handling distinguishes:
  - original prompt
  - Thinker suggested prompt
  - final adopted prompt
- scenario-entry pending-upload payload writes the final adopted prompt, not the original prompt
- scenario-entry synthetic seed file contains the adopted seed text

Example smoke assertions:

```js
const jobPayload = buildScenarioThinkerJobPayload({
  scenarioDirection: 'Fed pause with sticky inflation',
  scenarioPrompt: 'What happens to rates-sensitive assets?',
})
assert.equal(jobPayload.mode, 'topic_only')
assert.equal(jobPayload.research_direction, 'Fed pause with sticky inflation')

const pending = createPendingUploadPayload({
  files: [buildThinkerSeedFile({ finalSeedText: 'expanded seed' })],
  simulationRequirement: 'original prompt',
  finalSimulationRequirement: 'final adopted prompt',
})
assert.equal(pending.simulationRequirement, 'final adopted prompt')
```

- [ ] **Step 2: Run the smoke check to verify it fails**

Run:

```bash
node vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs
```

Expected: FAIL because scenario-entry helper behavior does not exist yet.

- [ ] **Step 3: Implement the minimal scenario-entry helpers**

Add focused helpers in `utils/thinker.js`, for example:

```js
export function buildScenarioThinkerJobPayload({ scenarioDirection }) {
  return {
    mode: 'topic_only',
    research_direction: scenarioDirection,
  }
}

export function createScenarioThinkerDraft({
  originalPrompt,
  suggestedPrompt,
  seedText,
}) {
  return {
    generatedSeedText: seedText,
    originalPrompt,
    suggestedPrompt,
    finalPrompt: suggestedPrompt || originalPrompt,
  }
}
```

Implementation notes:

- Keep `originalPrompt` read-only in data shape
- Keep `finalPrompt` as the only downstream truth
- Reuse `createPendingUploadPayload(...)` rather than duplicating `pendingUpload` normalization in `Home.vue`

- [ ] **Step 4: Run the smoke check again**

Run:

```bash
node vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs
```

Expected: PASS

- [ ] **Step 5: Commit the helper layer**

```bash
git add vendor/MiroFish/frontend/src/utils/thinker.js vendor/MiroFish/frontend/src/store/pendingUpload.js vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs
git commit -m "feat: add scenario thinker helper layer"
```

## Task 2: Add the Scenario Entry Tab UI

**Files:**
- Modify: `vendor/MiroFish/frontend/src/views/Home.vue`

- [ ] **Step 1: Add the third tab and minimal failing wiring**

Add a third top-level tab label such as `现况输入`, plus local reactive state:

```js
const scenarioForm = ref({
  direction: '',
  prompt: '',
})
const scenarioThinkerJobId = ref('')
const scenarioThinkerStatus = ref('idle')
const scenarioThinkerDraft = ref(createEmptyScenarioDraft())
const scenarioThinkerError = ref('')
```

Also update `canSubmit` so the scenario tab is only submittable when both fields are non-empty.

- [ ] **Step 2: Run the frontend build to catch the incomplete state**

Run:

```bash
npm --prefix vendor/MiroFish/frontend run build
```

Expected: FAIL or incomplete UI placeholders still prevent the desired interaction. If it still builds, continue and rely on the browser smoke in Task 3 to prove the missing behavior.

- [ ] **Step 3: Implement the scenario success-state UI**

Add UI for:

- `现实方向` input
- `模拟提示词` input
- status area
- editable generated seed editor
- read-only `原始提示词`
- read-only `Thinker 建议提示词`
- editable `最终采用提示词`
- `启动引擎`
- `采用 Thinker 结果`
- `重新生成`

Implementation notes:

- This tab must not show a Thinker toggle
- This tab must not show a skip button
- `running` locks both inputs
- `ready` unlocks generated seed and final prompt editor only
- The shared footer `启动引擎` button is hidden for this tab
- This tab uses its own local action buttons only:
  - `idle`: show `启动引擎`
  - `running`: no start action, show status only
  - `ready`: show `采用 Thinker 结果` and `重新生成`
  - `error`: show `重新生成`

- [ ] **Step 4: Re-run the frontend build**

Run:

```bash
npm --prefix vendor/MiroFish/frontend run build
```

Expected: PASS

- [ ] **Step 5: Commit the UI shell**

```bash
git add vendor/MiroFish/frontend/src/views/Home.vue
git commit -m "feat: add scenario thinker tab shell"
```

## Task 3: Wire the Scenario Thinker Flow

**Files:**
- Modify: `vendor/MiroFish/frontend/src/views/Home.vue`
- Modify: `vendor/MiroFish/frontend/src/utils/thinker.js`
- Modify: `vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs`

- [ ] **Step 1: Add failing smoke/browser expectations for the scenario flow**

Required scenario-flow checks:

- `启动引擎` builds a `topic_only` Thinker job from `现实方向`
- on success, the draft is hydrated with:
  - generated seed
  - original prompt
  - suggested prompt
  - final adopted prompt
- adopt builds a synthetic seed file and uses the final adopted prompt downstream
- failure allows `重新生成` only
- no skip path exists in this tab

- [ ] **Step 2: Run the smoke script to verify the new expectations fail**

Run:

```bash
node vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs
```

Expected: FAIL because the scenario flow has not been wired yet.

- [ ] **Step 3: Implement the scenario Thinker lifecycle in `Home.vue`**

Suggested flow:

```js
const startScenarioThinkerFlow = async () => {
  const job = await createThinkerJob(
    buildScenarioThinkerJobPayload({
      scenarioDirection: scenarioForm.value.direction,
    })
  )
  const terminalJob = await pollThinkerJobUntilTerminal(job.job_id, getThinkerJob)
  scenarioThinkerDraft.value = createScenarioThinkerDraft({
    originalPrompt: scenarioForm.value.prompt,
    suggestedPrompt: terminalJob.result?.suggested_simulation_prompt ?? '',
    seedText: terminalJob.result?.enriched_seed_text ?? '',
  })
}
```

Adopt flow:

```js
const materialized = await materializeThinkerJob({
  job_id: scenarioThinkerJobId.value,
  adopted: {
    enriched_seed_text: scenarioThinkerDraft.value.generatedSeedText,
    suggested_simulation_prompt: scenarioThinkerDraft.value.finalPrompt,
  },
})

const pendingPayload = createPendingUploadPayload({
  files: [buildThinkerSeedFile(materialized.payload)],
  simulationRequirement: scenarioForm.value.prompt,
  finalSimulationRequirement: scenarioThinkerDraft.value.finalPrompt,
  finalSeedText: materialized.payload.final_seed_text,
  finalTopics: materialized.payload.final_topics,
})
```

Implementation notes:

- `现实方向` is not sent into `pendingUpload`
- only the synthetic seed file and final adopted prompt continue downstream
- `重新生成` uses the current form state and discards the previous job state
- `startSimulation()` must route scenario-tab submissions through this scenario flow, not the upload or polymarket branches
- The global `canSubmit` / footer button path must not be reused for the scenario tab
- Scenario-tab actions must stay local to the scenario panel to avoid duplicate entry points

- [ ] **Step 4: Run smoke check and frontend build**

Run:

```bash
node vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs
npm --prefix vendor/MiroFish/frontend run build
```

Expected: both PASS

- [ ] **Step 5: Commit the scenario flow**

```bash
git add vendor/MiroFish/frontend/src/views/Home.vue vendor/MiroFish/frontend/src/utils/thinker.js vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs
git commit -m "feat: wire scenario thinker entry flow"
```

## Task 4: End-to-End Verification

**Files:**
- Modify: none

- [ ] **Step 1: Run the relevant backend regression slice**

Run:

```bash
. .venv/bin/activate && python -m pytest tests/test_thinker_jobs.py tests/test_thinker_orchestrator.py tests/test_gateway_thinker_api.py tests/test_gateway_polymarket_proxy.py -q
```

Expected: PASS

- [ ] **Step 2: Run frontend smoke and production build**

Run:

```bash
node vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs
npm --prefix vendor/MiroFish/frontend run build
```

Expected: both PASS

- [ ] **Step 3: Run browser smoke for the new third tab**

Smoke checklist:

- open `现况输入`
- verify the shared footer `启动引擎` button is hidden for this tab
- enter `现实方向`
- enter `模拟提示词`
- start Thinker
- verify `ready` state shows:
  - generated seed editor
  - original prompt
  - suggested prompt
  - editable final adopted prompt
- edit generated seed and/or final prompt
- adopt and confirm navigation to `Process`
- verify there is no skip button in this tab
- verify Thinker failure path still offers only `重新生成`
- verify switching back to Upload/Polymarket restores their existing footer/button behavior unchanged

- [ ] **Step 4: Check working tree cleanliness**

Run:

```bash
git status --short
```

Expected: only intended implementation files are modified

- [ ] **Step 5: Final feature commit if needed**

```bash
git add vendor/MiroFish/frontend/src/views/Home.vue vendor/MiroFish/frontend/src/utils/thinker.js vendor/MiroFish/frontend/src/store/pendingUpload.js vendor/MiroFish/frontend/scripts/thinker-smoke-check.mjs
git commit -m "feat: add scenario thinker entry"
```
