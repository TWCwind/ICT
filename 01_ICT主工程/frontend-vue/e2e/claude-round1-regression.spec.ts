import { expect, test, type Page } from '@playwright/test'

// 第一轮修复回归：只覆盖本轮修改的页面（评估进化/多模态实验室/智能辅导/资源工坊），
// 以及探针未覆盖完的知识中枢按钮尾部（第 60 个之后）。

async function openAsFreshLearner(page: Page, route: string) {
  await page.addInitScript(() => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    localStorage.setItem('las_student_id', 'claude-round1-learner')
    localStorage.removeItem('multimodal-chat-sessions-v2')
  })
  await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.waitForTimeout(1200)
  await expect(page.locator('.portal-main')).toBeVisible()
}

test('评估进化：诊断页签切换与重复点击都有可观察结果', async ({ page }) => {
  await openAsFreshLearner(page, '/evaluate')
  const tabs = page.locator('.shot-diagnosis nav button')
  await expect(tabs.nth(0)).toHaveAttribute('aria-pressed', 'true')
  await expect(tabs.nth(0)).toHaveClass(/active/)

  // 切到薄弱点热区：页签状态翻转，面板标题跟随
  await tabs.nth(1).click()
  await expect(tabs.nth(1)).toHaveAttribute('aria-pressed', 'true')
  await expect(tabs.nth(0)).toHaveAttribute('aria-pressed', 'false')

  // 切回诊断结论：状态再次翻转
  await tabs.nth(0).click()
  await expect(tabs.nth(0)).toHaveAttribute('aria-pressed', 'true')

  // 重复点击已选中的“诊断结论”：把诊断面板带回视野
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.waitForTimeout(200)
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
  await tabs.nth(0).click()
  await page.waitForTimeout(1200)
  const inView = await page.locator('.shot-diagnosis').evaluate((element) => {
    const rect = element.getBoundingClientRect()
    return rect.top >= 0 && rect.bottom <= window.innerHeight
  })
  expect(inView, '重复点击当前页签后面板应滚动回视野').toBe(true)
})

test('多模态实验室：模式按钮切换与重复点击都有可观察结果', async ({ page }) => {
  await openAsFreshLearner(page, '/multimodal')
  const quick = page.locator('.multi-composer button[title="快速生成"]')
  const writing = page.locator('.multi-composer button[title="帮我写作"]')
  await expect(quick).toHaveAttribute('aria-pressed', 'true')

  await writing.click()
  await expect(writing).toHaveAttribute('aria-pressed', 'true')
  await expect(quick).toHaveAttribute('aria-pressed', 'false')

  // 重复点击已选中的“帮我写作”：焦点移到输入框
  await writing.click()
  await page.waitForTimeout(300)
  const focused = await page.evaluate(() => {
    const active = document.activeElement
    return active instanceof HTMLTextAreaElement && active.placeholder.includes('发消息')
  })
  expect(focused, '重复点击当前模式按钮应聚焦输入框').toBe(true)

  await quick.click()
  await expect(quick).toHaveAttribute('aria-pressed', 'true')
})

test('智能辅导：语音未配置时展示中文错误说明与禁用原因', async ({ page }) => {
  await openAsFreshLearner(page, '/tutor')
  const startCall = page.getByRole('button', { name: '开始通话', exact: true })
  await expect(startCall).toBeDisabled()
  await expect(startCall).toHaveAttribute('title', /暂时无法通话/)
  await expect(startCall).toHaveAttribute('title', /语音通话服务未启用/)

  const status = page.locator('.realtime-status-text')
  await expect(status).toContainText('语音通话服务未启用', { timeout: 15_000 })
  await expect(status).not.toContainText('Realtime voice is disabled')
  await expect(page.getByText('语音辅导服务还没有配置完成，请先检查密钥和连接地址。')).toBeVisible()
})

test('资源工坊：生成按钮说明禁用原因，填写需求后可真实生成', async ({ page }) => {
  await openAsFreshLearner(page, '/workshop')
  const generate = page.locator('.shot-generate')
  await expect(generate).toBeDisabled()
  await expect(generate).toHaveAttribute('title', '请先填写课程、章节或薄弱点，再生成资源')

  // 参考布局里课程/章节输入框被隐藏，用户通过需求 textarea 触发生成
  await page.locator('.shot-create > textarea').fill('生成《软件需求分析与建模》第一章的讲解文档，重点讲需求获取与用例建模。')
  await expect(generate).toBeEnabled()

  const [response] = await Promise.all([
    page.waitForResponse((item) => new URL(item.url()).pathname.startsWith('/api/') && item.request().method() === 'POST', { timeout: 30_000 }),
    generate.click(),
  ])
  expect(response.status()).toBe(200)
})

test('知识中枢：补测第一轮探针未覆盖的尾部按钮', async ({ page }) => {
  test.setTimeout(6 * 60_000)
  // 尾部按钮（章节模块/核心知识点）只在 demo 课程图谱中存在
  await page.addInitScript(() => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    sessionStorage.setItem('zx-resource-agent-demo', '1')
    localStorage.setItem('las_student_id', 'demo')
    localStorage.removeItem('multimodal-chat-sessions-v2')
  })
  await page.goto('/knowledge', { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.waitForTimeout(1500)
  await expect(page.locator('.portal-main')).toBeVisible()
  const total = await page.locator('.portal-main button:visible').count()
  expect(total).toBeGreaterThan(60)

  const failures: string[] = []
  for (let index = 60; index < total; index += 1) {
    await page.goto('/knowledge', { waitUntil: 'domcontentloaded', timeout: 30_000 })
    await page.waitForTimeout(1200)
    const button = page.locator('.portal-main button:visible').nth(index)
    if (!(await button.isVisible().catch(() => false))) continue
    const label = ((await button.innerText().catch(() => '')) || await button.getAttribute('aria-label') || `button-${index}`).trim().replace(/\s+/g, ' ').slice(0, 40)
    if (await button.isDisabled().catch(() => false)) continue
    const alreadyActive = await button.evaluate((element) => (
      element.getAttribute('aria-pressed') === 'true'
      || ['active', 'selected', 'is-active', 'current'].some((name) => element.classList.contains(name))
    ))
    if (alreadyActive) continue

    let apiCalled = false
    const onRequest = (request: { method(): string; url(): string }) => {
      const path = new URL(request.url()).pathname
      if (path.startsWith('/api/') && path !== '/api/health') apiCalled = true
    }
    page.on('request', onRequest)
    const beforeUrl = page.url()
    const beforeDom = await page.locator('.portal-main').evaluate((element) => element.innerHTML)
    await button.scrollIntoViewIfNeeded().catch(() => undefined)
    await button.click({ timeout: 15_000, noWaitAfter: true }).catch(() => undefined)
    await page.waitForTimeout(800)
    page.off('request', onRequest)
    const domChanged = page.url() === beforeUrl
      && beforeDom !== await page.locator('.portal-main').evaluate((element) => element.innerHTML).catch(() => beforeDom)
    if (!apiCalled && page.url() === beforeUrl && !domChanged) {
      failures.push(`#${index} ${label || 'button-' + index}`)
    }
  }
  expect(failures, `知识中枢尾部按钮无可观察结果: ${failures.join('、')}`).toEqual([])
})
