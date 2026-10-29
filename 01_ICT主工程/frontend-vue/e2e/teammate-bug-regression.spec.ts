import { expect, test, type Page } from '@playwright/test'

const routes = [
  ['总控首页', '/'],
  ['用户画像', '/profile'],
  ['资源工坊', '/workshop'],
  ['路径推送', '/path'],
  ['练习诊断', '/exercise'],
  ['知识中枢', '/knowledge'],
  ['多模态实验室', '/multimodal'],
  ['智能辅导', '/tutor'],
  ['评估进化', '/evaluate'],
] as const

async function login(page: Page) {
  await page.goto('/')
  const loginGate = page.locator('.login-gate')
  if (await loginGate.isVisible().catch(() => false)) {
    await page.getByPlaceholder('手机号').fill('10000000000')
    await page.getByPlaceholder('密码', { exact: true }).fill('demo123')
    await page.getByPlaceholder('验证码').fill('2VV3')
    await page.getByRole('button', { name: '登录并进入系统' }).click()
    await expect(loginGate).toBeHidden()
  }
}

test('primary navigation and settings popover work with keyboard and restore focus', async ({ page }) => {
  const pageErrors: string[] = []
  const failedApi: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('response', response => {
    if (response.url().includes('/api/') && response.status() >= 500) {
      failedApi.push(`${response.status()} ${response.url()}`)
    }
  })

  await login(page)
  for (const [name, route] of routes.slice(1)) {
    await page.getByRole('link', { name, exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`${route.replaceAll('/', '\\/')}$`))
    await expect(page.locator('.portal-main')).not.toBeEmpty()
    await expect(page.locator(`.portal-nav a[href="${route}"]`)).toHaveClass(/router-link-active/)
  }

  const trigger = page.getByRole('button', { name: '打开用户设置' })
  await trigger.click()
  const panel = page.getByRole('region', { name: '用户设置面板' })
  await expect(panel).toBeVisible()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await expect(page.locator('.portal-settings-panel input').first()).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await expect(trigger).toBeFocused()

  await trigger.click()
  const settingsInputs = panel.locator('input')
  await settingsInputs.nth(0).fill('teammate-regression-learner')
  await settingsInputs.nth(1).fill('软件工程')
  await panel.locator('textarea').fill('检查刷新后学习者设置是否保留')
  await page.reload()
  await trigger.click()
  await expect(panel.locator('input').nth(0)).toHaveValue('teammate-regression-learner')
  await expect(panel.locator('input').nth(1)).toHaveValue('软件工程')
  await expect(panel.locator('textarea')).toHaveValue('检查刷新后学习者设置是否保留')
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()

  await trigger.click()
  await panel.getByRole('button', { name: '关闭用户设置' }).click()
  await expect(panel).toBeHidden()
  await expect(trigger).toBeFocused()

  await trigger.click()
  await page.locator('.portal-main').click({ position: { x: 12, y: 12 } })
  await expect(panel).toBeHidden()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')

  await trigger.click()
  await panel.getByRole('button', { name: '退出登录' }).click()
  await expect(page.locator('.login-gate')).toBeVisible()
  await login(page)
  await expect(page.locator('.login-gate')).toBeHidden()
  expect(pageErrors).toEqual([])
  expect(failedApi).toEqual([])
})

