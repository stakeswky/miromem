<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand">MIROFISH</div>
      <div class="nav-links">
        <a href="https://github.com/666ghj/MiroFish" target="_blank" class="github-link">
          访问我们的Github主页 <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content">
      <!-- 上半部分：Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">简洁通用的群体智能引擎</span>
            <span class="version-text">/ v0.1-预览版</span>
          </div>

          <h1 class="main-title">
            上传任意报告<br>
            <span class="gradient-text">即刻推演未来</span>
          </h1>

          <div class="hero-desc">
            <p>
              即使只有一段文字，<span class="highlight-bold">MiroFish</span> 也能基于其中的现实种子，全自动生成与之对应的至多<span class="highlight-orange">百万级Agent</span>构成的平行世界。通过上帝视角注入变量，在复杂的群体交互中寻找动态环境下的<span class="highlight-code">"局部最优解"</span>
            </p>
            <p class="slogan-text">
              让未来在 Agent 群中预演，让决策在百战后胜出<span class="blinking-cursor">_</span>
            </p>
          </div>

          <div class="decoration-square"></div>
        </div>

        <div class="hero-right">
          <!-- Logo 区域 -->
          <div class="logo-container">
            <img src="../assets/logo/MiroFish_logo_left.jpeg" alt="MiroFish Logo" class="hero-logo" />
          </div>

          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- 下半部分：双栏布局 -->
      <section class="dashboard-section">
        <!-- 左栏：状态与步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> 系统状态
          </div>

          <h2 class="section-title">准备就绪</h2>
          <p class="section-desc">
            预测引擎待命中，可上传非结构化数据或选择 Polymarket 议题以初始化模拟序列
          </p>

          <!-- 数据指标卡片 -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">低成本</div>
              <div class="metric-label">常规模拟平均5$/次</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">高可用</div>
              <div class="metric-label">最多百万级Agent模拟</div>
            </div>
          </div>

          <!-- 项目模拟步骤介绍 -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> 工作流序列
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">图谱构建</div>
                  <div class="step-desc">现实种子提取 & 个体与群体记忆注入 & GraphRAG构建</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">环境搭建</div>
                  <div class="step-desc">实体关系抽取 & 人设生成 & 环境配置Agent注入仿真参数</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">开始模拟</div>
                  <div class="step-desc">双平台并行模拟 & 自动解析预测需求 & 动态更新时序记忆</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">报告生成</div>
                  <div class="step-desc">ReportAgent拥有丰富的工具集与模拟后环境进行深度交互</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">深度互动</div>
                  <div class="step-desc">与模拟世界中的任意一位进行对话 & 与ReportAgent进行对话</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：交互控制台 -->
        <div class="right-panel">
          <div class="console-box">
            <!-- Tab 切换 -->
            <div class="console-tabs">
              <button
                class="tab-btn"
                :class="{ active: activeTab === 'upload' }"
                @click="activeTab = 'upload'"
              >上传文档</button>
              <button
                class="tab-btn"
                :class="{ active: activeTab === 'polymarket' }"
                @click="activeTab = 'polymarket'; loadPolymarketEvents()"
              >Polymarket</button>
            </div>

            <!-- 上传文档 Tab -->
            <div v-if="activeTab === 'upload'">
              <!-- 上传区域 -->
              <div class="console-section">
                <div class="console-header">
                  <span class="console-label">01 / 现实种子</span>
                  <span class="console-meta">支持格式: PDF, MD, TXT</span>
                </div>

                <div
                  class="upload-zone"
                  :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                  @dragover.prevent="handleDragOver"
                  @dragleave.prevent="handleDragLeave"
                  @drop.prevent="handleDrop"
                  @click="triggerFileInput"
                >
                  <input
                    ref="fileInput"
                    type="file"
                    multiple
                    accept=".pdf,.md,.txt"
                    @change="handleFileSelect"
                    style="display: none"
                    :disabled="uploadInputsDisabled"
                  />

                  <div v-if="files.length === 0" class="upload-placeholder">
                    <div class="upload-icon">↑</div>
                    <div class="upload-title">拖拽文件上传</div>
                    <div class="upload-hint">或点击浏览文件系统</div>
                  </div>

                  <div v-else class="file-list">
                    <div v-for="(file, index) in files" :key="index" class="file-item">
                      <span class="file-icon">📄</span>
                      <span class="file-name">{{ file.name }}</span>
                      <button
                        @click.stop="removeFile(index)"
                        class="remove-btn"
                        :disabled="uploadInputsDisabled"
                      >×</button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 分割线 -->
              <div class="console-divider">
                <span>输入参数</span>
              </div>

              <!-- 输入区域 -->
              <div class="console-section">
                <div class="console-header">
                  <span class="console-label">>_ 02 / 模拟提示词</span>
                </div>
                <div class="input-wrapper">
                  <textarea
                    v-model="formData.simulationRequirement"
                    class="code-input"
                    placeholder="// 用自然语言输入模拟或预测需求（例.武大若发布撤销肖某处分的公告，会引发什么舆情走向）"
                    rows="6"
                    :disabled="uploadInputsDisabled"
                  ></textarea>
                  <div class="model-badge">引擎: MiroFish-V1.0</div>
                </div>
              </div>
            </div>

            <!-- Polymarket Tab -->
            <div v-if="activeTab === 'polymarket'">
              <div class="console-section">
                <div class="console-header">
                  <span class="console-label">Polymarket / 预测市场</span>
                  <span class="console-meta">选择议题进行模拟预测</span>
                </div>

                <!-- 搜索栏 -->
                <div class="pm-search-row">
                  <input
                    v-model="pmSearch"
                    class="pm-search-input"
                    placeholder="搜索议题..."
                    :disabled="polymarketInputsDisabled"
                    @keyup.enter="searchPolymarket"
                  />
                  <button
                    class="pm-search-btn"
                    :disabled="polymarketInputsDisabled"
                    @click="searchPolymarket"
                  >搜索</button>
                </div>

                <!-- 标签筛选 -->
                <div class="pm-tags">
                  <button
                    v-for="t in pmTags"
                    :key="t"
                    class="pm-tag"
                    :class="{ active: pmActiveTag === t }"
                    :disabled="polymarketInputsDisabled"
                    @click="filterByTag(t)"
                  >{{ t }}</button>
                </div>

                <!-- 事件列表 -->
                <div class="pm-events" v-if="!pmLoading">
                  <div
                    v-for="ev in pmEvents"
                    :key="ev.id"
                    class="pm-event-card"
                    :class="{ selected: selectedEvent && selectedEvent.id === ev.id }"
                    @click="selectEvent(ev)"
                  >
                    <div class="pm-event-header">
                      <div class="pm-event-title">{{ ev.title }}</div>
                      <div class="pm-event-vol">${{ formatVolume(ev.volume24hr) }} / 24h</div>
                    </div>
                    <div class="pm-event-desc">{{ truncate(ev.description, 120) }}</div>
                    <div class="pm-markets" v-if="ev.markets && ev.markets.length">
                      <div v-for="(m, mi) in ev.markets.slice(0, 3)" :key="mi" class="pm-market">
                        <span class="pm-market-q">{{ truncate(m.question, 60) }}</span>
                        <span class="pm-market-odds" v-if="m.outcomePrices">
                          {{ formatOdds(m.outcomes, m.outcomePrices) }}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div v-if="pmEvents.length === 0" class="pm-empty">暂无结果</div>
                </div>
                <div v-else class="pm-loading">加载中...</div>
              </div>

              <!-- 选中事件后的模拟提示词 -->
              <div v-if="selectedEvent" class="console-section">
                <div class="console-divider"><span>模拟参数</span></div>
                <div class="console-header">
                  <span class="console-label">>_ 模拟提示词（可编辑）</span>
                </div>
                <div class="input-wrapper">
                  <textarea
                    v-model="formData.simulationRequirement"
                    class="code-input"
                    rows="4"
                    :disabled="polymarketInputsDisabled"
                  ></textarea>
                  <div class="model-badge">引擎: MiroFish-V1.0</div>
                </div>
              </div>
            </div>

            <div
              v-if="activeTab === 'upload' || activeTab === 'polymarket'"
              class="console-section thinker-section"
            >
              <div class="console-divider"><span>Thinker</span></div>

              <label class="thinker-toggle">
                <input
                  v-model="thinkerEnabled"
                  type="checkbox"
                  :disabled="loading"
                  @change="handleThinkerToggleChange"
                >
                <span class="thinker-toggle-text">
                  <strong>启用 Thinker 预处理</strong>
                  <span>{{ thinkerToggleDescription }}</span>
                </span>
              </label>

              <div v-if="thinkerEnabled" class="thinker-panel">
                <div class="thinker-status-row">
                  <span class="thinker-status-label">状态</span>
                  <span
                    class="thinker-status-badge"
                    :class="`status-${thinkerStatus || 'idle'}`"
                  >
                    {{ formatThinkerStatus(thinkerStatus) }}
                  </span>
                </div>

                <p
                  v-if="thinkerHasJobOnAnotherTab || !thinkerJobId"
                  class="thinker-help"
                >
                  {{ thinkerIdleHelpText }}
                </p>

                <p
                  v-else-if="thinkerStatus === 'created' || thinkerStatus === 'running'"
                  class="thinker-help"
                >
                  {{ thinkerRunningHelpText }}
                </p>

                <div v-if="thinkerError" class="thinker-error">
                  {{ thinkerError }}
                </div>

                <div
                  v-if="thinkerStatus === 'succeeded' && thinkerJobMode === activeTab"
                  class="thinker-draft"
                >
                  <div class="thinker-field">
                    <label for="thinker-topics">扩展议题</label>
                    <textarea
                      id="thinker-topics"
                      v-model="thinkerExpandedTopicsText"
                      class="thinker-input"
                      rows="3"
                      :disabled="loading"
                    ></textarea>
                  </div>

                  <div class="thinker-field">
                    <label for="thinker-seed">增强现实种子</label>
                    <textarea
                      id="thinker-seed"
                      v-model="thinkerResultDraft.enrichedSeedText"
                      class="thinker-input"
                      rows="8"
                      :disabled="loading"
                    ></textarea>
                  </div>

                  <div class="thinker-field">
                    <label for="thinker-prompt">建议模拟提示词</label>
                    <textarea
                      id="thinker-prompt"
                      v-model="thinkerResultDraft.suggestedSimulationPrompt"
                      class="thinker-input"
                      rows="5"
                      :disabled="loading"
                    ></textarea>
                  </div>

                  <div class="thinker-actions">
                    <button
                      class="thinker-primary-btn"
                      @click="adoptThinkerResult"
                      :disabled="loading"
                    >
                      采用 Thinker 结果
                    </button>
                    <button
                      v-if="canSkipThinkerAction"
                      class="thinker-secondary-btn"
                      @click="skipThinkerFlow"
                      :disabled="loading"
                    >
                      跳过 Thinker
                    </button>
                  </div>
                </div>

                <div
                  v-else-if="
                    thinkerStatus === 'failed' &&
                    thinkerJobMode === activeTab &&
                    (canRetryThinkerAction || canSkipThinkerAction)
                  "
                  class="thinker-actions"
                >
                  <button
                    v-if="canRetryThinkerAction"
                    class="thinker-primary-btn"
                    @click="retryThinkerFlow"
                    :disabled="loading || !thinkerJobId || !canRetryThinkerAction"
                  >
                    重试 Thinker
                  </button>
                  <button
                    v-if="canSkipThinkerAction"
                    class="thinker-secondary-btn"
                    @click="skipThinkerFlow"
                    :disabled="loading || !thinkerJobId || !canSkipThinkerAction"
                  >
                    跳过 Thinker
                  </button>
                </div>
              </div>
            </div>

            <!-- 启动按钮 -->
            <div class="console-section btn-section">
              <button
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span>{{ startButtonLabel }}</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 历史项目数据库 -->
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import { getPolymarketEvents } from '../api/polymarket'
import {
  createThinkerJob,
  getThinkerJob,
  materializeThinkerJob,
  retryThinkerJob,
  skipThinkerJob
} from '../api/thinker'
import { setPendingUpload } from '../store/pendingUpload.js'
import {
  buildThinkerJobPayload,
  buildThinkerMaterializePayload,
  buildThinkerPendingUploadPayload,
  extractThinkerErrorMessage,
  hydrateThinkerDraft,
  normalizeThinkerAvailableActions,
  normalizeThinkerJobState,
  pollThinkerJobUntilTerminal,
  resolveThinkerPollErrorState
} from '../utils/thinker'

