import assert from 'node:assert/strict'
import { File as NodeFile } from 'node:buffer'

if (typeof globalThis.File === 'undefined') {
  globalThis.File = NodeFile
}

const {
  buildScenarioThinkerJobPayload,
  buildScenarioThinkerPendingUploadPayload,
  buildThinkerSeedFile,
  createScenarioThinkerDraft,
  normalizeThinkerAvailableActions,
  normalizeThinkerMaterialized,
  resolveThinkerPollErrorState,
  shouldPreservePolymarketThinkerSession
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

async function testScenarioThinkerJobPayloadUsesTopicOnlyMode() {
  const payload = buildScenarioThinkerJobPayload({
    scenarioDirection: 'Fed pause with sticky inflation',
    scenarioPrompt: 'What happens to rates-sensitive assets?'
  })

  assert.equal(payload.mode, 'topic_only')
  assert.equal(payload.research_direction, 'Fed pause with sticky inflation')
  assert.equal(
    Object.hasOwn(payload, 'simulationRequirement'),
    false,
    'scenario helper should only forward the direction into the topic_only Thinker job payload'
  )
}

async function testScenarioThinkerDraftTracksPromptOwnership() {
  const draft = createScenarioThinkerDraft({
    originalPrompt: 'What happens to rates-sensitive assets?',
    suggestedPrompt: 'Model rates-sensitive assets under a sticky inflation pause.',
    finalPrompt: 'Focus on REITs and duration-sensitive equities.',
    seedText: '# Expanded seed'
  })

  assert.equal(draft.originalPrompt, 'What happens to rates-sensitive assets?')
  assert.equal(
    draft.suggestedPrompt,
    'Model rates-sensitive assets under a sticky inflation pause.'
  )
  assert.equal(
    draft.finalPrompt,
    'Focus on REITs and duration-sensitive equities.',
    'finalPrompt should stay distinct from both the original and Thinker-suggested prompts'
  )
  assert.equal(draft.generatedSeedText, '# Expanded seed')
  assert.throws(
    () => {
      draft.originalPrompt = 'mutated'
    },
    TypeError,
    'originalPrompt should remain read-only'
  )
}

async function testScenarioPendingUploadUsesFinalPromptAndAdoptedSeed() {
  const draft = createScenarioThinkerDraft({
    originalPrompt: 'What happens to rates-sensitive assets?',
    suggestedPrompt: 'Model rates-sensitive assets under a sticky inflation pause.',
    finalPrompt: 'Focus on REITs and duration-sensitive equities.',
    seedText: '# Final adopted seed'
  })

  const pendingPayload = buildScenarioThinkerPendingUploadPayload(draft)

  assert.equal(
    pendingPayload.simulationRequirement,
    'Focus on REITs and duration-sensitive equities.',
    'scenario pending upload should use the final adopted prompt downstream'
  )
  assert.equal(
    pendingPayload.finalSimulationRequirement,
    'Focus on REITs and duration-sensitive equities.'
  )
  assert.equal(pendingPayload.finalSeedText, '# Final adopted seed')
  assert.equal(pendingPayload.files.length, 1)
  assert.equal(
    await pendingPayload.files[0].text(),
    '# Final adopted seed',
    'scenario synthetic seed file should contain the adopted seed text'
  )
}

async function testShouldPreservePolymarketThinkerSession() {
  assert.equal(
    shouldPreservePolymarketThinkerSession({
      thinkerJobId: 'job-1',
      thinkerJobMode: 'polymarket',
      selectedEventId: 'event-1',
      snapshotEventId: 'event-1'
    }),
    true,
    'an engaged Polymarket Thinker session should stay protected for the same selected event'
  )

  assert.equal(
    shouldPreservePolymarketThinkerSession({
      thinkerJobId: 'job-1',
      thinkerJobMode: 'polymarket',
      selectedEventId: 'event-2',
      snapshotEventId: 'event-1'
    }),
    false,
    'changing the selected event should allow the old Polymarket session to be cleared cleanly'
  )

  assert.equal(
    shouldPreservePolymarketThinkerSession({
      thinkerJobId: 'job-1',
      thinkerJobMode: 'upload',
      selectedEventId: 'event-1',
      snapshotEventId: 'event-1'
    }),
    false,
    'upload Thinker sessions should not lock the Polymarket fallback path'
  )

  assert.equal(
    shouldPreservePolymarketThinkerSession({
      thinkerJobId: 'job-1',
      thinkerJobMode: 'polymarket',
      selectedEventId: 'event-1',
      snapshotEventId: 'event-1',
      unrecoverableTransportError: true
    }),
    false,
    'an unrecoverable polling transport failure must allow the user to escape the locked Polymarket session'
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
  await testScenarioThinkerJobPayloadUsesTopicOnlyMode()
  await testScenarioThinkerDraftTracksPromptOwnership()
  await testScenarioPendingUploadUsesFinalPromptAndAdoptedSeed()
  await testShouldPreservePolymarketThinkerSession()
  await testNormalizeThinkerAvailableActions()
  await testResolveThinkerPollErrorStateKeepsTransportFailureSeparate()
  await testResolveThinkerPollErrorStateUsesServerActionsForTerminalFailure()
  clearPendingUpload()
  console.log('thinker smoke check passed')
}

await main()
