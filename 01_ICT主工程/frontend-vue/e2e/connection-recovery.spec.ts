import { expect, test } from '@playwright/test'

test('fresh login and actual navigation work without bypassing the login gate', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await page.getByPlaceholder('手机号').fill('10000000000')
  await page.getByPlaceholder('密码', { exact: true }).fill('demo123')
  await page.getByPlaceholder('验证码').fill('2VV3')
  await page.getByRole('button', { name: '登录并进入系统' }).click()
  await expect(page.locator('.login-gate')).toBeHidden()
  for (const [label, route] of [['资源工坊', '/workshop'], ['练习诊断', '/exercise'], ['知识中枢', '/knowledge'], ['用户画像', '/profile'], ['路径推送', '/path'], ['多模态实验室', '/multimodal'], ['智能辅导', '/tutor'], ['评估进化', '/evaluate']]) {
    await page.getByRole('link', { name: label, exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`${route}$`))
    await expect(page.locator('.portal-main')).not.toBeEmpty()
  }
  await page.getByRole('button', { name: '打开用户设置' }).click()
  await expect(page.getByRole('region', { name: '用户设置面板' })).toBeVisible()
  await page.getByRole('button', { name: '关闭用户设置' }).click()
  await expect(page.getByRole('region', { name: '用户设置面板' })).toBeHidden()
  expect(errors).toEqual([])
})

test('disconnected backend has a retry action and recovers against the real backend', async ({ page }) => {
  // Fault injection only: successful retry uses the actual local server.
  await page.route('**/api/health', route => route.abort('connectionrefused'))
  await page.goto('/')
  await expect(page.getByText('本地服务暂时未连接', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  const notice = page.getByRole('status', { name: '服务连接状态' })
  await expect(notice.getByRole('button', { name: '重新检查连接' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: 'test-results/connection-offline-mobile.png' })
  await page.unroute('**/api/health')
  await notice.getByRole('button', { name: '重新检查连接' }).click()
  await expect(page.getByText('服务已恢复连接', { exact: true })).toBeVisible()
  await notice.getByRole('button', { name: '刷新页面' }).click()
  await expect(notice).toBeHidden()
})
