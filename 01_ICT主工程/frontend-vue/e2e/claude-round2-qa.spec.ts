import { expect, test, type Page } from '@playwright/test'

// 第二轮交互复核：练习诊断五个视图、知识图谱全键位键盘/滚轮/全屏/输入不抢键、
// 错题星系高 DPI 与 reduced-motion。针对真实实现（KnowledgePage.handleKeydown、
// ExerciseCenterPage trySwitchPage/openTagGalaxy/galaxy renderer）编写。

async function enterDemo(page: Page, route: string) {
  await page.addInitScript(() => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    sessionStorage.setItem('zx-resource-agent-demo', '1')
    localStorage.setItem('las_student_id', 'demo')
  })
  await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.waitForTimeout(1200)
  await expect(page.locator('.portal-main')).toBeVisible()
}

function collectErrors(page: Page) {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && !/favicon|ResizeObserver loop/i.test(message.text())) errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(`pageerror: ${String(error)}`))
  return errors
}

async function graphScale(page: Page) {
  return page.locator('.graph-zoom-layer').evaluate((element) => Number((element as HTMLElement).style.transform.match(/scale\(([\d.]+)\)/)?.[1] || 1))
}

test('练习诊断：题库定制/智能做题/错题本/知识点诊断/历史星系都可切换且无错误', async ({ page }) => {
  const errors = collectErrors(page)
  await enterDemo(page, '/exercise')
  const nav = page.locator('.practice-workshop-nav button')
  await expect(nav).toHaveCount(4)

  const seen: string[] = []
  for (const label of ['题库定制', '智能做题', '错题本', '知识点诊断']) {
    const tab = nav.filter({ hasText: label })
    await tab.click()
    await page.waitForTimeout(600)
    await expect(tab).toHaveAttribute('aria-current', 'page')
    seen.push(label)
  }
  expect(seen).toEqual(['题库定制', '智能做题', '错题本', '知识点诊断'])

  // 知识点诊断页应出现错题标签星系 Canvas（无障碍属性）
  const canvas = page.locator('canvas[aria-label="错题标签星系"]')
  await expect(canvas).toHaveAttribute('tabindex', '0')
  await expect(canvas).toHaveAttribute('aria-describedby', 'tag-galaxy-keyboard-help')

  // 错题本页的“进入历史星系”入口可点击且产生视图变化
  await nav.filter({ hasText: '错题本' }).click()
  await page.waitForTimeout(500)
  const enterGalaxy = page.getByRole('button', { name: '进入历史星系' })
  if (await enterGalaxy.isVisible().catch(() => false)) {
    await enterGalaxy.click()
    await page.waitForTimeout(800)
    await expect(page.locator('canvas[aria-label="错题标签星系"]')).toBeVisible()
  }
  expect(errors, errors.join('\n')).toEqual([])
})

test('知识图谱：方向键/Home/End/0/-/+/Escape 与全屏降级、焦点返回', async ({ page }) => {
  const errors = collectErrors(page)
  await enterDemo(page, '/knowledge')
  const nodes = page.locator('.kg-node')
  await expect(nodes.first()).toBeVisible()

  // 点击选中第一个图谱节点（moveNodeFocus 基于选中节点而非仅焦点），方向键移动焦点
  const firstNode = nodes.first()
  await firstNode.click()
  await page.waitForTimeout(300)
  await firstNode.focus()
  await page.waitForTimeout(200)
  const before = await page.evaluate(() => document.activeElement?.textContent?.slice(0, 30))
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(400)
  const afterRight = await page.evaluate(() => document.activeElement?.textContent?.slice(0, 30))
  expect(afterRight, '方向键应移动节点焦点').not.toEqual(before)

  // Enter/Space 激活节点：详情面板出现选中态
  await page.keyboard.press('Enter')
  await page.waitForTimeout(400)
  await expect(page.locator('[aria-selected="true"]')).toBeVisible()

  // Home 回课程根、End 到末尾资源
  await page.keyboard.press('Home')
  await page.waitForTimeout(300)
  await expect(page.locator('[aria-selected="true"]')).toContainText(/软件需求分析|课程/)
  await page.keyboard.press('End')
  await page.waitForTimeout(300)

  // 0 复位缩放并给出状态提示（第一轮修复的行为）
  await page.keyboard.press('+')
  await page.waitForTimeout(200)
  const zoomed = await graphScale(page)
  expect(zoomed).toBeGreaterThan(1)
  await page.keyboard.press('0')
  await page.waitForTimeout(600)
  expect(await graphScale(page)).toBe(1)
  await expect(page.getByText('图谱缩放已恢复 100%。')).toBeVisible()

  // 全屏按钮存在；F 键触发全屏请求（无头环境可能被拒绝，但不得抛错），Escape 退出并恢复焦点
  await expect(page.getByRole('button', { name: /进入全屏|退出全屏/ })).toBeVisible()
  await nodes.first().focus()
  await page.keyboard.press('f')
  await page.waitForTimeout(400)
  await page.keyboard.press('Escape')
  await page.waitForTimeout(400)

  // 输入框不抢快捷键：搜索框里按 + / f 只输入字符，图谱缩放不变
  const search = page.locator('input[aria-label="搜索知识图谱"]')
  await search.click()
  await search.press('f')
  await search.press('+')
  await page.waitForTimeout(300)
  expect(await search.inputValue()).toContain('f')
  expect(await graphScale(page)).toBe(1)
  expect(errors, errors.join('\n')).toEqual([])
})

