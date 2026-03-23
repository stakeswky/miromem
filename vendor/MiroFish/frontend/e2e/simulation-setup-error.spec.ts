import { expect, test } from '@playwright/test'

import { installPageGuards, mockSimulationSetupFailure } from './helpers/mock-api'

test('simulation setup shows failure log when backend prepare fails', async ({ page }) => {
  installPageGuards(page)
  await mockSimulationSetupFailure(page)

  await page.goto('/simulation/sim-test-001')

  await expect(page.getByText("准备失败: 'float' object has no attribute 'get'")).toBeVisible()
  await expect(page.getByTestId('step2-config-ready')).toHaveCount(0)
  await expect(page.getByTestId('step2-next-step')).toBeDisabled()
})
