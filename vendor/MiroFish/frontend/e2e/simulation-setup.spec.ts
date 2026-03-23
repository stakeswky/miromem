import { expect, test } from '@playwright/test'

import { installPageGuards, mockSimulationSetupHappyPath } from './helpers/mock-api'

test('simulation setup renders profiles and config after prepare completes', async ({ page }) => {
  installPageGuards(page)
  await mockSimulationSetupHappyPath(page)

  await page.goto('/simulation/sim-test-001')

  await expect(page.getByTestId('step2-profiles-preview')).toBeVisible()
  await expect(page.getByText('alice_123')).toBeVisible()
  await expect(page.getByTestId('step2-config-ready')).toBeVisible()
  await expect(page.getByText('Agent数量: 2个')).toBeVisible()
  await expect(page.getByTestId('step2-next-step')).toBeEnabled()
})
