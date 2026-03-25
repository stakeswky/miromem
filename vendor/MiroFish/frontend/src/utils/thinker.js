import { createPendingUploadPayload } from '../store/pendingUpload.js'

const TERMINAL_STATUSES = new Set([
  'succeeded',
  'failed',
  'materialized',
  'skipped'
])
const AVAILABLE_ACTIONS = new Set([
  'retry',
  'skip'
])

const DEFAULT_POLL_INTERVAL_MS = 1500
const DEFAULT_POLL_TIMEOUT_MS = 180000
const DEFAULT_SEED_FILE_NAME = 'thinker_enriched_seed.md'

const toStringValue = value => {
  if (typeof value === 'string') {
    return value
  }
  if (value == null) {
    return ''
  }
  return String(value)
}

const normalizeTopics = topics => {
  if (!Array.isArray(topics)) {
    return []
  }

  return topics
    .map(toStringValue)
    .map(topic => topic.trim())
    .filter(Boolean)
}

const normalizeFiles = files => {
  if (!files) {
    return []
  }

  if (Array.isArray(files)) {
    return files.filter(Boolean)
  }

  return Array.from(files).filter(Boolean)
}

const normalizePolymarketEvent = event => (
  event && !Array.isArray(event) && typeof event === 'object'
    ? event
    : null
)

const delay = ms => new Promise(resolve => setTimeout(resolve, ms))

const defineReadOnlyValue = (target, key, value) => {
  Object.defineProperty(target, key, {
    value,
    enumerable: true,
    writable: false,
    configurable: false
  })

  return target
}

export const THINKER_TERMINAL_STATUSES = Object.freeze([...TERMINAL_STATUSES])

export function isThinkerTerminalStatus(status) {
  return TERMINAL_STATUSES.has(toStringValue(status).trim())
}

export function normalizeThinkerAvailableActions(actions) {
  if (!Array.isArray(actions)) {
    return []
  }

  const normalized = []

  actions.forEach(action => {
    const value = toStringValue(action).trim()
    if (AVAILABLE_ACTIONS.has(value) && !normalized.includes(value)) {
      normalized.push(value)
    }
  })

  return normalized
}

export function normalizeThinkerJobState(job = {}) {
  return {
    status: toStringValue(job?.status).trim(),
    availableActions: normalizeThinkerAvailableActions(
      job?.available_actions ?? job?.availableActions
    ),
    errorMessage: toStringValue(job?.error_message ?? job?.errorMessage)
  }
}

export function extractThinkerErrorMessage(error, fallback = '') {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message
  }

  return fallback
}

export async function pollThinkerJobUntilTerminal(jobId, getJob, options = {}) {
  if (typeof getJob !== 'function') {
    throw new TypeError('pollThinkerJobUntilTerminal requires a getJob function')
  }

  const intervalMs = Number.isFinite(options.intervalMs) && options.intervalMs >= 0
    ? options.intervalMs
    : DEFAULT_POLL_INTERVAL_MS
  const timeoutMs = Number.isFinite(options.timeoutMs) && options.timeoutMs > 0
    ? options.timeoutMs
    : DEFAULT_POLL_TIMEOUT_MS
  const startedAt = Date.now()

  while (true) {
    const job = await getJob(jobId)

    if (typeof options.onUpdate === 'function') {
      options.onUpdate(job)
    }

    if (isThinkerTerminalStatus(job?.status)) {
      return job
    }

    if (Date.now() - startedAt >= timeoutMs) {
      throw new Error(`Timed out waiting for Thinker job ${jobId}`)
    }

    await delay(intervalMs)
  }
}

export async function resolveThinkerPollErrorState(jobId, getJob, error) {
  const fallbackMessage = jobId
    ? `Failed to refresh Thinker job ${jobId}`
    : 'Thinker polling failed'
  const transportErrorMessage = extractThinkerErrorMessage(error, fallbackMessage)

  if (!jobId || typeof getJob !== 'function') {
    return {
      job: null,
      status: '',
      availableActions: [],
      errorMessage: transportErrorMessage,
      isTerminal: false
    }
  }

  try {
    const job = await getJob(jobId)
    const state = normalizeThinkerJobState(job)

    return {
      job,
      status: state.status,
      availableActions: state.availableActions,
      errorMessage: state.errorMessage || transportErrorMessage,
      isTerminal: isThinkerTerminalStatus(state.status)
    }
  } catch {
    return {
      job: null,
      status: '',
      availableActions: [],
      errorMessage: transportErrorMessage,
      isTerminal: false
    }
  }
}

export function normalizeThinkerMaterialized(materialized = {}) {
  const finalTopics = materialized?.final_topics ?? materialized?.finalTopics
  const finalSeedText = materialized?.final_seed_text ?? materialized?.finalSeedText
  const finalSimulationRequirement = materialized?.final_simulation_requirement
    ?? materialized?.finalSimulationRequirement

  return {
    finalTopics: normalizeTopics(finalTopics),
    finalSeedText: toStringValue(finalSeedText),
    finalSimulationRequirement: toStringValue(finalSimulationRequirement)
  }
}

