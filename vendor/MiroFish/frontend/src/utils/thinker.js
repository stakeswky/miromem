const TERMINAL_STATUSES = new Set([
  'succeeded',
  'failed',
  'materialized',
  'skipped'
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

const delay = ms => new Promise(resolve => setTimeout(resolve, ms))

export const THINKER_TERMINAL_STATUSES = Object.freeze([...TERMINAL_STATUSES])

export function isThinkerTerminalStatus(status) {
  return TERMINAL_STATUSES.has(toStringValue(status).trim())
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

export function normalizeThinkerMaterialized(materialized = {}) {
  const finalSimulationRequirement = toStringValue(
    materialized?.final_simulation_requirement
  )

  return {
    finalTopics: normalizeTopics(materialized?.final_topics),
    finalSeedText: toStringValue(materialized?.final_seed_text),
    finalSimulationRequirement
  }
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

export const toThinkerDraft = hydrateThinkerDraft
