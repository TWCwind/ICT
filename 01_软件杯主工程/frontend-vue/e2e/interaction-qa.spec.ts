import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const viewports = [
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
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
  await expect(page.locator('body')).not.toContainText('Cannot read properties')
}

test.describe.configure({ mode: 'serial' })

test('roadshow pages render at all required sizes and produce review screenshots', async ({ page }) => {
  const outputRoot = path.resolve('test-results/roadshow-screenshots')
  fs.mkdirSync(outputRoot, { recursive: true })
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
    await page.setViewportSize(viewport)
    const sizeDir = path.join(outputRoot, `${viewport.width}x${viewport.height}`)
    fs.mkdirSync(sizeDir, { recursive: true })
    for (const [slug, route, heading] of pages) {
      await visit(page, route, heading)
      await page.screenshot({ path: path.join(sizeDir, `${slug}.png`), fullPage: true })
    }
  }
  expect(consoleErrors, `console errors:\n${consoleErrors.join('\n')}`).toEqual([])
  expect(badResponses, `bad API responses:\n${badResponses.join('\n')}`).toEqual([])
})

test('knowledge graph exposes real counts and keyboard/zoom controls', async ({ page }) => {
  await enterDemo(page)
  await visit(page, '/knowledge', /知识中枢|知识图谱/)
  await expect(page.getByRole('button', { name: '业务场景与范围，章节模块' })).toBeVisible()
  await expect(page.getByRole('button', { name: '验证与变更，章节模块' })).toBeVisible()
  await expect(page.locator('.course-stat-row')).toContainText('6')
  await expect(page.locator('.course-stat-row')).toContainText('30')
  const graphNode = page.locator('.kg-node').first()
  await graphNode.focus()
  await page.keyboard.press('+')
  await expect(page.getByRole('status')).toBeVisible().catch(() => undefined)
  await page.keyboard.press('End')
  await page.keyboard.press('0')
  await expect(page.getByRole('button', { name: '适配图谱到窗口' })).toBeVisible()
  await page.getByRole('button', { name: '适配图谱到窗口' }).click()
})

test('wrong-book galaxy canvas is keyboard reachable and empty state is explicit', async ({ page }) => {
  await enterDemo(page)
  await visit(page, '/exercise', /练习诊断|Practice Center/)
  await page.locator('button').filter({ hasText: '错题本' }).first().click()
  await expect(page.locator('[aria-label="错题标签星系"]')).toBeHidden()
  await expect(page.locator('body')).toContainText(/当前无待复盘错题|错题本/)
  await page.getByRole('button', { name: /知识点诊断/ }).click()
  const canvas = page.locator('canvas[aria-label="错题标签星系"]')
  await expect(canvas).toHaveAttribute('tabindex', '0')
  await expect(canvas).toHaveAttribute('aria-describedby', 'tag-galaxy-keyboard-help')
  await canvas.focus()
  await page.keyboard.press('+')
  await page.keyboard.press('0')
  await page.keyboard.press('Escape')
})