const router = useRouter()

// Tab 状态
const activeTab = ref('upload')

// 表单数据
const formData = ref({
  simulationRequirement: ''
})

// 文件列表
const files = ref([])

// 状态
const loading = ref(false)
const isDragOver = ref(false)

// 文件输入引用
const fileInput = ref(null)

// === Polymarket 状态 ===
const pmSearch = ref('')
const pmActiveTag = ref('')
const pmEvents = ref([])
const pmLoading = ref(false)
const selectedEvent = ref(null)
const pmTags = ['All', 'Crypto', 'Politics', 'Sports', 'Pop Culture', 'Science']

const createEmptyThinkerDraft = () => ({
  expandedTopics: [],
  enrichedSeedText: '',
  suggestedSimulationPrompt: ''
})

const createEmptyThinkerSnapshot = () => ({
  mode: '',
  files: [],
  simulationRequirement: '',
  polymarketEvent: null
})

const thinkerEnabled = ref(false)
const thinkerJobId = ref('')
const thinkerJobMode = ref('')
const thinkerStatus = ref('')
const thinkerResultDraft = ref(createEmptyThinkerDraft())
const thinkerError = ref('')
const thinkerAvailableActions = ref([])
const thinkerInputSnapshot = ref(createEmptyThinkerSnapshot())

