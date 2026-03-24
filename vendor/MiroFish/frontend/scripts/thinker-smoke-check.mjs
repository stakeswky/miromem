import assert from 'node:assert/strict'
import { File as NodeFile } from 'node:buffer'

if (typeof globalThis.File === 'undefined') {
  globalThis.File = NodeFile
}

const {
  buildThinkerJobPayload,
  buildThinkerMaterializePayload,
  buildThinkerPendingUploadPayload,
  buildThinkerSeedFile,
  normalizeThinkerAvailableActions,
  normalizeThinkerMaterialized,
  resolveThinkerPollErrorState
} = await import('../src/utils/thinker.js')
const {
  createPendingUploadPayload,
  clearPendingUpload,
  getPendingUpload,
  setPendingUpload
} = await import('../src/store/pendingUpload.js')

async function testExplicitEmptyPromptPreserved() {
  clearPendingUpload()

  const sourceFile = new File(['seed'], 'seed.txt', { type: 'text/plain' })
  setPendingUpload({
    files: [sourceFile],
    simulationRequirement: 'old prompt',
    finalSimulationRequirement: ''
  })

  const pending = getPendingUpload()
  assert.equal(
    pending.simulationRequirement,
    '',
    'explicit empty finalSimulationRequirement should remain empty'
  )
  assert.equal(
    pending.finalSimulationRequirement,
    '',
    'stored finalSimulationRequirement should remain empty'
  )
}

async function testNormalizeThenBuildSeedFileFlow() {
  const normalized = normalizeThinkerMaterialized({
    final_topics: ['Macro'],
    final_seed_text: '# Enriched seed',
    final_simulation_requirement: 'prompt'
  })

  const seedFile = buildThinkerSeedFile(normalized)
  assert.equal(seedFile.name, 'thinker_enriched_seed.md')
  assert.equal(seedFile.type, 'text/markdown')
  assert.equal(
    await seedFile.text(),
    '# Enriched seed',
    'normalizeThinkerMaterialized() output should remain usable by buildThinkerSeedFile()'
  )
}

async function testLegacyPendingUploadSignature() {
  clearPendingUpload()

  const legacyFile = new File(['legacy'], 'legacy.txt', { type: 'text/plain' })
  setPendingUpload([legacyFile], 'legacy prompt')

  const pending = getPendingUpload()
  assert.deepEqual(pending.files, [legacyFile])
  assert.equal(pending.simulationRequirement, 'legacy prompt')
  assert.equal(
    pending.finalSimulationRequirement,
    'legacy prompt',
    'legacy setPendingUpload(files, requirement) should still populate finalSimulationRequirement'
  )
  assert.deepEqual(pending.finalTopics, [])
  assert.equal(pending.finalSeedText, '')
  assert.equal(pending.isPending, true)
}

async function testCreatePendingUploadPayloadForThinkerAdoption() {
  const originalFile = new File(['original'], 'seed.txt', { type: 'text/plain' })
  const syntheticSeedFile = new File(['# Draft'], 'thinker_enriched_seed.md', {
    type: 'text/markdown'
  })

  const payload = createPendingUploadPayload({
    files: [originalFile, syntheticSeedFile],
    simulationRequirement: 'original prompt',
    finalTopics: [' Macro ', '', 'Rates'],
    finalSeedText: '# Draft',
    finalSimulationRequirement: 'final prompt'
  })

  assert.deepEqual(
    payload.files,
    [originalFile, syntheticSeedFile],
    'helper should preserve both original uploads and the synthetic seed file'
  )
  assert.equal(
    payload.simulationRequirement,
    'final prompt',
    'helper should expose the adopted prompt as the downstream simulation requirement'
  )
  assert.equal(payload.finalSimulationRequirement, 'final prompt')
  assert.deepEqual(payload.finalTopics, ['Macro', 'Rates'])
  assert.equal(payload.finalSeedText, '# Draft')
}

async function testBuildThinkerJobPayloadForUpload() {
  const uploadFile = new File(['upload'], 'upload.txt', { type: 'text/plain' })

  const payload = buildThinkerJobPayload({
    mode: 'upload',
    researchDirection: 'simulate upload',
    files: [uploadFile]
  })

  assert.equal(payload.get('mode'), 'upload')
  assert.equal(payload.get('research_direction'), 'simulate upload')
  assert.deepEqual(
    payload.getAll('files'),
    [uploadFile],
    'upload thinker payload should keep the original file objects'
  )
}

