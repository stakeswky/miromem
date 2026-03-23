import { expect, test } from '@playwright/test'

import { expectEventuallyEnabled, installPageGuards, mockProcessGraphCompleted } from './helpers/mock-api'

test('process page loads completed graph state and enters environment setup', async ({ page }) => {
  installPageGuards(page)
  await mockProcessGraphCompleted(page)

  await page.goto('/process/proj-test-001')

  await expect(page.getByText('图谱构建', { exact: true })).toBeVisible()
  await expect(page.getByText('Alice')).toBeVisible()

  const createSimulation = page.getByTestId('step1-create-simulation')
  await expectEventuallyEnabled(createSimulation)
  await createSimulation.click()

  await expect(page).toHaveURL(/\/simulation\/sim-test-001$/)
})