const thinkerHasJobOnAnotherTab = computed(() => (
  thinkerEnabled.value &&
  thinkerJobId.value !== '' &&
  thinkerJobMode.value !== '' &&
  thinkerJobMode.value !== activeTab.value
))

// 计算属性:是否可以提交
const canSubmit = computed(() => {
  const simulationRequirement = formData.value.simulationRequirement.trim()

  if (activeTab.value === 'upload') {
    if (simulationRequirement === '' || files.value.length === 0) {
      return false
    }
  } else if (!selectedEvent.value || simulationRequirement === '') {
    return false
  }

  if (thinkerEnabled.value) {
    return thinkerJobId.value === ''
  }

  return true
})

const uploadInputsDisabled = computed(() => (
  activeTab.value === 'upload' &&
  (loading.value || (thinkerEnabled.value && thinkerJobId.value !== ''))
))

const polymarketInputsDisabled = computed(() => (
  activeTab.value === 'polymarket' &&
  (loading.value || (thinkerEnabled.value && thinkerJobId.value !== ''))
))

const canRetryThinkerAction = computed(() => (
  thinkerAvailableActions.value.includes('retry')
))

const canSkipThinkerAction = computed(() => (
  thinkerAvailableActions.value.includes('skip')
))

const thinkerToggleDescription = computed(() => (
  activeTab.value === 'polymarket'
    ? '先扩展当前议题并生成可编辑模拟草稿，再决定是否进入原有模拟流程。'
    : '先扩展议题并补全文档种子，再决定是否进入原有模拟流程。'
))

const thinkerExpandedTopicsText = computed({
  get: () => thinkerResultDraft.value.expandedTopics.join('\n'),
  set: value => {
    thinkerResultDraft.value = {
      ...thinkerResultDraft.value,
      expandedTopics: value
        .split(/\r?\n|,/)
        .map(topic => topic.trim())
        .filter(Boolean)
    }
  }
})