export function buildThinkerJobPayload(options = {}) {
  const mode = toStringValue(options.mode).trim()
  const researchDirection = toStringValue(
    options.researchDirection ?? options.research_direction
  )
  const seedText = toStringValue(options.seedText ?? options.seed_text)
  const files = normalizeFiles(options.files)
  const polymarketEvent = normalizePolymarketEvent(
    options.polymarketEvent ?? options.polymarket_event
  )

  if (mode === 'upload') {
    const payload = new FormData()
    payload.append('mode', mode)
    payload.append('research_direction', researchDirection)

    if (seedText !== '') {
      payload.append('seed_text', seedText)
    }

    files.forEach(file => {
      payload.append('files', file)
    })

    return payload
  }

  const payload = {
    mode,
    research_direction: researchDirection
  }

  if (seedText !== '') {
    payload.seed_text = seedText
  }

  if (mode === 'polymarket' && polymarketEvent) {
    payload.polymarket_event = polymarketEvent
  }

  return payload
}

export function buildScenarioThinkerJobPayload(options = {}) {
  return buildThinkerJobPayload({
    mode: 'topic_only',
    researchDirection: toStringValue(
      options.scenarioDirection ?? options.researchDirection ?? options.direction
    ).trim()
  })
}

export function buildThinkerSeedFile(materialized, options = {}) {
  const normalized = normalizeThinkerMaterialized(materialized)
  const fileName = toStringValue(options.fileName).trim() || DEFAULT_SEED_FILE_NAME

  return new File([normalized.finalSeedText], fileName, {
    type: 'text/markdown',
    lastModified: 0
  })
}

export function hydrateThinkerDraft(result = {}) {
  return {
    expandedTopics: normalizeTopics(result?.expanded_topics),
    enrichedSeedText: toStringValue(result?.enriched_seed_text),
    suggestedSimulationPrompt: toStringValue(result?.suggested_simulation_prompt)
  }
}

export function createScenarioThinkerDraft(options = {}) {
  const thinkerDraft = hydrateThinkerDraft({
    expanded_topics: options.expandedTopics ?? options.expanded_topics,
    enriched_seed_text: (
      options.generatedSeedText
      ?? options.seedText
      ?? options.enrichedSeedText
      ?? options.enriched_seed_text
    ),
    suggested_simulation_prompt: (
      options.suggestedPrompt
      ?? options.suggestedSimulationPrompt
      ?? options.suggested_simulation_prompt
    )
  })
  const originalPrompt = toStringValue(options.originalPrompt)
  const explicitFinalPrompt = (
    options.finalPrompt
    ?? options.final_prompt
    ?? options.finalSimulationPrompt
    ?? options.final_simulation_prompt
    ?? options.finalSimulationRequirement
    ?? options.final_simulation_requirement
  )
  const finalPrompt = explicitFinalPrompt != null
    ? toStringValue(explicitFinalPrompt)
    : (thinkerDraft.suggestedSimulationPrompt || originalPrompt)

  return defineReadOnlyValue({
    ...thinkerDraft,
    generatedSeedText: thinkerDraft.enrichedSeedText,
    suggestedPrompt: thinkerDraft.suggestedSimulationPrompt,
    finalPrompt
  }, 'originalPrompt', originalPrompt)
}

export function buildThinkerMaterializePayload(jobId, draft = {}) {
  return {
    job_id: toStringValue(jobId).trim(),
    adopted: {
      expanded_topics: normalizeTopics(draft?.expandedTopics ?? draft?.expanded_topics),
      enriched_seed_text: toStringValue(
        draft?.generatedSeedText
        ?? draft?.enrichedSeedText
        ?? draft?.enriched_seed_text
      ),
      suggested_simulation_prompt: toStringValue(
        draft?.finalPrompt
        ?? draft?.suggestedPrompt
        ?? draft?.suggestedSimulationPrompt
        ?? draft?.suggested_simulation_prompt
      )
    }
  }
}

const requireScenarioGeneratedSeedText = (value, context) => {
  const generatedSeedText = toStringValue(value).trim()

  if (generatedSeedText === '') {
    throw new Error(`${context} requires a non-empty generatedSeedText`)
  }

  return generatedSeedText
}

const requireScenarioFinalPrompt = (value, context) => {
  const finalPrompt = toStringValue(value).trim()

  if (finalPrompt === '') {
    throw new Error(`${context} requires a non-empty finalPrompt`)
  }

  return finalPrompt
}

