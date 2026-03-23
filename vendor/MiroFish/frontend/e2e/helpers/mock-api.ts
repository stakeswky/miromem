import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { expect, type Locator, type Page } from '@playwright/test'

type JsonValue = Record<string, unknown>

function readFixture(name: string): JsonValue {
  const path = resolve(process.cwd(), 'e2e', 'fixtures', name)
  return JSON.parse(readFileSync(path, 'utf8')) as JsonValue
}

const graphData = readFixture('graph-data.json')
const project = readFixture('project.json')
const profilesRealtime = readFixture('profiles-realtime.json')
const configRealtime = readFixture('config-realtime.json')
const prepareStatusSequence = readFixture('prepare-status.json') as JsonValue[]

async function fulfillJson(route: any, body: JsonValue) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

function sequence<T>(items: T[]) {
  let index = 0
  return () => {
    const current = items[Math.min(index, items.length - 1)]
    index += 1
    return current
  }
}

export function installPageGuards(page: Page) {
  page.on('pageerror', (error) => {
    throw error
  })

  page.on('console', (message) => {
    if (message.type() === 'error') {
      throw new Error(`Console error: ${message.text()}`)
    }
  })

  page.on('response', async (response) => {
    if (response.status() >= 500) {
      throw new Error(`HTTP ${response.status()} for ${response.url()}`)
    }
  })
}

export async function mockProcessGraphCompleted(page: Page) {
  await mockSimulationSetupBase(page)

  await page.route('**/api/graph/project/proj-test-001', async (route) => {
    await fulfillJson(route, project as JsonValue)
  })

  await page.route('**/api/graph/data/graph-test-001', async (route) => {
    await fulfillJson(route, graphData as JsonValue)
  })

  await page.route('**/api/simulation/create', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        simulation_id: 'sim-test-001',
        project_id: 'proj-test-001',
        graph_id: 'graph-test-001',
        status: 'created',
        enable_twitter: true,
        enable_reddit: true,
      },
    })
  })

  await page.route('**/api/simulation/prepare', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        simulation_id: 'sim-test-001',
        task_id: 'task-test-001',
        status: 'preparing',
        expected_entities_count: 2,
        entity_types: ['Student', 'Official'],
      },
    })
  })

  await page.route('**/api/simulation/prepare/status', async (route) => {
    await fulfillJson(route, prepareStatusSequence[0])
  })

  await page.route('**/api/simulation/sim-test-001/profiles/realtime**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        total_expected: 2,
        profiles: [],
      },
    })
  })

  await page.route('**/api/simulation/sim-test-001/config/realtime', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        simulation_id: 'sim-test-001',
        file_exists: false,
        is_generating: true,
        generation_stage: 'generating_profiles',
        config_generated: false,
        config: null,
      },
    })
  })
}

export async function mockSimulationSetupBase(page: Page) {
  await page.route('**/api/simulation/env-status', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        env_alive: false,
      },
    })
  })

  await page.route('**/api/simulation/sim-test-001', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        simulation_id: 'sim-test-001',
        project_id: 'proj-test-001',
        graph_id: 'graph-test-001',
        status: 'created',
      },
    })
  })
}

export async function mockSimulationSetupHappyPath(page: Page) {
  await mockSimulationSetupBase(page)

  await page.route('**/api/graph/project/proj-test-001', async (route) => {
    await fulfillJson(route, project as JsonValue)
  })

  await page.route('**/api/graph/data/graph-test-001', async (route) => {
    await fulfillJson(route, graphData as JsonValue)
  })

  await page.route('**/api/simulation/prepare', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        simulation_id: 'sim-test-001',
        task_id: 'task-test-001',
        status: 'preparing',
        expected_entities_count: 2,
        entity_types: ['Student', 'Official'],
      },
    })
  })

  const nextPrepareStatus = sequence(prepareStatusSequence)
  await page.route('**/api/simulation/prepare/status', async (route) => {
    await fulfillJson(route, nextPrepareStatus())
  })

  await page.route('**/api/simulation/sim-test-001/profiles/realtime**', async (route) => {
    await fulfillJson(route, profilesRealtime)
  })

  await page.route('**/api/simulation/sim-test-001/config/realtime', async (route) => {
    await fulfillJson(route, configRealtime)
  })
}

export async function mockSimulationSetupFailure(page: Page) {
  await mockSimulationSetupBase(page)

  await page.route('**/api/graph/project/proj-test-001', async (route) => {
    await fulfillJson(route, project as JsonValue)
  })

  await page.route('**/api/graph/data/graph-test-001', async (route) => {
    await fulfillJson(route, graphData as JsonValue)
  })

  await page.route('**/api/simulation/prepare', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        simulation_id: 'sim-test-001',
        task_id: 'task-test-001',
        status: 'preparing',
        expected_entities_count: 2,
        entity_types: ['Student', 'Official'],
      },
    })
  })

  await page.route('**/api/simulation/prepare/status', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        status: 'failed',
        progress: 72,
        error: "'float' object has no attribute 'get'",
      },
    })
  })

  await page.route('**/api/simulation/sim-test-001/profiles/realtime**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        total_expected: 2,
        profiles: [],
      },
    })
  })

  await page.route('**/api/simulation/sim-test-001/config/realtime', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        simulation_id: 'sim-test-001',
        file_exists: false,
        is_generating: true,
        generation_stage: 'generating_config',
        config_generated: false,
        config: null,
      },
    })
  })
}

export async function expectEventuallyEnabled(locator: Locator) {
  await expect(locator).toBeVisible()
  await expect(locator).toBeEnabled()
}