const thinkerIdleHelpText = computed(() => {
  if (thinkerHasJobOnAnotherTab.value) {
    return thinkerJobMode.value === 'polymarket'
      ? '当前 Polymarket 标签已有一个 Thinker 任务，请切回对应标签继续处理。'
      : '当前上传标签已有一个 Thinker 任务，请切回对应标签继续处理。'
  }

  if (activeTab.value === 'polymarket' && !selectedEvent.value) {
    return '请先选择一个 Polymarket 议题，再启动 Thinker。'
  }

  return activeTab.value === 'polymarket'
    ? 'Thinker 会基于当前 Polymarket 议题和模拟提示词生成一份可编辑草稿，确认后再继续。'
    : 'Thinker 会基于当前上传文件和模拟提示词生成一份可编辑草稿，确认后再继续。'
})

const thinkerRunningHelpText = computed(() => (
  activeTab.value === 'polymarket'
    ? 'Thinker 正在分析选中的 Polymarket 议题，请等待任务完成。'
    : 'Thinker 正在分析上传内容，请等待任务完成。'
))

const startButtonLabel = computed(() => {
  if (loading.value) {
    return thinkerEnabled.value
      ? 'Thinker 处理中...'
      : '初始化中...'
  }

  if (thinkerHasJobOnAnotherTab.value) {
    return '请先完成当前 Thinker 任务'
  }

  if (thinkerEnabled.value && thinkerJobId.value && thinkerJobMode.value === activeTab.value) {
    if (thinkerStatus.value === 'created' || thinkerStatus.value === 'running') {
      return '等待 Thinker 完成'
    }
    if (thinkerStatus.value === 'succeeded') {
      return '等待采用 Thinker 结果'
    }
    if (thinkerStatus.value === 'failed') {
      return canRetryThinkerAction.value || canSkipThinkerAction.value
        ? '请重试或跳过 Thinker'
        : 'Thinker 已结束'
    }
  }

  return '启动引擎'
})

// 触发文件选择
const triggerFileInput = () => {
  if (!uploadInputsDisabled.value) {
    fileInput.value?.click()
  }
}

