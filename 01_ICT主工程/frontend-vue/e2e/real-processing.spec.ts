import { expect, type Page, type Response, test } from '@playwright/test'

const studentId = `test-generated-real-processing-${Date.now()}`
const resourceStudentId = 'active-learner'

async function openAsLearner(page: Page, route: string) {
  await page.addInitScript((id) => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    localStorage.setItem('las_student_id', id)
  }, studentId)
  await page.goto(route, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
  await expect(page.locator('.portal-main')).toBeVisible()
}

async function successfulApi(response: Response) {
  expect(response.ok(), `${response.status()} ${response.url()}`).toBeTruthy()
  const payload = await response.json()
  expect(payload.success, JSON.stringify(payload.error || payload)).not.toBe(false)
  return payload.data ?? payload
}

test('analysis buttons create input-dependent and persisted backend evidence', async ({ page }) => {
  test.setTimeout(240_000)

  await openAsLearner(page, '/profile')
  const profileInput = page.locator('textarea:visible').first()
  const profileText = `本轮唯一证据 ${studentId}：正在学习链表，尾插法更新尾指针容易出错，偏好执行轨迹图和 Python 反例。`
  await profileInput.fill(profileText)
  const [profileResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/profile/chat') && response.request().method() === 'POST', { timeout: 90_000 }),
    page.getByRole('button', { name: '分析并更新' }).first().click(),
  ])
  const profileResult = await successfulApi(profileResponse)
  expect(JSON.stringify(profileResult)).toMatch(/链表|linked list|tail pointer/i)

  const profileRead = await page.request.get(`/api/profile/${encodeURIComponent(studentId)}/overview`)
  const persistedProfile = await successfulApi(profileRead)
  expect(persistedProfile.history.length).toBeGreaterThan(0)
  expect(JSON.stringify(persistedProfile)).toMatch(/链表|linked list|tail pointer/i)

  await openAsLearner(page, '/path')
  const goal = `test/generated：完成 ${studentId} 的链表尾插边界测试并解释指针变化`
  await page.locator('#path-real-goal').fill(goal)
  const [pathResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/path/plan') && response.request().method() === 'POST', { timeout: 90_000 }),
    page.getByRole('button', { name: /生成路径|重新规划/ }).first().click(),
  ])
  const pathResult = await successfulApi(pathResponse)
  expect(pathResult.plan.steps.length).toBeGreaterThan(0)
  expect(['llm', 'evidence_rules']).toContain(pathResult.plan.analysis_mode)

  const pathRead = await page.request.get(`/api/path/overview?student_id=${encodeURIComponent(studentId)}`)
  const persistedPath = await successfulApi(pathRead)
  expect(persistedPath.has_plan).toBe(true)
  expect(persistedPath.nodes.length).toBe(pathResult.plan.steps.length)

  await openAsLearner(page, '/tutor')
  const tutorQuestion = `根据刚才的画像证据，解释 ${studentId} 在链表尾插时为什么必须同时处理空链表，并给出可验证步骤。`
  await page.getByPlaceholder('也可以直接打字提问，回车发送…').fill(tutorQuestion)
  const [tutorResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/tutor/ask') && response.request().method() === 'POST', { timeout: 120_000 }),
    page.getByRole('button', { name: '发送问题' }).click(),
  ])
  const tutorPayload = await tutorResponse.json()
  const assistantTurn = page.locator('.tb-turn.is-assistant').last()
  if (tutorPayload.success) {
    const tutorResult = tutorPayload.data
    expect(String(tutorResult.markdown || tutorResult.answer?.text || tutorResult.answer || '').length).toBeGreaterThan(40)
    await expect(assistantTurn).not.toContainText('正在思考')
  } else {
    expect(String(tutorPayload.error?.message || '')).toMatch(/模型尚未配置|模型暂时不可用/)
    await expect(assistantTurn).toContainText(tutorPayload.error.message)
    await expect(page.locator('.tb-warn').filter({ hasText: tutorPayload.error.message })).toBeVisible()
  }

  await openAsLearner(page, '/evaluate')
  const [evaluationResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/evaluate/report') && response.request().method() === 'POST', { timeout: 90_000 }),
    page.getByRole('button', { name: /生成智能评估|生成最新评估/ }).first().click(),
  ])
  const evaluationResult = await successfulApi(evaluationResponse)
  expect(evaluationResult.report || evaluationResult).toBeTruthy()

  const evaluationRead = await page.request.get(`/api/evaluate/overview?student_id=${encodeURIComponent(studentId)}`)
  const persistedEvaluation = await successfulApi(evaluationRead)
  expect(persistedEvaluation.latest_report).toBeTruthy()
  expect(Number(persistedEvaluation.evidence?.total || 0)).toBeGreaterThan(0)
})

