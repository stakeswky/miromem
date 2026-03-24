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

export function buildThinkerMaterializePayload(jobId, draft = {}) {
  return {
    job_id: toStringValue(jobId).trim(),
    adopted: {
      expanded_topics: normalizeTopics(draft?.expandedTopics ?? draft?.expanded_topics),
      enriched_seed_text: toStringValue(
        draft?.enrichedSeedText ?? draft?.enriched_seed_text
      ),
      suggested_simulation_prompt: toStringValue(
        draft?.suggestedSimulationPrompt ?? draft?.suggested_simulation_prompt
      )
    }
  }
}

export function buildThinkerPendingUploadPayload(materialized, options = {}) {
  const normalized = normalizeThinkerMaterialized(materialized)
  const baseFiles = normalizeFiles(options.baseFiles ?? options.files)
  const syntheticSeedFile = buildThinkerSeedFile(normalized, options)

  return {
    files: [...baseFiles, syntheticSeedFile],
    simulationRequirement: normalized.finalSimulationRequirement,
    finalTopics: normalized.finalTopics,
    finalSeedText: normalized.finalSeedText,
    finalSimulationRequirement: normalized.finalSimulationRequirement
  }
}

export const toThinkerDraft = hydrateThinkerDraft