// 处理文件选择
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 处理拖拽相关
const handleDragOver = (e) => {
  if (!uploadInputsDisabled.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (uploadInputsDisabled.value) return
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// 添加文件
const addFiles = (newFiles) => {
  if (uploadInputsDisabled.value) return
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// 移除文件
const removeFile = (index) => {
  if (uploadInputsDisabled.value) return
  files.value.splice(index, 1)
}

// 滚动到底部
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// === Polymarket 方法 ===
const loadPolymarketEvents = async () => {
  if (pmEvents.value.length > 0 && !pmSearch.value && !pmActiveTag.value) return
  pmLoading.value = true
  try {
    const params = { limit: 20 }
    if (pmActiveTag.value && pmActiveTag.value !== 'All') {
      params.tag = pmActiveTag.value.toLowerCase()
    }
    if (pmSearch.value) {
      params.search = pmSearch.value
    }
    const res = await getPolymarketEvents(params)
    pmEvents.value = res.data || []
  } catch (e) {
    console.error('Failed to load Polymarket events:', e)
    pmEvents.value = []
  } finally {
    pmLoading.value = false
  }
}

const searchPolymarket = () => {
  pmActiveTag.value = ''
  pmEvents.value = []
  loadPolymarketEvents()
}

const filterByTag = (tag) => {
  pmActiveTag.value = tag
  pmSearch.value = ''
  pmEvents.value = []
  loadPolymarketEvents()
}

const selectEvent = (ev) => {
  if (polymarketInputsDisabled.value) return

  selectedEvent.value = ev
  // 自动生成模拟提示词
  let prompt = `预测以下 Polymarket 议题的走向：\n\n${ev.title}\n\n`
  if (ev.markets && ev.markets.length) {
    prompt += '当前市场数据：\n'
    ev.markets.forEach(m => {
      prompt += `- ${m.question}`
      if (m.outcomePrices) {
        prompt += ` (${formatOdds(m.outcomes, m.outcomePrices)})`
      }
      prompt += '\n'
    })
  }
  prompt += '\n请分析各种可能的结果及其概率，并给出预测建议。'
  formData.value.simulationRequirement = prompt
}

const formatVolume = (v) => {
  const num = parseFloat(v) || 0
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toFixed(0)
}

const formatOdds = (outcomes, prices) => {
  try {
    const outs = typeof outcomes === 'string' ? JSON.parse(outcomes) : outcomes
    const prs = typeof prices === 'string' ? JSON.parse(prices) : prices
    if (!outs || !prs) return ''
    return outs.map((o, i) => `${o}: ${(parseFloat(prs[i]) * 100).toFixed(0)}%`).join(' / ')
  } catch { return '' }
}

const truncate = (s, n) => {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '...' : s
}

const formatThinkerStatus = (status) => {
  const statusText = {
    '': '待启动',
    created: '已创建',
    running: '分析中',
    succeeded: '可采用',
    failed: '失败',
    skipped: '已跳过',
    materialized: '已采用'
  }

  return statusText[status] || status || '待启动'
}

const clonePolymarketEvent = (event) => {
  if (!event || Array.isArray(event) || typeof event !== 'object') {
    return null
  }

  return {
    ...event,
    markets: Array.isArray(event.markets)
      ? event.markets.map(market => ({ ...market }))
      : event.markets
  }
}

const getCurrentThinkerSnapshot = () => {
  if (activeTab.value === 'polymarket') {
    return {
      mode: 'polymarket',
      files: [],
      simulationRequirement: formData.value.simulationRequirement,
      polymarketEvent: clonePolymarketEvent(selectedEvent.value)
    }
  }

  return {
    mode: 'upload',
    files: [...files.value],
    simulationRequirement: formData.value.simulationRequirement,
    polymarketEvent: null
  }
}

const getThinkerSnapshot = () => {
  if (thinkerInputSnapshot.value.mode) {
    return {
      mode: thinkerInputSnapshot.value.mode,
      files: [...thinkerInputSnapshot.value.files],
      simulationRequirement: thinkerInputSnapshot.value.simulationRequirement,
      polymarketEvent: clonePolymarketEvent(thinkerInputSnapshot.value.polymarketEvent)
    }
  }

  return getCurrentThinkerSnapshot()
}

const resetThinkerState = () => {
  thinkerJobId.value = ''
  thinkerJobMode.value = ''
  thinkerStatus.value = ''
  thinkerResultDraft.value = createEmptyThinkerDraft()
  thinkerError.value = ''
  thinkerAvailableActions.value = []
  thinkerInputSnapshot.value = createEmptyThinkerSnapshot()
}

const handleThinkerToggleChange = () => {
  if (!thinkerEnabled.value) {
    resetThinkerState()
  }
}

const applyThinkerJobState = (job, options = {}) => {
  const state = normalizeThinkerJobState(job)

  thinkerStatus.value = state.status
  thinkerAvailableActions.value = state.availableActions

  if (state.status === 'succeeded') {
    thinkerResultDraft.value = hydrateThinkerDraft(job?.result)
    if (!options.preserveError) {
      thinkerError.value = ''
    }
    return
  }

  thinkerResultDraft.value = createEmptyThinkerDraft()

  if (state.status === 'failed') {
    thinkerError.value = state.errorMessage || 'Thinker 分析失败'
    return
  }

  if (!options.preserveError) {
    thinkerError.value = ''
  }
}

const pollThinkerJob = async (jobId) => {
  try {
    const terminalJob = await pollThinkerJobUntilTerminal(jobId, getThinkerJob, {
      onUpdate: job => {
        const state = normalizeThinkerJobState(job)
        thinkerStatus.value = state.status || thinkerStatus.value
        thinkerAvailableActions.value = state.availableActions
      }
    })

    applyThinkerJobState(terminalJob)
    return terminalJob
  } catch (err) {
    const recoveredState = await resolveThinkerPollErrorState(jobId, getThinkerJob, err)

    if (recoveredState.job) {
      applyThinkerJobState(recoveredState.job, {
        preserveError: !recoveredState.isTerminal
      })

      if (!recoveredState.isTerminal) {
        thinkerError.value = recoveredState.errorMessage
      }

      return recoveredState.job
    }

    thinkerAvailableActions.value = []
    thinkerError.value = recoveredState.errorMessage
    return null
  }
}

const pushPendingUploadToProcess = (filesOrPayload, requirement = '') => {
  setPendingUpload(filesOrPayload, requirement)
  router.push({ name: 'Process', params: { projectId: 'new' } })
}

const startThinkerFlow = async () => {
  thinkerError.value = ''
  thinkerResultDraft.value = createEmptyThinkerDraft()
  thinkerAvailableActions.value = []
  thinkerInputSnapshot.value = getCurrentThinkerSnapshot()
  thinkerJobMode.value = thinkerInputSnapshot.value.mode

  const payload = buildThinkerJobPayload({
    mode: thinkerInputSnapshot.value.mode,
    researchDirection: thinkerInputSnapshot.value.simulationRequirement,
    files: thinkerInputSnapshot.value.files,
    polymarketEvent: thinkerInputSnapshot.value.polymarketEvent
  })

  loading.value = true

  try {
    const job = await createThinkerJob(payload)
    thinkerJobId.value = job?.job_id || ''
    if (!thinkerJobId.value) {
      thinkerStatus.value = ''
      thinkerAvailableActions.value = normalizeThinkerAvailableActions(job?.available_actions)
      thinkerError.value = 'Thinker job 创建失败: 缺少 job_id'
      return
    }
    applyThinkerJobState(job)
    await pollThinkerJob(thinkerJobId.value)
  } catch (err) {
    thinkerStatus.value = ''
    thinkerAvailableActions.value = []
    thinkerError.value = extractThinkerErrorMessage(err, 'Thinker 任务创建失败')
  } finally {
    loading.value = false
  }
}

const adoptThinkerResult = async () => {
  if (!thinkerJobId.value) return

  loading.value = true
  thinkerError.value = ''

  try {
    const response = await materializeThinkerJob(
      buildThinkerMaterializePayload(thinkerJobId.value, thinkerResultDraft.value)
    )

    thinkerStatus.value = response?.status || 'materialized'

    const snapshot = getThinkerSnapshot()
    const pendingPayload = buildThinkerPendingUploadPayload(response?.payload, {
      baseFiles: snapshot.mode === 'upload' ? snapshot.files : []
    })

    pushPendingUploadToProcess(pendingPayload)
  } catch (err) {
    thinkerError.value = extractThinkerErrorMessage(err, 'Thinker 结果采用失败')
  } finally {
    loading.value = false
  }
}

const retryThinkerFlow = async () => {
  if (!thinkerJobId.value || !canRetryThinkerAction.value) return

  loading.value = true
  thinkerError.value = ''
  thinkerResultDraft.value = createEmptyThinkerDraft()

  try {
    const job = await retryThinkerJob(thinkerJobId.value)
    thinkerJobId.value = job?.job_id || thinkerJobId.value
    applyThinkerJobState(job)
    await pollThinkerJob(job?.job_id || thinkerJobId.value)
  } catch (err) {
    thinkerError.value = extractThinkerErrorMessage(err, 'Thinker 重试失败')
  } finally {
    loading.value = false
  }
}

const buildFallbackFilesFromThinkerSnapshot = (snapshot) => {
  if (snapshot.mode === 'polymarket' && snapshot.polymarketEvent) {
    return [buildPolymarketDoc(snapshot.polymarketEvent)]
  }

  return [...snapshot.files]
}

const skipThinkerFlow = async () => {
  if (thinkerJobId.value && !canSkipThinkerAction.value) return

  loading.value = true
  thinkerError.value = ''

  try {
    if (thinkerJobId.value) {
      const job = await skipThinkerJob(thinkerJobId.value)
      applyThinkerJobState(job)
    }

    const snapshot = getThinkerSnapshot()
    pushPendingUploadToProcess(
      buildFallbackFilesFromThinkerSnapshot(snapshot),
      snapshot.simulationRequirement
    )
  } catch (err) {
    thinkerError.value = extractThinkerErrorMessage(err, '跳过 Thinker 失败')
  } finally {
    loading.value = false
  }
}

// 生成 Polymarket 事件文档 Blob
const buildPolymarketDoc = (ev) => {
  let doc = `Polymarket Event: ${ev.title}\n\n`
  doc += `Description:\n${ev.description || 'N/A'}\n\n`
  doc += `Liquidity: $${formatVolume(ev.liquidity)}\n`
  doc += `24h Volume: $${formatVolume(ev.volume24hr)}\n\n`
  if (ev.markets && ev.markets.length) {
    doc += 'Markets:\n'
    ev.markets.forEach(m => {
      doc += `\n  Question: ${m.question}\n`
      if (m.outcomePrices) {
        doc += `  Odds: ${formatOdds(m.outcomes, m.outcomePrices)}\n`
      }
    })
  }
  return new File([doc], `polymarket_${ev.id}.txt`, { type: 'text/plain' })
}

// 开始模拟
const startSimulation = async () => {
  if (!canSubmit.value || loading.value) return

  if (
    thinkerEnabled.value &&
    (activeTab.value === 'upload' || activeTab.value === 'polymarket')
  ) {
    await startThinkerFlow()
    return
  }

  let uploadFiles = files.value
  if (activeTab.value === 'polymarket' && selectedEvent.value) {
    uploadFiles = [buildPolymarketDoc(selectedEvent.value)]
  }

  pushPendingUploadToProcess(uploadFiles, formData.value.simulationRequirement)
}
</script>

<style scoped>
/* 全局变量与重置 */
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-cn: 'Noto Sans SC', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* 顶部导航 */
.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
}

.nav-links { display: flex; align-items: center; }

.github-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s;
}
.github-link:hover { opacity: 0.8; }
.arrow { font-family: sans-serif; }

/* 主要内容区 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
}

/* Hero 区域 */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 80px;
  position: relative;
}
.hero-left { flex: 1; padding-right: 60px; }

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
}
.version-text { color: #999; font-weight: 500; letter-spacing: 0.5px; }

.main-title {
  font-size: 4.5rem;
  line-height: 1.2;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -2px;
  color: var(--black);
}

.gradient-text {
  background: linear-gradient(90deg, #000000 0%, #444444 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
  font-weight: 400;
  text-align: justify;
}
.hero-desc p { margin-bottom: 1.5rem; }
.highlight-bold { color: var(--black); font-weight: 700; }
.highlight-orange { color: var(--orange); font-weight: 700; font-family: var(--font-mono); }
.highlight-code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--black);
  font-weight: 600;
}

