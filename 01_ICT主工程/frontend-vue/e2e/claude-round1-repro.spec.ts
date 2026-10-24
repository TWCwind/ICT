import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { test, type Page } from '@playwright/test'

// 第一轮复现探针：真实登录 + 真实点击所有可见按钮，记录每个按钮的可观察结果。
// 该测试只做记录，不做断言；结果写入 test-results/claude-round1/probe-report.json。

type ButtonRecord = {
  route: string
  label: string
  index: number
  disabled: boolean
  hitTest: string
  clicked: boolean
  clickError?: string
  navigated: boolean
  domChanged: boolean
  focusChanged: boolean
  scrollChanged: boolean
  apiCalls: string[]
  fileChooser: boolean
  download: boolean
  popup: boolean
  dialog: boolean
  consoleErrors: string[]
}

const routes = ['/', '/profile', '/workshop', '/path', '/exercise', '/knowledge', '/multimodal', '/tutor', '/evaluate']
const routeNames: Record<string, string> = {
  '/': '总控首页',
  '/profile': '用户画像(用户设置)',
  '/workshop': '资源工坊',
  '/path': '路径推送',
  '/exercise': '练习诊断',
  '/knowledge': '知识中枢',
  '/multimodal': '多模态实验室',
  '/tutor': '智能辅导',
  '/evaluate': '评估进化',
}
const maxButtonsPerRoute = 60
// 产物写到工程根 test-results/claude-round1：frontend-vue/test-results 会被
// 每次 `playwright test` 启动时整体清空，与并发测试运行互相覆盖。
const outputDir = join(process.cwd(), '..', 'test-results', 'claude-round1')

async function settle(page: Page) {
  await page.waitForLoadState('domcontentloaded', { timeout: 20_000 }).catch(() => undefined)
  await page.waitForTimeout(1500)
}

async function domSignature(page: Page) {
  return page.locator('.portal-main').evaluate((element) => element.innerHTML)
}

async function hitTestButton(page: Page, index: number) {
  return page.locator('.portal-main button:visible').nth(index).evaluate((element: HTMLElement) => {
    const rect = element.getBoundingClientRect()
    const x = rect.left + rect.width / 2
    const y = rect.top + rect.height / 2
    const top = document.elementFromPoint(x, y)
    if (!top) return 'no-element-at-point(offscreen?)'
    if (top === element || element.contains(top) || top.contains(element)) return 'ok'
    const describe = (node: Element) => {
      const cls = typeof node.className === 'string' && node.className.trim() ? `.${node.className.trim().split(/\s+/).slice(0, 3).join('.')}` : ''
      return `${node.tagName.toLowerCase()}${cls}`
    }
    const style = getComputedStyle(top)
    return `blocked:${describe(top)} pointer-events=${style.pointerEvents} z=${style.zIndex} opacity=${style.opacity}`
  })
}

