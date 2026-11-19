import { expect, test, type Page } from '@playwright/test'

const viewport = { width: 2048, height: 1152 }
const emptyStudent = 'test-generated-density-empty-v2'

async function openExercise(page: Page) {
  await page.setViewportSize(viewport)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.addInitScript((studentId) => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    localStorage.setItem('las_student_id', studentId)
    localStorage.removeItem(`exercise_active_question_banks:${studentId}`)
  }, emptyStudent)
  await page.goto('/exercise', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.workshop-shell-practice')).toBeVisible()
}

async function assertNoPageOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow, '练习页不应把整个文档撑宽').toBeLessThanOrEqual(1)
}

test('current question-bank form follows its content and keeps core controls visible', async ({ page }) => {
  await openExercise(page)
  await page.getByRole('button', { name: /题库定制/ }).first().click()
  const panel = page.locator('.workshop-content > .studio-panel:visible').first()
  await expect(panel).toBeVisible()
  await expect(page.getByRole('button', { name: '生成阶段题库并开始学习' })).toBeVisible()
  const dimensions = await panel.evaluate((element) => {
    const box = element.getBoundingClientRect()
    const children = [...element.children].map((child) => child.getBoundingClientRect())
    return { height: box.height, lastContentBottom: Math.max(...children.map((child) => child.bottom)) - box.top }
  })
  expect(dimensions.height - dimensions.lastContentBottom, '表单不应保留大块固定高度空白').toBeLessThan(100)
  await assertNoPageOverflow(page)
})

test('smart practice waits for an explicit start action', async ({ page }) => {
  await openExercise(page)
  await page.getByRole('button', { name: /智能做题/ }).first().click()
  await expect(page.getByTestId('practice-start-panel')).toBeVisible()
  await expect(page.getByRole('button', { name: '开始做题' })).toBeVisible()
  await expect(page.locator('.exercise-question-focus')).toHaveCount(0)
  await assertNoPageOverflow(page)
})

test('empty wrong-book explains the next step without showing a zero-value radar', async ({ page }) => {
  await openExercise(page)
  await page.getByRole('button', { name: /错题本/ }).first().click()
  const empty = page.locator('.wrongbook-empty-state:visible')
  await expect(empty).toBeVisible()
  await expect(empty).toContainText(/做题|练习|错题/)
  await expect(page.locator('.wrongbook-radar:visible')).toHaveCount(0)
  await assertNoPageOverflow(page)
})

test('demo knowledge concepts use semantic SVG icons and remain selectable', async ({ page }) => {
  await page.setViewportSize(viewport)
  await page.addInitScript(() => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    localStorage.setItem('las_student_id', 'demo')
  })
  await page.goto('/knowledge', { waitUntil: 'domcontentloaded' })
  const concepts = page.locator('.kg-node.type-concept')
  await expect(concepts.first()).toBeVisible()
  const iconAudit = await concepts.locator('.node-icon').evaluateAll((icons) => ({
    count: icons.length,
    withoutSvg: icons.filter((icon) => !icon.querySelector('svg')).length,
    pointGlyphs: icons.filter((icon) => icon.textContent?.trim() === '点').length,
  }))
  expect(iconAudit.count).toBeGreaterThan(0)
  expect(iconAudit.withoutSvg).toBe(0)
  expect(iconAudit.pointGlyphs).toBe(0)
  await concepts.first().click()
  await expect(concepts.first()).toHaveAttribute('aria-selected', 'true')
})
