import { expect, test } from '@playwright/test'
import { readCaptcha } from './helpers/captcha'

test('login code supports keyboard refresh, error feedback, and successful login', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.login-gate')).toBeVisible()

  const refresh = page.getByRole('button', { name: '刷新验证码' })
  await page.getByPlaceholder('验证码').focus()
  await page.keyboard.press('Tab')
  await expect(refresh).toBeFocused()
  const initialCode = await readCaptcha(page)
  await refresh.press('Enter')
  await expect(page.getByPlaceholder('验证码')).toBeEmpty()
  const refreshedCode = await readCaptcha(page)
  expect(refreshedCode).not.toBe(initialCode)
  await refresh.press('Space')
  expect(await readCaptcha(page)).not.toBe(refreshedCode)

  await page.getByPlaceholder('手机号').fill('10000000000')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByPlaceholder('验证码').fill('0000')
  await page.getByRole('button', { name: '登录并进入系统' }).click()
  await expect(page.getByText('验证码不正确，请输入新验证码')).toBeVisible()
  await expect(page.locator('.login-gate')).toBeVisible()

  await page.getByPlaceholder('验证码').fill(await readCaptcha(page))
  await page.getByRole('button', { name: '登录并进入系统' }).click()
  await expect(page.locator('.login-gate')).toBeHidden()
})
