import assert from 'node:assert/strict'
import { File as NodeFile } from 'node:buffer'

if (typeof globalThis.File === 'undefined') {
  globalThis.File = NodeFile
}

const {
  buildScenarioThinkerJobPayload,
  buildScenarioThinkerMaterializePayload,
  buildScenarioThinkerPendingUploadPayload,
  buildThinkerSeedFile,
  createScenarioThinkerDraft,
  deriveScenarioThinkerPollRecoveryState,
  isScenarioThinkerDraftAdoptable,
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

async function testScenarioFlowContractFromReadyDraftToPendingUpload() {
  clearPendingUpload()

  const originalPrompt = 'What happens to rates-sensitive assets?'
  const suggestedPrompt = 'Model rates-sensitive assets under a sticky inflation pause.'
  const adoptedPrompt = 'Focus on REITs and duration-sensitive equities.'

  const draft = createScenarioThinkerDraft({
    originalPrompt,
    suggestedPrompt,
    seedText: '# Expanded seed'
  })

  assert.equal(draft.originalPrompt, originalPrompt)
  assert.equal(draft.suggestedPrompt, suggestedPrompt)
  assert.equal(
    draft.finalPrompt,
    suggestedPrompt,
    'ready drafts should default the adopted prompt to the Thinker suggestion'
  )
  assert.equal(draft.generatedSeedText, '# Expanded seed')
  assert.equal(
    isScenarioThinkerDraftAdoptable(draft),
    true,
    'scenario drafts should only become adoptable when both the seed and adopted prompt are present'
  )
  assert.throws(
    () => {
      draft.originalPrompt = 'mutated'
    },
    TypeError,
    'originalPrompt should remain read-only'
  )

  draft.finalPrompt = adoptedPrompt

  const materializePayload = buildScenarioThinkerMaterializePayload('job-scenario-1', draft)
  assert.equal(materializePayload.job_id, 'job-scenario-1')
  assert.equal(
    materializePayload.adopted.suggested_simulation_prompt,
    adoptedPrompt,
    'scenario materialization should persist the final adopted prompt without fallback'
  )
  assert.equal(
    materializePayload.adopted.enriched_seed_text,
    '# Expanded seed',
    'scenario materialization should persist the edited seed draft'
  )

  const pendingPayload = buildScenarioThinkerPendingUploadPayload({
    final_topics: [' Macro ', '', 'Rates'],
    final_seed_text: '# Final adopted seed',
    final_simulation_requirement: 'backend should not override the adopted prompt'
  }, {
    finalPrompt: adoptedPrompt
  })

  setPendingUpload(pendingPayload)

  const pending = getPendingUpload()
  assert.equal(
    pending.simulationRequirement,
    adoptedPrompt,
    'scenario downstream routing must use the final adopted prompt as the only truth'
  )
  assert.equal(pending.finalSimulationRequirement, adoptedPrompt)
  assert.deepEqual(pending.finalTopics, ['Macro', 'Rates'])
  assert.equal(pending.finalSeedText, '# Final adopted seed')
  assert.equal(pending.files.length, 1)
  assert.equal(
    await pending.files[0].text(),
    '# Final adopted seed',
    'scenario synthetic seed file should contain the materialized adopted seed text'
  )
}

async function testScenarioPendingUploadRejectsMalformedMaterializedPayload() {
  assert.throws(
    () => buildScenarioThinkerPendingUploadPayload(null, {
      finalPrompt: 'Focus on REITs and duration-sensitive equities.'
    }),
    /must be an object/i,
    'scenario pending upload should fail fast when materialized payload is not an object'
  )

  assert.throws(
    () => buildScenarioThinkerPendingUploadPayload({
      final_topics: ['Rates'],
      final_seed_text: '   '
    }, {
      finalPrompt: 'Focus on REITs and duration-sensitive equities.'
    }),
    /final_seed_text/i,
    'scenario pending upload should fail fast when final_seed_text is missing or empty'
  )

  assert.throws(
    () => buildScenarioThinkerMaterializePayload('job-scenario-1', {
      generatedSeedText: '# Expanded seed',
      finalPrompt: '   '
    }),
    /finalPrompt/i,
    'scenario materialization should fail fast when the adopted prompt is blank'
  )

  assert.equal(
    isScenarioThinkerDraftAdoptable({
      generatedSeedText: '   ',
      finalPrompt: 'Focus on REITs and duration-sensitive equities.'
    }),
    false,
    'scenario drafts with blank generated seed must not be adoptable'
  )

  assert.throws(
    () => buildScenarioThinkerMaterializePayload('job-scenario-1', {
      generatedSeedText: '   ',
      finalPrompt: 'Focus on REITs and duration-sensitive equities.'
    }),
    /generatedSeedText/i,
    'scenario materialization should fail fast when the adopted seed is blank'
  )

  assert.throws(
    () => buildScenarioThinkerPendingUploadPayload({
      final_topics: ['Rates'],
      final_seed_text: '# Final adopted seed',
      final_simulation_requirement: 'backend prompt'
    }),
    /finalPrompt/i,
    'scenario pending upload should fail fast when the final adopted prompt is missing'
  )
}

async function testScenarioPollRecoveryLeavesRegeneratePathAvailable() {
  const recovered = await resolveThinkerPollErrorState(
    'job-running',
    async jobId => ({
      job_id: jobId,
      status: 'running',
      available_actions: []
    }),
    new Error('network flake')
  )

  assert.deepEqual(
    deriveScenarioThinkerPollRecoveryState(recovered),
    {
      status: 'error',
      errorMessage: 'network flake。当前无法继续轮询，请重新生成。',
      shouldClearDraft: false
    },
    'a recovered non-terminal scenario polling failure should surface a recoverable error state instead of trapping the UI in running'
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
  await testScenarioFlowContractFromReadyDraftToPendingUpload()
  await testScenarioPendingUploadRejectsMalformedMaterializedPayload()
  await testScenarioPollRecoveryLeavesRegeneratePathAvailable()
  await testShouldPreservePolymarketThinkerSession()
  await testNormalizeThinkerAvailableActions()
  await testResolveThinkerPollErrorStateKeepsTransportFailureSeparate()
  await testResolveThinkerPollErrorStateUsesServerActionsForTerminalFailure()
  clearPendingUpload()
  console.log('thinker smoke check passed')
}

await main()
