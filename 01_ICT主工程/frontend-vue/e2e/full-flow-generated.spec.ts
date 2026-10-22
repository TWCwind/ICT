import { expect, test, type Page } from '@playwright/test'

const viewports = [
  { label: '1440x900', width: 1440, height: 900 },
  { label: '1280x720', width: 1280, height: 720 },
  { label: '1024x768', width: 1024, height: 768 },
  { label: '768x1024', width: 768, height: 1024 },
  { label: '390x844', width: 390, height: 844 },
]

const pages = [
  ['home', '/', /为每一位学生|个性化学习资源|路演/],
  ['exercise', '/exercise', /练习诊断|Practice Center/],
  ['knowledge', '/knowledge', /知识中枢|知识图谱/],
  ['workshop', '/workshop', /资源工坊/],
  ['path', '/path', /路径推送|学习路径/],
  ['evaluate', '/evaluate', /评估进化|学习效果评估/],
] as const

async function enterDemo(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem('las_student_id', 'demo'))
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  const loginButton = page.getByRole('button', { name: /登录并进入系统/ })
  if (await loginButton.isVisible().catch(() => false)) {
    await page.getByPlaceholder('手机号').fill('10000000000')
    await page.getByPlaceholder('密码').fill('demo123')
    await page.getByPlaceholder('验证码').fill('2VV3')
    await loginButton.click()
  }
  await expect(page.locator('.login-gate')).toBeHidden({ timeout: 15_000 })
}

async function visit(page: Page, route: string, heading: RegExp) {
  await page.goto(route, { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined)
  await expect(page.locator('#app')).toBeVisible()
  await expect(page.locator('body')).toContainText(heading, { timeout: 15_000 })
  await expect(page.locator('body')).not.toContainText('undefined')
  await expect(page.locator('body')).not.toContainText('null')
  await expect(page.locator('body')).not.toContainText('Cannot read properties')
}

test.describe.configure({ mode: 'serial' })

test('generated dataset powers all roadshow review pages at five viewport sizes', async ({ page }) => {
  const consoleErrors: string[] = []
  const badResponses: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && !/favicon|ResizeObserver loop/i.test(message.text())) consoleErrors.push(message.text())
  })
  page.on('response', (response) => {
    if (response.url().includes('/api/') && response.status() >= 500) badResponses.push(`${response.status()} ${response.url()}`)
  })
  await enterDemo(page)

  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    for (const [slug, route, heading] of pages) {
      await visit(page, route, heading)
      await page.screenshot({
        path: `test-results/generated-flow/${viewport.label}/${slug}.png`,
        fullPage: true,
        animations: 'disabled',
      })
    }
  }
  expect(consoleErrors, `console errors:\n${consoleErrors.join('\n')}`).toEqual([])
  expect(badResponses, `bad API responses:\n${badResponses.join('\n')}`).toEqual([])
})

test('generated course statistics and final resource remain usable', async ({ page }) => {
  await enterDemo(page)
  await visit(page, '/knowledge', /知识中枢|知识图谱/)
  await expect(page.locator('.course-stat-row')).toContainText('6')
  await expect(page.locator('.course-stat-row')).toContainText('30')
  const detailPanel = page.locator('.course-detail-panel')
  const resourceButtons = detailPanel.locator('.resource-links button')
  await expect(resourceButtons).toHaveCount(3)
  const detailBox = await detailPanel.boundingBox()
  const actionBox = await detailPanel.locator('.detail-actions').boundingBox()
  expect(detailBox).not.toBeNull()
  expect(actionBox).not.toBeNull()
  for (let index = 0; index < 3; index += 1) {
    const resourceBox = await resourceButtons.nth(index).boundingBox()
    expect(resourceBox).not.toBeNull()
    expect(resourceBox!.y + resourceBox!.height).toBeLessThanOrEqual(actionBox!.y + 1)
    expect(resourceBox!.y + resourceBox!.height).toBeLessThanOrEqual(detailBox!.y + detailBox!.height + 1)
  }
  await expect(page.getByRole('button', { name: '业务场景与范围，章节模块' })).toBeVisible()
  await expect(page.getByRole('button', { name: '验证与变更，章节模块' })).toBeVisible()
  await page.getByRole('button', { name: '验证与变更，章节模块' }).click()
  await expect(page.locator('[aria-selected="true"]')).toContainText('验证与变更')
  await page.getByRole('button', { name: '适配图谱到窗口' }).click()

  await visit(page, '/exercise', /练习诊断|Practice Center/)
  await page.getByRole('button', { name: /错题本/ }).first().click()
  await expect(page.locator('body')).toContainText(/当前无待复盘错题|错题本|错题标签星系/)
})