export function isScenarioThinkerDraftAdoptable(draft = {}) {
  const generatedSeedText = toStringValue(
    draft?.generatedSeedText
    ?? draft?.enrichedSeedText
    ?? draft?.enriched_seed_text
  ).trim()
  const finalPrompt = toStringValue(
    draft?.finalPrompt
    ?? draft?.final_prompt
    ?? draft?.finalSimulationPrompt
    ?? draft?.final_simulation_prompt
    ?? draft?.finalSimulationRequirement
    ?? draft?.final_simulation_requirement
  ).trim()

  return generatedSeedText !== '' && finalPrompt !== ''
}

export function buildScenarioThinkerMaterializePayload(jobId, draft = {}) {
  const generatedSeedText = requireScenarioGeneratedSeedText(
    draft?.generatedSeedText
    ?? draft?.enrichedSeedText
    ?? draft?.enriched_seed_text,
    'Scenario Thinker materialize payload'
  )
  const finalPrompt = requireScenarioFinalPrompt(
    draft?.finalPrompt
    ?? draft?.final_prompt
    ?? draft?.finalSimulationPrompt
    ?? draft?.final_simulation_prompt
    ?? draft?.finalSimulationRequirement
    ?? draft?.final_simulation_requirement,
    'Scenario Thinker materialize payload'
  )

  return buildThinkerMaterializePayload(jobId, {
    ...draft,
    generatedSeedText,
    finalPrompt
  })
}

export function deriveScenarioThinkerPollRecoveryState(recoveredState = {}) {
  const transportErrorMessage = toStringValue(recoveredState?.errorMessage).trim()
  const fallbackMessage = transportErrorMessage || 'Thinker 轮询失败'

  if (recoveredState?.job && !recoveredState?.isTerminal) {
    return {
      status: 'error',
      errorMessage: `${fallbackMessage}。当前无法继续轮询，请重新生成。`,
      shouldClearDraft: false
    }
  }

  return {
    status: 'error',
    errorMessage: fallbackMessage,
    shouldClearDraft: false
  }
}

export function shouldPreservePolymarketThinkerSession(options = {}) {
  const thinkerJobId = toStringValue(options.thinkerJobId ?? options.jobId).trim()
  const thinkerJobMode = toStringValue(options.thinkerJobMode ?? options.jobMode).trim()
  const selectedEventId = toStringValue(options.selectedEventId).trim()
  const snapshotEventId = toStringValue(
    options.snapshotEventId ?? options.polymarketEventId
  ).trim()
  const unrecoverableTransportError = Boolean(options.unrecoverableTransportError)

  return (
    thinkerJobId !== '' &&
    thinkerJobMode === 'polymarket' &&
    selectedEventId !== '' &&
    snapshotEventId !== '' &&
    selectedEventId === snapshotEventId &&
    !unrecoverableTransportError
  )
}

function buildPendingUploadPayloadFromMaterialized(materialized, options = {}) {
  const normalized = normalizeThinkerMaterialized(materialized)
  const baseFiles = normalizeFiles(options.baseFiles ?? options.files)
  const syntheticSeedFile = buildThinkerSeedFile(normalized, options)
  const fallbackFinalPrompt = toStringValue(options.finalPrompt).trim()
  const finalSimulationRequirement = (
    normalized.finalSimulationRequirement || fallbackFinalPrompt
  )

  return createPendingUploadPayload({
    files: [...baseFiles, syntheticSeedFile],
    simulationRequirement: finalSimulationRequirement,
    finalTopics: normalized.finalTopics,
    finalSeedText: normalized.finalSeedText,
    finalSimulationRequirement
  })
}

export function buildThinkerPendingUploadPayload(materialized, options = {}) {
  return buildPendingUploadPayloadFromMaterialized(materialized, options)
}

function validateScenarioMaterializedPayload(materialized) {
  if (!materialized || Array.isArray(materialized) || typeof materialized !== 'object') {
    throw new TypeError('Scenario Thinker materialized payload must be an object')
  }

  const finalSeedText = normalizeThinkerMaterialized(materialized).finalSeedText.trim()
  if (finalSeedText === '') {
    throw new Error(
      'Scenario Thinker materialized payload must include a non-empty final_seed_text'
    )
  }
}

export function buildScenarioThinkerPendingUploadPayload(materialized, options = {}) {
  validateScenarioMaterializedPayload(materialized)
  const finalPrompt = requireScenarioFinalPrompt(
    options.finalPrompt
    ?? options.final_prompt
    ?? options.finalSimulationPrompt
    ?? options.final_simulation_prompt
    ?? options.finalSimulationRequirement
    ?? options.final_simulation_requirement,
    'Scenario Thinker pending upload'
  )

  return buildPendingUploadPayloadFromMaterialized({
    ...materialized,
    final_simulation_requirement: finalPrompt
  }, {
    ...options,
    finalPrompt
  })
}

export const toThinkerDraft = hydrateThinkerDraft
