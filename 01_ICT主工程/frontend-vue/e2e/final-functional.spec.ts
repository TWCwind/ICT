import { expect, test } from '@playwright/test'

async function authenticate(page: import('@playwright/test').Page, studentId: string) {
  await page.addInitScript((id) => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    localStorage.setItem('las_student_id', id)
  }, studentId)
}

test('wrong-book radar renders a persisted wrong answer from an isolated learner', async ({ page }) => {
  const studentId = 'test-generated-final-functional-wrong-v2'
  const plan = await page.request.post('/api/path/plan', { data: { student_id: studentId, goals: 'test/generated: 软件需求验收练习' } })
  expect((await plan.json()).success).toBe(true)
  const bank = await page.request.post('/api/path/stage/questions', { data: { student_id: studentId, count: 3, question_types: ['single_choice'] } })
  expect((await bank.json()).success).toBe(true)
  const session = await page.request.get(`/api/exercise/session?student_id=${studentId}&limit=3`)
  const sessionData = (await session.json()).data
  expect(sessionData.questions.length).toBeGreaterThan(0)
  const answer = await page.request.post('/api/exercise/answer', { data: { student_id: studentId, question_id: sessionData.questions[0].id, answer: 'Z' } })
  const answerData = (await answer.json()).data
  expect(answerData.correct).toBe(false)
  await authenticate(page, studentId)
  await page.goto('/exercise')
  await page.getByRole('button', { name: /错题本/ }).first().click()
  const radar = page.locator('.ability-radar-svg')
  await expect(radar).toBeVisible()
  const points = await radar.locator('.radar-area').getAttribute('points')
  expect(points).toBeTruthy()
  expect(points).not.toBe('120,120 120,120 120,120 120,120 120,120 120,120')
  const wrongBook = await page.request.get(`/api/exercise/wrong-book?student_id=${studentId}`)
  expect((await wrongBook.json()).data.stats.wrong).toBeGreaterThan(0)
})

test('workshop loads a persisted demo resource body as readable preview', async ({ page }) => {
  await authenticate(page, 'demo')
  await page.goto('/workshop')
  const resources = await page.request.get('/api/workshop/overview?student_id=demo')
  const overview = await resources.json()
  expect(overview.success).toBe(true)
  expect(overview.data.latest.length).toBeGreaterThan(0)
  const selected = page.locator('.shot-record-card:visible').first()
  await expect(selected).toBeVisible()
  await selected.click()
  const preview = page.locator('.shot-preview-content .markdown-body')
  await expect(preview).toBeVisible({ timeout: 20_000 })
  expect((await preview.innerText()).trim().length).toBeGreaterThan(40)
  await page.getByRole('button', { name: '查看全文' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('dialog')).toContainText('软件需求分析与建模')
  await page.getByRole('dialog').getByRole('button', { name: '关闭' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('global user settings opens and exposes profile actions', async ({ page }) => {
  await authenticate(page, 'demo_user_001')
  await page.goto('/profile')
  await page.getByRole('button', { name: /用户设置/ }).click()
  await expect(page.getByText('学习者 ID')).toBeVisible()
  await expect(page.getByRole('link', { name: /完善用户画像/ })).toBeVisible()
})