test('resource, exercise and multimodal buttons persist their real outputs', async ({ page }) => {
  test.setTimeout(300_000)

  await page.addInitScript((id) => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    localStorage.setItem('las_student_id', id)
  }, resourceStudentId)
  await page.goto('/workshop', { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)

  const typeButtons = page.locator('.shot-type-grid button:visible')
  const questionBankType = typeButtons.filter({ hasText: /练习题库/ }).first()
  await expect(questionBankType).toBeVisible()
  for (let index = 0; index < await typeButtons.count(); index += 1) {
    const item = typeButtons.nth(index)
    const isQuestionBank = /练习题库/.test(await item.innerText())
    if (!isQuestionBank && await item.getAttribute('aria-pressed') === 'true') await item.click()
  }
  if (await questionBankType.getAttribute('aria-pressed') !== 'true') await questionBankType.click()

  const workshopInput = page.locator('textarea:visible').first()
  await workshopInput.fill(`为 ${resourceStudentId} 生成 3 道链表尾插边界条件诊断题，每题必须包含答案、解析和知识点标签。`)
  const generateButton = page.locator('button:visible').filter({ hasText: /生成资源|生成资源包/ }).first()
  await expect(generateButton).toBeEnabled()
  const existingResourcesResponse = await page.request.get(`/api/resources?student_id=${encodeURIComponent(resourceStudentId)}`)
  const existingResourcesPayload = await existingResourcesResponse.json()
  const existingResources = existingResourcesPayload.data?.resources || existingResourcesPayload.data?.items || []
  const [workshopResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/workshop/generate') && response.request().method() === 'POST', { timeout: 120_000 }),
    generateButton.click(),
  ])
  expect(workshopResponse.ok()).toBeTruthy()
  const workshopStream = await workshopResponse.text()
  await expect(generateButton).toBeEnabled({ timeout: 180_000 })
  if (workshopStream.includes('event: error')) {
    expect(workshopStream).toContain('内容生成模型尚未配置')
    await expect(page.getByRole('alert')).toContainText('内容生成模型尚未配置')
    const afterResourcesResponse = await page.request.get(`/api/resources?student_id=${encodeURIComponent(resourceStudentId)}`)
    const afterResourcesPayload = await afterResourcesResponse.json()
    const afterResources = afterResourcesPayload.data?.resources || afterResourcesPayload.data?.items || []
    expect(afterResources.length).toBe(existingResources.length)
  } else {
    expect(workshopStream).toContain('agent_done')
    await expect.poll(async () => {
      const response = await page.request.get(`/api/resources?student_id=${encodeURIComponent(resourceStudentId)}`)
      const payload = await response.json()
      const items = payload.data?.resources || payload.data?.items || []
      return items.length
    }, { timeout: 30_000 }).toBeGreaterThan(existingResources.length)
  }

  await page.goto('/exercise', { waitUntil: 'domcontentloaded', timeout: 30_000 })
  const builderTab = page.locator('.practice-workshop-nav').getByRole('button', { name: /题库定制/ })
  await builderTab.click()
  await expect(builderTab).toHaveAttribute('aria-current', 'page')
  const generateStageBank = page.getByRole('button', { name: '生成阶段题库并开始学习' })
  await expect(generateStageBank).toBeEnabled({ timeout: 20_000 })
  const [stageBankResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/path/stage/questions') && response.request().method() === 'POST', { timeout: 60_000 }),
    generateStageBank.click(),
  ])
  const stageBankResult = await successfulApi(stageBankResponse)
  expect(stageBankResult.question_bank.type).toBe('question_bank')
  expect(stageBankResult.question_bank.meta.local_template).toBe(true)
  const question = page.locator('.exercise-question-focus')
  await expect(question).toBeVisible({ timeout: 30_000 })
  const firstChoice = page.locator('.exercise-options label:visible').first()
  if (await firstChoice.isVisible().catch(() => false)) await firstChoice.click()
  else await page.locator('.exercise-answer-input:visible').fill('空链表时同时更新 head 和 tail，非空链表连接 next 后更新 tail。')
  const [answerResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/exercise/answer') && response.request().method() === 'POST', { timeout: 30_000 }),
    page.getByRole('button', { name: /提交答案/ }).click(),
  ])
  const answerResult = await successfulApi(answerResponse)
  expect(typeof answerResult.correct).toBe('boolean')
  expect(Number(answerResult.stats?.total || 0)).toBeGreaterThan(0)

  const wrongBookTab = page.locator('.practice-workshop-nav').getByRole('button', { name: /错题本/ })
  await wrongBookTab.click()
  await expect(wrongBookTab).toHaveAttribute('aria-current', 'page')
  await expect(page.locator('body')).toContainText(/错题本|错题标签星系/)

  await page.goto('/multimodal', { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.getByRole('button', { name: '编程' }).click()
  await page.locator('.multi-composer textarea').fill(`为 ${resourceStudentId} 生成 Python 链表尾插边界测试案例，必须包含可运行代码和验收步骤。`)
  const sendButton = page.locator('.multi-send')
  await expect(sendButton).toBeEnabled()
  const [multimodalResponse] = await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/multimodal/code-case/stream') && response.request().method() === 'POST', { timeout: 120_000 }),
    sendButton.click(),
  ])
  expect(multimodalResponse.ok()).toBeTruthy()
  const multimodalStream = await multimodalResponse.text()
  if (/"event"\s*:\s*"error"/.test(multimodalStream)) {
    expect(multimodalStream).toContain('代码案例生成模型尚未配置')
    await expect(page.locator('.multi-message')).toContainText('代码案例生成模型尚未配置')
  } else {
    expect(multimodalStream).toMatch(/"event"\s*:\s*"final"/)
    await expect(page.locator('.multi-message')).not.toContainText('代码案例生成模型尚未配置')
  }
})