test('exercise sections switch state and knowledge graph controls update real selection and zoom', async ({ page }) => {
  const exerciseSessionRequests: string[] = []
  page.on('request', request => {
    if (request.url().includes('/api/exercise/session')) exerciseSessionRequests.push(request.url())
  })
  await login(page)
  await page.goto('/exercise')
  const practiceNav = page.getByRole('navigation', { name: '练习诊断导航' })
  for (const name of ['题库定制', '智能做题', '错题本', '知识点诊断']) {
    const item = practiceNav.getByRole('button', { name: new RegExp(name) })
    await item.click()
    await expect(item).toHaveAttribute('aria-current', 'page')
    await expect(item).toHaveClass(/active/)
    await expect(page.locator('.workshop-content')).not.toBeEmpty()
    if (name === '智能做题') {
      await expect(page.getByTestId('practice-start-panel')).toBeVisible()
      await expect(page.locator('.exercise-practice-center')).toHaveCount(0)
      expect(exerciseSessionRequests, 'entering the tab must not load or start a practice session').toEqual([])
      const sessionResponse = page.waitForResponse(response => response.url().includes('/api/exercise/session'))
      await page.getByRole('button', { name: '开始做题', exact: true }).click()
      const response = await sessionResponse
      const payload = await response.json()
      expect(response.ok()).toBe(true)
      expect(payload.success).toBe(true)
      await expect(page.locator('.exercise-practice-center')).toBeVisible()
      if ((payload.data?.questions || []).length) {
        await expect(page.locator('.exercise-question-focus')).toBeVisible()
      } else {
        await expect(page.locator('.exercise-empty')).toBeVisible()
        const emptyLayout = await page.locator('.exercise-practice-center').evaluate(root => {
          const rootRect = root.getBoundingClientRect()
          const mainRect = root.querySelector('.practice-main-panel')!.getBoundingClientRect()
          return { rootWidth: rootRect.width, mainWidth: mainRect.width }
        })
        expect(emptyLayout.mainWidth, JSON.stringify(emptyLayout)).toBeGreaterThan(emptyLayout.rootWidth * 0.9)
      }
    }
  }

  await page.goto('/knowledge')
  await expect(page.locator('.kg-node').first()).toBeVisible()
  const initialGraphNodeCount = await page.locator('.kg-node').count()
  const sourceFilters = page.locator('.filter-unit').filter({ hasText: '知识来源' })
  const resourceFilter = sourceFilters.getByRole('button', { name: '资源', exact: true })
  await resourceFilter.click()
  await expect(resourceFilter).toHaveClass(/active/)
  await expect.poll(() => page.locator('.kg-node').count()).toBeLessThan(initialGraphNodeCount)
  await sourceFilters.getByRole('button', { name: '全量', exact: true }).click()
  await expect.poll(() => page.locator('.kg-node').count()).toBe(initialGraphNodeCount)

  const graphNode = page.locator('.kg-node').first()
  await expect(graphNode).toBeVisible()
  await graphNode.click()
  await expect(page.locator('.selected-node-card')).toBeVisible()
  const zoom = page.locator('.graph-zoom-controls output')
  await expect(zoom).toHaveText(/\d+%/)
  const before = Number((await zoom.innerText()).replace('%', ''))
  await page.getByRole('button', { name: '放大图谱' }).click()
  await expect(zoom).toHaveText(`${before + 10}%`)
  await graphNode.focus()
  await page.keyboard.press('End')
  await expect(page.locator('.selected-node-card')).toBeVisible()
  await page.keyboard.press('0')
  await expect(zoom).toHaveText('100%')
})

test('mobile navigation remains clickable without page-wide horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page)
  const navGeometry = await page.locator('.portal-nav').evaluate(nav => {
    const rect = nav.getBoundingClientRect()
    const links = Array.from(nav.querySelectorAll('a')).map(link => {
      const item = link.getBoundingClientRect()
      return { left: item.left, right: item.right, height: item.height }
    })
    return { left: rect.left, right: rect.right, clientWidth: nav.clientWidth, scrollWidth: nav.scrollWidth, links }
  })
  expect(navGeometry.links).toHaveLength(9)
  expect(navGeometry.scrollWidth, 'mobile navigation should expose all items without a hidden horizontal scroller').toBeLessThanOrEqual(navGeometry.clientWidth + 1)
  expect(navGeometry.links.every(link => link.left >= navGeometry.left - 1 && link.right <= navGeometry.right + 1 && link.height >= 44), JSON.stringify(navGeometry)).toBe(true)
  await page.getByRole('link', { name: '资源工坊', exact: true }).click()
  await expect(page).toHaveURL(/\/workshop$/)
  await expect(page.locator('.portal-main')).not.toBeEmpty()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  const unnamedButtons = await page.locator('button:visible').evaluateAll(buttons => buttons.filter(button => {
    const element = button as HTMLButtonElement
    return !element.disabled && !(element.innerText.trim() || element.getAttribute('aria-label') || element.getAttribute('title'))
  }).length)
  expect(unnamedButtons, 'visible enabled buttons should have an accessible name').toBe(0)
})

