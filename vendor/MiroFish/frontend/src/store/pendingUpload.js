/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  finalTopics: [],
  finalSeedText: '',
  finalSimulationRequirement: '',
  isPending: false
})

const toStringValue = value => {
  if (typeof value === 'string') {
    return value
  }
  if (value == null) {
    return ''
  }
  return String(value)
}

const normalizeFiles = files => {
  if (!files) {
    return []
  }
  if (Array.isArray(files)) {
    return [...files]
  }
  return Array.from(files)
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

const isPendingUploadPayload = value => (
  value &&
  !Array.isArray(value) &&
  typeof value === 'object' &&
  (
    'files' in value ||
    'simulationRequirement' in value ||
    'finalTopics' in value ||
    'finalSeedText' in value ||
    'finalSimulationRequirement' in value
  )
)

const normalizePendingUpload = (filesOrPayload, requirement) => {
  if (isPendingUploadPayload(filesOrPayload)) {
    const files = normalizeFiles(filesOrPayload.files)
    const fallbackRequirement = toStringValue(filesOrPayload.simulationRequirement)
    const finalSimulationRequirement = toStringValue(
      filesOrPayload.finalSimulationRequirement ?? fallbackRequirement
    )

    return {
      files,
      simulationRequirement: finalSimulationRequirement || fallbackRequirement,
      finalTopics: normalizeTopics(filesOrPayload.finalTopics),
      finalSeedText: toStringValue(filesOrPayload.finalSeedText),
      finalSimulationRequirement: finalSimulationRequirement || fallbackRequirement,
      isPending: files.length > 0
    }
  }

  const files = normalizeFiles(filesOrPayload)
  const simulationRequirement = toStringValue(requirement)

  return {
    files,
    simulationRequirement,
    finalTopics: [],
    finalSeedText: '',
    finalSimulationRequirement: simulationRequirement,
    isPending: files.length > 0
  }
}

export function setPendingUpload(filesOrPayload, requirement = '') {
  const normalized = normalizePendingUpload(filesOrPayload, requirement)

  state.files = normalized.files
  state.simulationRequirement = normalized.simulationRequirement
  state.finalTopics = normalized.finalTopics
  state.finalSeedText = normalized.finalSeedText
  state.finalSimulationRequirement = normalized.finalSimulationRequirement
  state.isPending = normalized.isPending
}

export function getPendingUpload() {
  return {
    files: [...state.files],
    simulationRequirement: state.simulationRequirement,
    finalTopics: [...state.finalTopics],
    finalSeedText: state.finalSeedText,
    finalSimulationRequirement: state.finalSimulationRequirement,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.finalTopics = []
  state.finalSeedText = ''
  state.finalSimulationRequirement = ''
  state.isPending = false
}

export default state