async function testBuildThinkerJobPayloadForPolymarket() {
  const event = { id: 'market-1', title: 'Fed event' }

  const payload = buildThinkerJobPayload({
    mode: 'polymarket',
    researchDirection: 'simulate polymarket',
    polymarketEvent: event
  })

  assert.deepEqual(payload, {
    mode: 'polymarket',
    research_direction: 'simulate polymarket',
    polymarket_event: event
  })
}

async function testBuildThinkerMaterializePayloadUsesEditableDraft() {
  const payload = buildThinkerMaterializePayload('job-123', {
    expandedTopics: [' Macro ', '', 'Rates'],
    enrichedSeedText: '# Adopted seed',
    suggestedSimulationPrompt: 'Use the adopted prompt'
  })

  assert.deepEqual(payload, {
    job_id: 'job-123',
    adopted: {
      expanded_topics: ['Macro', 'Rates'],
      enriched_seed_text: '# Adopted seed',
      suggested_simulation_prompt: 'Use the adopted prompt'
    }
  })
}

async function testBuildThinkerPendingUploadPayloadForPolymarketAdoption() {
  const payload = buildThinkerPendingUploadPayload({
    final_topics: ['Macro'],
    final_seed_text: '# Synthetic seed',
    final_simulation_requirement: 'Use final simulation requirement'
  })

  assert.equal(
    payload.simulationRequirement,
    'Use final simulation requirement',
    'materialized final_simulation_requirement should replace the pending upload prompt'
  )
  assert.equal(payload.finalSimulationRequirement, 'Use final simulation requirement')
  assert.equal(payload.files.length, 1)
  assert.equal(payload.files[0].name, 'thinker_enriched_seed.md')
  assert.equal(
    await payload.files[0].text(),
    '# Synthetic seed',
    'polymarket adopt should synthesize a single seed file from final_seed_text'
  )
}

async function testNormalizeThinkerAvailableActions() {
  assert.deepEqual(
    normalizeThinkerAvailableActions(['retry', 'skip', 'skip', 'unknown']),
    ['retry', 'skip'],
    'only supported Thinker actions should remain, in stable order'
  )
  assert.deepEqual(
    normalizeThinkerAvailableActions(null),
    [],
    'missing available_actions should normalize to an empty array'
  )
}

async function testResolveThinkerPollErrorStateKeepsTransportFailureSeparate() {
  const recovered = await resolveThinkerPollErrorState(
    'job-running',
    async jobId => ({
      job_id: jobId,
      status: 'running',
      available_actions: []
    }),
    new Error('network flake')
  )

  assert.equal(recovered.status, 'running')
  assert.equal(
    recovered.isTerminal,
    false,
    'a recovered non-terminal job must not be treated as terminally failed'
  )
  assert.deepEqual(recovered.availableActions, [])
  assert.equal(recovered.errorMessage, 'network flake')
}

async function testResolveThinkerPollErrorStateUsesServerActionsForTerminalFailure() {
  const recovered = await resolveThinkerPollErrorState(
    'job-failed',
    async jobId => ({
      job_id: jobId,
      status: 'failed',
      available_actions: ['retry', 'skip'],
      error_message: 'provider unavailable'
    }),
    new Error('poll timeout')
  )

  assert.equal(recovered.status, 'failed')
  assert.equal(recovered.isTerminal, true)
  assert.deepEqual(
    recovered.availableActions,
    ['retry', 'skip'],
    'retry/skip availability must come from the server payload'
  )
  assert.equal(
    recovered.errorMessage,
    'provider unavailable',
    'terminal failure should surface the backend error details when they are available'
  )
}

async function main() {
  await testExplicitEmptyPromptPreserved()
  await testNormalizeThenBuildSeedFileFlow()
  await testLegacyPendingUploadSignature()
  await testCreatePendingUploadPayloadForThinkerAdoption()
  await testBuildThinkerJobPayloadForUpload()
  await testBuildThinkerJobPayloadForPolymarket()
  await testBuildThinkerMaterializePayloadUsesEditableDraft()
  await testBuildThinkerPendingUploadPayloadForPolymarketAdoption()
  await testNormalizeThinkerAvailableActions()
  await testResolveThinkerPollErrorStateKeepsTransportFailureSeparate()
  await testResolveThinkerPollErrorStateUsesServerActionsForTerminalFailure()
  clearPendingUpload()
  console.log('thinker smoke check passed')
}

await main()
