import assert from 'node:assert/strict'
import { File as NodeFile } from 'node:buffer'

if (typeof globalThis.File === 'undefined') {
  globalThis.File = NodeFile
}

const {
  buildThinkerSeedFile,
  normalizeThinkerMaterialized
} = await import('../src/utils/thinker.js')
const {
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

async function main() {
  await testExplicitEmptyPromptPreserved()
  await testNormalizeThenBuildSeedFileFlow()
  await testLegacyPendingUploadSignature()
  clearPendingUpload()
  console.log('thinker smoke check passed')
}

await main()
