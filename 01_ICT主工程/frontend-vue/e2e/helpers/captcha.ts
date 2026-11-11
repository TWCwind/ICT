import type { Page } from '@playwright/test'

export async function readCaptcha(page: Page): Promise<string> {
  const characters = await page.locator('.captcha-char').allTextContents()
  if (characters.length !== 4) throw new Error('Expected a visible four-character login code')
  return characters.join('')
}