.slogan-text {
  font-size: 1.2rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 1px;
  border-left: 3px solid var(--orange);
  padding-left: 15px;
  margin-top: 20px;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

.decoration-square { width: 16px; height: 16px; background: var(--orange); }

.hero-right {
  flex: 0.8;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
}
.logo-container { width: 100%; display: flex; justify-content: flex-end; padding-right: 40px; }
.hero-logo { max-width: 500px; width: 100%; }

.scroll-down-btn {
  width: 40px; height: 40px;
  border: 1px solid var(--border);
  background: transparent;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--orange); font-size: 1.2rem;
  transition: all 0.2s;
}
.scroll-down-btn:hover { border-color: var(--orange); }

/* Dashboard 双栏布局 */
.dashboard-section {
  display: flex; gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
  align-items: flex-start;
}
.dashboard-section .left-panel,
.dashboard-section .right-panel { display: flex; flex-direction: column; }

.left-panel { flex: 0.8; }

.panel-header {
  font-family: var(--font-mono); font-size: 0.8rem; color: #999;
  display: flex; align-items: center; gap: 8px; margin-bottom: 20px;
}
.status-dot { color: var(--orange); font-size: 0.8rem; }
.section-title { font-size: 2rem; font-weight: 520; margin: 0 0 15px 0; }
.section-desc { color: var(--gray-text); margin-bottom: 25px; line-height: 1.6; }