test('真实登录并逐一点击全部可见按钮，记录可观察结果', async ({ page }) => {
  test.setTimeout(45 * 60_000)
  mkdirSync(outputDir, { recursive: true })

  const consoleErrors: string[] = []
  const records: ButtonRecord[] = []
  const notes: string[] = []

  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text().slice(0, 300))
  })
  page.on('pageerror', (error) => consoleErrors.push(`pageerror: ${String(error).slice(0, 300)}`))
  page.on('dialog', (dialog) => { void dialog.dismiss().catch(() => undefined) })

  // --- 1. 未登录遮罩行为 ---
  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await settle(page)
  await page.screenshot({ path: join(outputDir, '00-login-gate.png'), fullPage: false })
  const gateVisible = await page.locator('.login-gate').isVisible().catch(() => false)
  notes.push(`登录遮罩初始可见: ${gateVisible}`)

  if (!gateVisible) {
    notes.push('异常：进入首页未见登录遮罩')
  } else {
    // 点击遮罩背后的主导航，验证点击不会穿透（设计上应被遮罩拦截）
    const navUrlBefore = page.url()
    await page.locator('.portal-nav-link').first().click({ timeout: 5_000, noWaitAfter: true }).catch(() => undefined)
    await page.waitForTimeout(400)
    notes.push(`未登录时点击主导航后 URL: ${page.url()}（之前 ${navUrlBefore}）`)
    // 错误验证码应出现中文错误提示
    await page.locator('.login-field input[placeholder="手机号"]').fill('13800001234')
    await page.locator('.login-field input[placeholder="密码"]').fill('demo123')
    await page.locator('.login-field input[placeholder="验证码"]').fill('XXXX')
    await page.locator('.login-submit').click({ timeout: 5_000, noWaitAfter: true })
    await page.waitForTimeout(400)
    const loginErrorText = (await page.locator('.login-tip strong').innerText().catch(() => '')) || ''
    notes.push(`错误验证码提示: ${loginErrorText.trim() || '（无提示）'}`)
  }

  // --- 2. 真实登录 ---
  await page.locator('.login-field input[placeholder="验证码"]').fill('2VV3')
  await page.locator('.login-submit').click({ timeout: 5_000, noWaitAfter: true })
  await page.waitForSelector('.login-gate', { state: 'hidden', timeout: 10_000 }).catch(() => undefined)
  const loginGateGone = !(await page.locator('.login-gate').isVisible().catch(() => false))
  notes.push(`提交正确凭据后登录遮罩消失: ${loginGateGone}`)
  await page.screenshot({ path: join(outputDir, '01-after-login.png'), fullPage: false })
  if (!loginGateGone) {
    const tip = await page.locator('.login-tip strong').innerText().catch(() => '')
    notes.push(`登录失败提示: ${tip}`)
  }

  // --- 3. 用户设置面板 ---
  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await settle(page)
  const settingsTrigger = page.locator('.portal-user-trigger')
  const settingsVisible = await settingsTrigger.isVisible().catch(() => false)
  notes.push(`用户设置按钮可见: ${settingsVisible}`)
  if (settingsVisible) {
    let apiCalls: string[] = []
    const onRequest = (request: { url(): string }) => {
      const path = new URL(request.url()).pathname
      if (path.startsWith('/api/') && path !== '/api/health') apiCalls.push(`${request.method()} ${path}`)
    }
    page.on('request', onRequest)
    await settingsTrigger.click({ timeout: 10_000, noWaitAfter: true })
    await page.waitForTimeout(500)
    const panelVisible = await page.locator('.portal-settings-panel').isVisible().catch(() => false)
    notes.push(`点击用户设置后面板可见: ${panelVisible}`)
    await page.screenshot({ path: join(outputDir, '02-settings-panel.png'), fullPage: false })
    const closeBtn = page.locator('.portal-settings-panel header button')
    if (panelVisible && await closeBtn.isVisible().catch(() => false)) {
      await closeBtn.click({ timeout: 5_000, noWaitAfter: true })
      await page.waitForTimeout(300)
      notes.push(`点击关闭后面板隐藏: ${!(await page.locator('.portal-settings-panel').isVisible().catch(() => true))}`)
    }
    apiCalls = []
    await settingsTrigger.click({ timeout: 10_000, noWaitAfter: true })
    await page.waitForTimeout(300)
    const profileLink = page.locator('.portal-settings-panel footer a')
    if (await profileLink.isVisible().catch(() => false)) {
      await profileLink.click({ timeout: 10_000, noWaitAfter: true })
      await page.waitForTimeout(800)
      notes.push(`点击“完善用户画像”后 URL: ${page.url()}`)
    }
    page.off('request', onRequest)
  }

  // --- 4. 每个页面逐一真实点击所有可见按钮 ---
  for (const route of routes) {
    await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 })
    await settle(page)
    const safeName = route === '/' ? 'home' : route.replace(/\//g, '-').slice(1)
    await page.screenshot({ path: join(outputDir, `page-${safeName}.png`), fullPage: false })

    const total = await page.locator('.portal-main button:visible').count()
    const limit = Math.min(total, maxButtonsPerRoute)
    notes.push(`${route}(${routeNames[route]}) 可见按钮数: ${total}${total > limit ? `（只测前 ${limit} 个）` : ''}`)

    for (let index = 0; index < limit; index += 1) {
      // 每个按钮都在页面新加载后点击，避免状态串联
      await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 })
      await settle(page)
      const button = page.locator('.portal-main button:visible').nth(index)
      if (!(await button.isVisible().catch(() => false))) continue

      const label = ((await button.innerText().catch(() => '')) || await button.getAttribute('aria-label') || `button-${index}`)
        .trim().replace(/\s+/g, ' ').slice(0, 40)
      const disabled = await button.isDisabled().catch(() => false)
      // :visible 只表示元素有布局尺寸，不保证它位于当前视口；先滚入视口，
      // 再做 elementFromPoint 命中检测，避免把长页面底部按钮误报为遮挡。
      await button.scrollIntoViewIfNeeded().catch(() => undefined)
      const hitTest = await hitTestButton(page, index)

      const record: ButtonRecord = {
        route,
        label: label || `button-${index}`,
        index,
        disabled,
        hitTest,
        clicked: false,
        navigated: false,
        domChanged: false,
        focusChanged: false,
        scrollChanged: false,
        apiCalls: [],
        fileChooser: false,
        download: false,
        popup: false,
        dialog: false,
        consoleErrors: [],
      }
      records.push(record)

      if (disabled) continue

      const errorMarker = consoleErrors.length
      let apiCalls: string[] = []
      const onRequest = (request: { method(): string; url(): string }) => {
        const path = new URL(request.url()).pathname
        if (path.startsWith('/api/') && path !== '/api/health') apiCalls.push(`${request.method()} ${path}`)
      }
      page.on('request', onRequest)
      page.once('filechooser', () => { record.fileChooser = true })
      page.once('download', () => { record.download = true })
      page.once('popup', () => { record.popup = true })
      page.on('dialog', (dialog) => { record.dialog = true })

      const beforeUrl = page.url()
      const beforeDom = await domSignature(page)
      const beforeState = await page.evaluate(() => ({
        scrollY: Math.round(window.scrollY),
        active: document.activeElement ? `${document.activeElement.tagName.toLowerCase()}#${(document.activeElement as HTMLElement).id || ''}.${(document.activeElement as HTMLElement).className || ''}`.slice(0, 60) : 'none',
      }))
      try {
        await button.click({ timeout: 15_000, noWaitAfter: true })
        record.clicked = true
      } catch (error) {
        record.clickError = String(error).split('\n').slice(0, 3).join(' | ').slice(0, 240)
      }
      await page.waitForTimeout(900)

      record.apiCalls = Array.from(new Set(apiCalls))
      record.navigated = page.url() !== beforeUrl
      if (!record.navigated) {
        const afterDom = await domSignature(page).catch(() => '')
        record.domChanged = beforeDom !== afterDom
        const afterState = await page.evaluate(() => ({
          scrollY: Math.round(window.scrollY),
          active: document.activeElement ? `${document.activeElement.tagName.toLowerCase()}#${(document.activeElement as HTMLElement).id || ''}.${(document.activeElement as HTMLElement).className || ''}`.slice(0, 60) : 'none',
        })).catch(() => ({ scrollY: 0, active: 'none' }))
        record.scrollChanged = Math.abs(afterState.scrollY - beforeState.scrollY) > 2
        record.focusChanged = afterState.active !== beforeState.active
      }
      record.consoleErrors = consoleErrors.slice(errorMarker)
      page.off('request', onRequest)
    }
  }

  // --- 5. 退出登录 ---
  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await settle(page)
  await page.locator('.portal-user-trigger').click({ timeout: 10_000, noWaitAfter: true })
  await page.waitForTimeout(300)
  const logoutButton = page.locator('.portal-settings-panel footer button')
  if (await logoutButton.isVisible().catch(() => false)) {
    await logoutButton.click({ timeout: 10_000, noWaitAfter: true })
    await page.waitForTimeout(800)
    const gateBack = await page.locator('.login-gate').isVisible().catch(() => false)
    notes.push(`点击“退出登录”后回到登录遮罩: ${gateBack}，URL: ${page.url()}`)
    await page.screenshot({ path: join(outputDir, '03-after-logout.png'), fullPage: false })
  } else {
    notes.push('未找到“退出登录”按钮')
  }

  // --- 6. 汇总 ---
  const clicked = records.filter((item) => item.clicked && !item.disabled)
  const noOutcome = clicked.filter((item) =>
    !item.navigated && !item.domChanged && !item.focusChanged && !item.scrollChanged && item.apiCalls.length === 0
    && !item.fileChooser && !item.download && !item.popup && !item.dialog)
  const blocked = records.filter((item) => !item.hitTest.startsWith('ok'))

  const summary = {
    target: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
    notes,
    totalButtonsSeen: records.length,
    clickedCount: clicked.length,
    noOutcomeCount: noOutcome.length,
    blockedCount: blocked.length,
    consoleErrorTotal: consoleErrors.length,
    noOutcome: noOutcome.map(({ route, label, index, hitTest, consoleErrors: errors }) => ({ route, label, index, hitTest, consoleErrors: errors.slice(0, 3) })),
    blocked: blocked.map(({ route, label, hitTest }) => ({ route, label, hitTest })),
    clickErrors: records.filter((item) => item.clickError).map(({ route, label, clickError }) => ({ route, label, clickError })),
    consoleErrors: consoleErrors.slice(0, 60),
  }
  writeFileSync(join(outputDir, 'probe-report.json'), JSON.stringify(summary, null, 2), 'utf8')
  writeFileSync(join(outputDir, 'probe-records.json'), JSON.stringify(records, null, 2), 'utf8')
  console.log(`[claude-round1] buttons=${records.length} clicked=${clicked.length} no-outcome=${noOutcome.length} blocked=${blocked.length} consoleErrors=${consoleErrors.length}`)
  for (const item of noOutcome) console.log(`[claude-round1] 无可观察结果: ${item.route} :: ${item.label} (${item.hitTest})`)
  for (const item of blocked) console.log(`[claude-round1] 点击被遮挡: ${item.route} :: ${item.label} (${item.hitTest})`)
})
