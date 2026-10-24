import { expect, test } from '@playwright/test'

// 后端完全断开时，页面级 API 失败必须显示中文错误与重试入口，
// 且不得把 fetch/JSON 解析的英文底层错误暴露给用户。

// 只按路径名匹配 /api/ 开头的后端接口；不能用 '**/api/**' 这类 glob，
// 它会把 Vite 开发服务器的模块 URL（/src/api/learningApi.ts）一并中断，
// 导致页面 chunk 加载失败而非接口失败。
function isBackendApi(url: string): boolean {
  try {
    return new URL(url).pathname.startsWith('/api/')
  } catch {
    return false
  }
}

test('后端断开时资源工坊加载失败显示中文错误与重试入口', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('pageerror', (error) => consoleErrors.push(error.message))

  // 故障注入：所有后端接口按“后端进程不存在”处理
  await page.route(isBackendApi, (route) => route.abort('connectionrefused'))

  await page.addInitScript(() => sessionStorage.setItem('zx-resource-agent-authed', '1'))
  await page.goto('/workshop', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3500)

  // 页内错误条：中文说明 + 重试按钮
  const alert = page.locator('[role="alert"]').first()
  await expect(alert).toBeVisible()
  const alertText = (await alert.innerText()).replace(/\s+/g, ' ')
  expect(alertText, `页内错误应含中文说明，实际：${alertText}`).toContain('本地服务未连接')
  await expect(alert.getByRole('button', { name: /重新同步/ })).toBeVisible()

  // 顶部连接横幅：中文提示 + 重新检查连接
  const notice = page.getByRole('status', { name: '服务连接状态' })
  await expect(notice).toBeVisible()
  await expect(notice.getByRole('button', { name: /重新检查连接/ })).toBeVisible()

  // 全页不得出现英文底层错误
  const bodyText = (await page.locator('body').innerText()).replace(/\s+/g, ' ')
  for (const banned of ['Failed to fetch', 'Unexpected token', 'SyntaxError', 'undefined', 'NetworkError', 'Load failed']) {
    expect(bodyText, `页面出现英文底层错误「${banned}」`).not.toContain(banned)
  }

  // 恢复后端：重试应让页面回到可用状态
  await page.unroute(isBackendApi)
  await alert.getByRole('button', { name: /重新同步/ }).click()
  await expect(page.locator('[role="alert"]')).toHaveCount(0, { timeout: 20_000 })
})

test('后端断开时评估进化页同样显示中文错误而非英文异常', async ({ page }) => {
  await page.route(isBackendApi, (route) => route.abort('connectionrefused'))
  await page.addInitScript(() => sessionStorage.setItem('zx-resource-agent-authed', '1'))
  await page.goto('/evaluate', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3500)

  const bodyText = (await page.locator('body').innerText()).replace(/\s+/g, ' ')
  for (const banned of ['Failed to fetch', 'Unexpected token', 'SyntaxError', 'NetworkError', 'Load failed']) {
    expect(bodyText, `页面出现英文底层错误「${banned}」`).not.toContain(banned)
  }
  // 必须存在某种用户可读的失败提示（错误条或连接横幅）
  const hasErrorUi = await page.locator('[role="alert"], .connection-notice').first().isVisible()
  expect(hasErrorUi, '后端断开时页面上应存在错误提示或连接横幅').toBe(true)
})