.metrics-row { display: flex; gap: 20px; margin-bottom: 15px; }
.metric-card { border: 1px solid var(--border); padding: 20px 30px; min-width: 150px; }
.metric-value { font-family: var(--font-mono); font-size: 1.8rem; font-weight: 520; margin-bottom: 5px; }
.metric-label { font-size: 0.85rem; color: #999; }

.steps-container { border: 1px solid var(--border); padding: 30px; position: relative; }
.steps-header {
  font-family: var(--font-mono); font-size: 0.8rem; color: #999;
  margin-bottom: 25px; display: flex; align-items: center; gap: 8px;
}
.diamond-icon { font-size: 1.2rem; line-height: 1; }
.workflow-list { display: flex; flex-direction: column; gap: 20px; }
.workflow-item { display: flex; align-items: flex-start; gap: 20px; }
.step-num { font-family: var(--font-mono); font-weight: 700; color: var(--black); opacity: 0.3; }
.step-info { flex: 1; }
.step-title { font-weight: 520; font-size: 1rem; margin-bottom: 4px; }
.step-desc { font-size: 0.85rem; color: var(--gray-text); }

/* 右侧交互控制台 */
.right-panel { flex: 1.2; }
.console-box { border: 1px solid #CCC; padding: 8px; }
.console-section { padding: 20px; }
.console-section.btn-section { padding-top: 0; }
.console-header {
  display: flex; justify-content: space-between; margin-bottom: 15px;
  font-family: var(--font-mono); font-size: 0.75rem; color: #666;
}

/* Tab 切换 */
.console-tabs {
  display: flex; border-bottom: 1px solid #EEE; margin-bottom: 0;
}
.tab-btn {
  flex: 1; padding: 14px 20px;
  background: transparent; border: none; border-bottom: 2px solid transparent;
  font-family: var(--font-mono); font-size: 0.85rem; font-weight: 600;
  color: #999; cursor: pointer; transition: all 0.2s;
}
.tab-btn.active { color: var(--black); border-bottom-color: var(--orange); }
.tab-btn:hover:not(.active) { color: #666; }

/* 上传区域 */
.upload-zone {
  border: 1px dashed #CCC; height: 200px; overflow-y: auto;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all 0.3s; background: #FAFAFA;
}
.upload-zone.has-files { align-items: flex-start; }
.upload-zone:hover { background: #F0F0F0; border-color: #999; }
.upload-placeholder { text-align: center; }
.upload-icon {
  width: 40px; height: 40px; border: 1px solid #DDD;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 15px; color: #999;
}
.upload-title { font-weight: 500; font-size: 0.9rem; margin-bottom: 5px; }
.upload-hint { font-family: var(--font-mono); font-size: 0.75rem; color: #999; }

.file-list { width: 100%; padding: 15px; display: flex; flex-direction: column; gap: 10px; }
.file-item {
  display: flex; align-items: center; background: var(--white);
  padding: 8px 12px; border: 1px solid #EEE;
  font-family: var(--font-mono); font-size: 0.85rem;
}
.file-name { flex: 1; margin: 0 10px; }
.remove-btn { background: none; border: none; cursor: pointer; font-size: 1.2rem; color: #999; }
.remove-btn:disabled { cursor: not-allowed; opacity: 0.4; }

.console-divider { display: flex; align-items: center; margin: 10px 0; }
.console-divider::before, .console-divider::after { content: ''; flex: 1; height: 1px; background: #EEE; }
.console-divider span {
  padding: 0 15px; font-family: var(--font-mono);
  font-size: 0.7rem; color: #BBB; letter-spacing: 1px;
}

.input-wrapper { position: relative; border: 1px solid #DDD; background: #FAFAFA; }
.code-input {
  width: 100%; border: none; background: transparent; padding: 20px;
  font-family: var(--font-mono); font-size: 0.9rem; line-height: 1.6;
  resize: vertical; outline: none; min-height: 150px;
}
.code-input:disabled { color: #999; cursor: not-allowed; }
.model-badge {
  position: absolute; bottom: 10px; right: 15px;
  font-family: var(--font-mono); font-size: 0.7rem; color: #AAA;
}

.thinker-section { padding-top: 0; }
.thinker-toggle {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 16px; border: 1px solid #EEE; background: #FAFAFA;
  cursor: pointer;
}
.thinker-toggle input { margin-top: 4px; accent-color: var(--orange); }
.thinker-toggle-text {
  display: flex; flex-direction: column; gap: 4px;
  font-size: 0.85rem; color: #666; line-height: 1.5;
}
.thinker-toggle-text strong { color: var(--black); font-family: var(--font-mono); }
.thinker-panel {
  margin-top: 14px; border: 1px solid #EEE; background: var(--white);
  padding: 18px; display: flex; flex-direction: column; gap: 14px;
}
.thinker-status-row {
  display: flex; justify-content: space-between; align-items: center;
  gap: 12px;
}
.thinker-status-label {
  font-family: var(--font-mono); font-size: 0.75rem;
  color: #999; letter-spacing: 1px;
}
.thinker-status-badge {
  padding: 4px 10px; border: 1px solid #DDD; font-family: var(--font-mono);
  font-size: 0.72rem; letter-spacing: 0.5px; background: #FAFAFA; color: #666;
}
.thinker-status-badge.status-idle,
.thinker-status-badge.status-created { border-color: #DDD; color: #777; }
.thinker-status-badge.status-running { border-color: #999; color: #444; }
.thinker-status-badge.status-succeeded,
.thinker-status-badge.status-materialized {
  border-color: var(--orange); color: var(--orange); background: #FFF5F0;
}
.thinker-status-badge.status-failed { border-color: #D14343; color: #D14343; background: #FFF4F4; }
.thinker-status-badge.status-skipped { border-color: #BBB; color: #666; background: #F4F4F4; }
.thinker-help {
  margin: 0; font-size: 0.85rem; color: #666; line-height: 1.6;
}
.thinker-error {
  border: 1px solid #F0B7B7; background: #FFF4F4; color: #A33A3A;
  padding: 12px 14px; font-size: 0.82rem; line-height: 1.5;
}
.thinker-draft { display: flex; flex-direction: column; gap: 14px; }
.thinker-field { display: flex; flex-direction: column; gap: 8px; }
.thinker-field label {
  font-family: var(--font-mono); font-size: 0.75rem; color: #666; letter-spacing: 0.5px;
}
.thinker-input {
  width: 100%; border: 1px solid #DDD; background: #FAFAFA; padding: 14px 16px;
  font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.6;
  resize: vertical; outline: none; min-height: 88px;
}
.thinker-input:focus { border-color: var(--orange); }
.thinker-input:disabled { color: #999; cursor: not-allowed; }
.thinker-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.thinker-primary-btn,
.thinker-secondary-btn {
  border: 1px solid var(--black); padding: 10px 16px; font-family: var(--font-mono);
  font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.thinker-primary-btn { background: var(--black); color: var(--white); }
.thinker-primary-btn:hover:not(:disabled) { background: var(--orange); border-color: var(--orange); }
.thinker-secondary-btn { background: transparent; color: var(--black); }
.thinker-secondary-btn:hover:not(:disabled) { border-color: var(--orange); color: var(--orange); }
.thinker-primary-btn:disabled,
.thinker-secondary-btn:disabled {
  cursor: not-allowed; opacity: 0.5;
}

/* Polymarket 样式 */
.pm-search-row { display: flex; gap: 8px; margin-bottom: 12px; }
.pm-search-input {
  flex: 1; padding: 10px 14px; border: 1px solid #DDD; background: #FAFAFA;
  font-family: var(--font-mono); font-size: 0.85rem; outline: none;
}
.pm-search-input:focus { border-color: var(--orange); }
.pm-search-btn {
  padding: 10px 20px; background: var(--black); color: var(--white);
  border: none; font-family: var(--font-mono); font-size: 0.85rem;
  cursor: pointer; font-weight: 600;
}
.pm-search-btn:hover { background: var(--orange); }

.pm-tags { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.pm-tag {
  padding: 4px 12px; border: 1px solid #DDD; background: transparent;
  font-family: var(--font-mono); font-size: 0.7rem; cursor: pointer;
  transition: all 0.2s; color: #666;
}
.pm-tag.active { background: var(--black); color: var(--white); border-color: var(--black); }
.pm-tag:hover:not(.active) { border-color: #999; }

.pm-events { max-height: 420px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.pm-event-card {
  border: 1px solid #EEE; padding: 14px 16px; cursor: pointer;
  transition: all 0.2s; background: #FAFAFA;
}
.pm-event-card:hover { border-color: #999; background: #F5F5F5; }
.pm-event-card.selected { border-color: var(--orange); background: #FFF5F0; }

.pm-event-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px; }
.pm-event-title { font-weight: 600; font-size: 0.9rem; flex: 1; margin-right: 10px; }
.pm-event-vol {
  font-family: var(--font-mono); font-size: 0.7rem; color: var(--orange);
  white-space: nowrap; font-weight: 600;
}
.pm-event-desc { font-size: 0.8rem; color: var(--gray-text); margin-bottom: 8px; line-height: 1.5; }

.pm-markets { display: flex; flex-direction: column; gap: 4px; }
.pm-market {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 0.75rem; padding: 4px 8px; background: rgba(0,0,0,0.02); border-radius: 2px;
}
.pm-market-q { color: #444; flex: 1; margin-right: 8px; }
.pm-market-odds { font-family: var(--font-mono); color: var(--orange); font-weight: 600; white-space: nowrap; }

.pm-loading { text-align: center; padding: 40px; color: #999; font-family: var(--font-mono); font-size: 0.85rem; }
.pm-empty { text-align: center; padding: 40px; color: #999; font-size: 0.85rem; }

/* 启动按钮 */
.start-engine-btn {
  width: 100%; background: var(--black); color: var(--white); border: none;
  padding: 20px; font-family: var(--font-mono); font-weight: 700; font-size: 1.1rem;
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer; transition: all 0.3s ease; letter-spacing: 1px;
  position: relative; overflow: hidden;
}
.start-engine-btn:not(:disabled) {
  background: var(--black); border: 1px solid var(--black);
  animation: pulse-border 2s infinite;
}
.start-engine-btn:hover:not(:disabled) {
  background: var(--orange); border-color: var(--orange); transform: translateY(-2px);
}
.start-engine-btn:active:not(:disabled) { transform: translateY(0); }
.start-engine-btn:disabled {
  background: #E5E5E5; color: #999; cursor: not-allowed;
  transform: none; border: 1px solid #E5E5E5;
}

@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .dashboard-section { flex-direction: column; }
  .hero-section { flex-direction: column; }
  .hero-left { padding-right: 0; margin-bottom: 40px; }
  .hero-logo { max-width: 200px; margin-bottom: 20px; }
}
</style>
