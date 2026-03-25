# Scenario Thinker Entry Design

Date: 2026-03-25
Status: Drafted from approved interactive design review

## Goal

Add a third entry tab beside Upload and Polymarket that lets a user enter:

- a `现实方向`
- a `模拟提示词`

This tab is a mandatory Thinker flow. The system must first expand the `现实方向` into a usable `现实种子`, then show the generated seed to the user for confirmation or editing, and only after adoption continue into the existing prediction workflow.

## Product Decisions

- Entry shape: a third top-level tab, separate from Upload and Polymarket
- Thinker policy: always on for this tab, no Thinker toggle
- Input contract:
  - `现实方向`
  - `模拟提示词`
- Control flow:
  - run Thinker first
  - show editable generated `现实种子`
  - user adopts edited result
  - continue into the existing flow
- Skip policy: not allowed in this tab
- Implementation strategy: reuse the existing Thinker job + materialize + pendingUpload pipeline

## Scope

### In scope

- Add a new third tab in `Home.vue`
- Add a two-field entry form for `现实方向` and `模拟提示词`
- Use Thinker to expand `现实方向` into a `现实种子`
- Let the user edit the generated seed before continuing
- Reuse the current synthetic-file approach to enter `Process.vue`

### Out of scope

- New backend Thinker mode
- New simulation pipeline
- Optional Thinker behavior in this tab
- Skip/fallback path in this tab

## User Experience

### Tab layout

Add a third tab, proposed label: `现况输入`.

This tab contains:

- input: `现实方向`
- input: `模拟提示词`
- status panel:
  - `待启动`
  - `处理中`
  - `可采用`
  - `失败`
- result editor:
  - editable generated `现实种子`
- prompt comparison area:
  - read-only `原始提示词`
  - read-only `Thinker 建议提示词`
  - editable `最终采用提示词`
- actions:
  - `启动引擎`
  - `采用 Thinker 结果`
  - `重新生成`

### Interaction rules

- `启动引擎` is enabled only when both text fields are non-empty
- `处理中` locks the two input fields
- `可采用` unlocks:
  - generated seed editor
  - final prompt editor
- In `可采用` state:
  - `原始提示词` stays visible as read-only reference
  - `Thinker 建议提示词` stays visible as read-only reference
  - `最终采用提示词` is editable and is the only prompt value used after adoption
- The initial value of `最终采用提示词` should be `Thinker 建议提示词`
- `采用 Thinker 结果`:
  - materializes the job
  - creates a synthetic markdown seed file from the final seed text
  - writes the final adopted prompt into `pendingUpload.simulationRequirement`
  - enters the existing `pendingUpload -> Process -> ontology/generate` flow
- `重新生成` re-runs Thinker from the current field values
- There is no `跳过 Thinker`

## State Model

Frontend-local state for the new tab:

- `scenarioDirection`
- `scenarioPrompt`
- `scenarioSuggestedPrompt`
- `scenarioFinalPrompt`
- `scenarioThinkerJobId`
- `scenarioThinkerStatus`
- `scenarioThinkerDraft`
- `scenarioThinkerError`

Suggested UI state machine:

- `idle`
- `running`
- `ready`
- `error`

No fallback state is needed because this tab has no non-Thinker path.

## Backend Reuse Strategy

Do not add a new backend Thinker mode.

The new tab should reuse the existing Thinker job contract as a `topic_only` job:

- `mode = topic_only`
- `research_direction = 现实方向`

The returned Thinker result is interpreted as the candidate `现实种子`.

Prompt ownership in this tab is explicit:

- the user-entered `模拟提示词` remains the read-only `原始提示词`
- Thinker returns `suggested_simulation_prompt` as the read-only `Thinker 建议提示词`
- the frontend owns a separate editable `最终采用提示词`
- only `最终采用提示词` is written into downstream `simulationRequirement`

## Data Flow

1. User opens `现况输入`
2. User enters `现实方向`
3. User enters `模拟提示词`
4. User clicks `启动引擎`
5. Frontend creates a Thinker job using `mode=topic_only`
6. Thinker returns:
   - `expanded_topics`
   - `enriched_seed_text`
   - `suggested_simulation_prompt`
7. Frontend shows:
   - editable generated seed
   - read-only original prompt
   - read-only Thinker suggested prompt
   - editable final adopted prompt initialized from `suggested_simulation_prompt`
8. User edits:
   - generated seed
   - final adopted prompt
9. User clicks `采用 Thinker 结果`
10. Frontend:
   - materializes the Thinker result
   - builds a synthetic seed file from final seed text
   - stores:
     - synthetic seed file in `pendingUpload.files`
     - final adopted prompt in `pendingUpload.simulationRequirement`
11. Frontend navigates to `Process.vue`

## Minimal Code Impact

### Frontend

- `vendor/MiroFish/frontend/src/views/Home.vue`
  - add the third tab
  - add tab-specific state machine
  - reuse existing Thinker helpers
- `vendor/MiroFish/frontend/src/utils/thinker.js`
  - add any small helper needed for scenario-entry payload assembly
- `vendor/MiroFish/frontend/src/store/pendingUpload.js`
  - reuse the normalized payload path already introduced

### Backend

No new backend mode is required.

Existing Thinker endpoints and materialization flow are sufficient.

## Validation

### Required frontend behavior

- Third tab renders and is independent from Upload/Polymarket
- Empty fields keep `启动引擎` disabled
- Successful Thinker run enters editable `ready` state
- Successful Thinker run shows:
  - original prompt
  - Thinker suggested prompt
  - editable final adopted prompt
- Adopt creates a synthetic seed file and navigates to `Process`
- Final prompt in `pendingUpload` matches the user-confirmed final adopted prompt
- No skip path appears in this tab

### Suggested verification

- Frontend smoke check for helper/store behavior
- Browser smoke:
  - `现况输入` -> Thinker success -> edit -> adopt -> `Process`
  - `现况输入` -> Thinker failure -> `重新生成`

## Risks

- If the generated seed is too abstract, the user may need strong editing affordances
- Reusing `topic_only` means the backend still sees this as general Thinker research, not a dedicated scenario mode
- `Home.vue` is already large; this change should avoid further cross-tab coupling

## Recommendation

Implement this feature as a third frontend entry tab that reuses the existing Thinker topic-only pipeline and the current synthetic-file handoff into `Process.vue`. This keeps backend scope small, preserves current prediction flow compatibility, and avoids inventing a second simulation path.
