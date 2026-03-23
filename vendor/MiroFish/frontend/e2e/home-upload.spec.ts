import { expect, test } from '@playwright/test'

test('home upload flow exposes stable selectors and enables start after input', async ({ page }) => {
  await page.goto('/')

  const uploadZone = page.getByTestId('home-upload-zone')
  const promptInput = page.getByTestId('home-prompt-input')
  const startButton = page.getByTestId('home-start-engine')
  const fileInput = page.locator('input[type="file"]')

  await expect(uploadZone).toBeVisible()
  await expect(promptInput).toBeVisible()
  await expect(startButton).toBeDisabled()

  await fileInput.setInputFiles({
    name: 'seed.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('seed content', 'utf8'),
  })
  await promptInput.fill('测试模拟需求')

  await expect(startButton).toBeEnabled()
})