test('tablet-width primary navigation has its own row and does not overlap settings', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await login(page)
  const geometry = await page.evaluate(() => {
    const header = document.querySelector('.portal-header')!.getBoundingClientRect()
    const brand = document.querySelector('.portal-brand')!.getBoundingClientRect()
    const nav = document.querySelector('.portal-nav') as HTMLElement
    const navRect = nav.getBoundingClientRect()
    const settings = document.querySelector('.portal-user-trigger')!.getBoundingClientRect()
    const links = Array.from(nav.querySelectorAll('a')).map(link => {
      const rect = link.getBoundingClientRect()
      return { left: rect.left, right: rect.right }
    })
    return {
      headerBottom: header.bottom,
      brandBottom: brand.bottom,
      navTop: navRect.top,
      navLeft: navRect.left,
      navRight: navRect.right,
      settingsBottom: settings.bottom,
      clientWidth: nav.clientWidth,
      scrollWidth: nav.scrollWidth,
      links,
    }
  })
  expect(geometry.navTop, JSON.stringify(geometry)).toBeGreaterThanOrEqual(geometry.brandBottom)
  expect(geometry.navTop, JSON.stringify(geometry)).toBeGreaterThanOrEqual(geometry.settingsBottom)
  expect(geometry.navRight, JSON.stringify(geometry)).toBeLessThanOrEqual(1024)
  expect(geometry.scrollWidth, 'all nine primary links should fit at 1024px').toBeLessThanOrEqual(geometry.clientWidth + 1)
  expect(geometry.links.every(link => link.left >= geometry.navLeft - 1 && link.right <= geometry.navRight + 1), JSON.stringify(geometry)).toBe(true)
})

test('tablet evaluation keeps all evidence columns inside the visible card', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  await login(page)
  await page.goto('/evaluate')
  const scoreRow = page.locator('.shot-score-row')
  await expect(scoreRow).toBeVisible()
  const geometry = await scoreRow.evaluate(element => {
    const row = element.getBoundingClientRect()
    const cards = Array.from(element.children).map(child => {
      const rect = child.getBoundingClientRect()
      return { left: rect.left, right: rect.right, width: rect.width }
    })
    return { width: row.width, scrollWidth: element.scrollWidth, left: row.left, right: row.right, cards }
  })
  expect(geometry.scrollWidth, 'evaluation score row must not internally clip a column').toBeLessThanOrEqual(geometry.width + 1)
  expect(geometry.cards.every(card => card.left >= geometry.left - 1 && card.right <= geometry.right + 1), JSON.stringify(geometry)).toBe(true)
  await expect(page.locator('.shot-evidence-version')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

test('knowledge graph fallback fullscreen exits on Escape and restores its trigger focus', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
      configurable: true,
      value: () => Promise.reject(new Error('Fullscreen API unavailable in this browser')),
    })
  })
  await login(page)
  await page.goto('/knowledge')
  const fullscreenButton = page.getByRole('button', { name: '进入全屏' })
  await fullscreenButton.click()
  const graph = page.locator('.knowledge-course-map')
  await expect(graph).toHaveClass(/fullscreen/)
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden')
  await page.keyboard.press('Escape')
  await expect(graph).not.toHaveClass(/fullscreen/)
  await expect(page.locator('body')).not.toHaveCSS('overflow', 'hidden')
  await expect(page.getByRole('button', { name: '进入全屏' })).toBeFocused()
})

test('knowledge graph native fullscreen stays synchronized and exits cleanly', async ({ page }) => {
  await login(page)
  await page.goto('/knowledge')
  const supported = await page.evaluate(() => document.fullscreenEnabled && typeof document.documentElement.requestFullscreen === 'function')
  test.skip(!supported, 'native fullscreen is not available in this browser')
  const fullscreenButton = page.getByRole('button', { name: '进入全屏' })
  await fullscreenButton.click()
  await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(true)
  await expect(page.locator('.knowledge-course-map')).toHaveClass(/fullscreen/)
  await page.keyboard.press('Escape')
  await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(false)
  await expect(page.locator('.knowledge-course-map')).not.toHaveClass(/fullscreen/)
  await expect(page.locator('body')).not.toHaveCSS('overflow', 'hidden')
  await expect(page.getByRole('button', { name: '进入全屏' })).toBeFocused()
})

test('backend outage exposes retry and the real local API recovers', async ({ page }) => {
  await page.route('**/api/health', route => route.fulfill({
    status: 502,
    contentType: 'text/plain',
    body: 'proxy returned a non-JSON gateway error',
  }))
  await page.goto('/')
  const notice = page.getByRole('status', { name: '服务连接状态' })
  await expect(notice).toContainText('本地服务暂时未连接')
  await expect(page.locator('body')).not.toContainText('proxy returned a non-JSON gateway error')
  const retry = notice.getByRole('button', { name: '重新检查连接' })
  await expect(retry).toBeVisible()
  await page.unroute('**/api/health')
  await retry.click()
  await expect(notice).toContainText('服务已恢复连接')
})