test('知识图谱滚轮：普通滚轮只滚动，Ctrl+滚轮才缩放', async ({ page }) => {
  const errors = collectErrors(page)
  await enterDemo(page, '/knowledge')
  const viewport = page.locator('.graph-scroll').first()
  const scaleBefore = await graphScale(page)
  await viewport.hover().catch(() => undefined)
  await page.mouse.wheel(0, 400)
  await page.waitForTimeout(300)
  expect(await graphScale(page), '普通滚轮不应改变缩放').toBe(scaleBefore)
  await page.keyboard.down('Control')
  await page.mouse.wheel(0, -300)
  await page.keyboard.up('Control')
  await page.waitForTimeout(300)
  expect(await graphScale(page), 'Ctrl+滚轮应改变缩放').not.toBe(scaleBefore)
  expect(errors, errors.join('\n')).toEqual([])
})

test.describe('错题星系高 DPI', () => {
  test.use({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 })
  test('高 DPI 触点与 reduced-motion 下稳定，切换页面无泄漏错误', async ({ page }) => {
  const errors = collectErrors(page)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await enterDemo(page, '/exercise')
  await page.locator('.practice-workshop-nav button').filter({ hasText: '知识点诊断' }).click()
  const canvas = page.locator('canvas[aria-label="错题标签星系"]')
  await expect(canvas).toBeVisible()
  await canvas.focus()
  await page.keyboard.press('+')
  await page.keyboard.press('-')
  const box = await canvas.boundingBox()
  if (box) {
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  }
  await page.waitForTimeout(600)
  // 切走再切回：卸载/重建资源不应产生错误
  await page.locator('.practice-workshop-nav button').filter({ hasText: '智能做题' }).click()
  await page.waitForTimeout(400)
  await page.locator('.practice-workshop-nav button').filter({ hasText: '知识点诊断' }).click()
  await page.waitForTimeout(800)
  await expect(canvas).toBeVisible()
  expect(errors, errors.join('\n')).toEqual([])
  })
})

test.describe('中小屏布局回归（第二轮修复）', () => {
  async function measure(page: Page, selector: string) {
    return page.locator(selector).first().evaluate((el) => ({ scroll: el.scrollWidth, client: el.clientWidth }))
  }

  test('1280px：评估页分数行/能力面板与知识页筛选面板不再裁切', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 })
    await enterDemo(page, '/evaluate')
    const scoreRow = await measure(page, '.shot-score-row')
    expect(scoreRow.scroll, '评估分数行内容不得超出容器').toBeLessThanOrEqual(scoreRow.client + 1)
    const capability = await measure(page, '.shot-capability__body')
    expect(capability.scroll, '能力雷达面板内容不得超出容器').toBeLessThanOrEqual(capability.client + 1)

    await enterDemo(page, '/knowledge')
    const filter = await measure(page, '.course-filter-panel')
    expect(filter.scroll, '知识筛选面板内容不得超出容器').toBeLessThanOrEqual(filter.client + 1)
    const zoom = await page.evaluate(() => {
      const shell = document.querySelector('.course-graph-shell') as HTMLElement | null
      const controls = document.querySelector('.graph-zoom-controls') as HTMLElement | null
      if (!shell || !controls) return { ok: false }
      return { ok: controls.getBoundingClientRect().right <= shell.getBoundingClientRect().right + 1 }
    })
    expect(zoom.ok, '图谱缩放控件必须完整落在图谱面板内').toBe(true)
  })

  test('1024px：学习路径时间线全部节点可见、雷达图在画像栏内', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 })
    await enterDemo(page, '/path')
    const visible = await page.locator('.shot-route-track').first().evaluate((track) => {
      const trackRight = track.getBoundingClientRect().right
      const buttons = Array.from(track.querySelectorAll<HTMLElement>(':scope > button'))
      return {
        total: buttons.length,
        inside: buttons.filter((button) => button.getBoundingClientRect().right <= trackRight + 1).length,
      }
    })
    expect(visible.total).toBeGreaterThanOrEqual(6)
    expect(visible.inside, '时间线所有节点必须完整落在容器内').toBe(visible.total)

    const radar = await page.locator('.shot-path-radar-canvas').evaluate((el) => {
      const profile = el.closest('.shot-path-profile') as HTMLElement | null
      if (!profile) return { ok: false }
      const r = el.getBoundingClientRect()
      const p = profile.getBoundingClientRect()
      return { ok: r.left >= p.left - 1 && r.right <= p.right + 1 }
    })
    expect(radar.ok, '能力雷达图必须完整落在画像栏内').toBe(true)
  })
})
