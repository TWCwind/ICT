import { test } from '@playwright/test'

// 快速冒烟：验证真实登录、主导航点击、设置面板在当前真实服务(5173+8000)上的行为。

test('冒烟：真实登录 + 主导航 + 设置面板', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)) })
  page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${String(e).slice(0, 200)}`))

  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.waitForTimeout(2000)

  const gate = await page.locator('.login-gate').isVisible().catch(() => false)
  console.log(`[smoke] login-gate visible: ${gate}`)
  console.log(`[smoke] url before login: ${page.url()}`)

  // 未登录点击主导航：观察是否被遮罩拦截
  const navFirst = page.locator('.portal-nav-link').first()
  if (await navFirst.isVisible().catch(() => false)) {
    const before = page.url()
    await navFirst.click({ timeout: 5000, noWaitAfter: true }).catch((e) => console.log(`[smoke] nav click err: ${String(e).slice(0, 120)}`))
    await page.waitForTimeout(500)
    console.log(`[smoke] nav click while gated: ${before} -> ${page.url()}`)
  } else {
    console.log('[smoke] portal-nav-link not visible')
  }

  // 真实登录
  await page.locator('.login-field input[placeholder="手机号"]').fill('13800001234')
  await page.locator('.login-field input[placeholder="密码"]').fill('demo123')
  await page.locator('.login-field input[placeholder="验证码"]').fill('2VV3')
  await page.locator('.login-submit').click({ timeout: 5000, noWaitAfter: true })
  await page.waitForTimeout(3000)
  const gateAfter = await page.locator('.login-gate').isVisible().catch(() => false)
  console.log(`[smoke] login-gate after submit: ${gateAfter}`)
  const tip = await page.locator('.login-tip strong').innerText().catch(() => '')
  console.log(`[smoke] login tip: ${tip}`)

  // 登录后主导航逐个点击
  for (const route of ['/profile', '/workshop', '/exercise', '/knowledge', '/path', '/evaluate']) {
    await page.locator('.portal-nav-link', { hasText: '' }).count().catch(() => 0)
    const link = page.locator(`.portal-nav-link[href="${route}"]`)
    if (!(await link.isVisible().catch(() => false))) {
      console.log(`[smoke] nav link ${route}: NOT VISIBLE`)
      continue
    }
    await link.click({ timeout: 5000, noWaitAfter: true }).catch((e) => console.log(`[smoke] nav ${route} click err: ${String(e).slice(0, 120)}`))
    await page.waitForTimeout(1500)
    const mainVisible = await page.locator('.portal-main').isVisible().catch(() => false)
    const heading = await page.locator('.portal-main h1').first().innerText().catch(() => '')
    console.log(`[smoke] nav -> ${route}: url=${page.url()} main=${mainVisible} h1=${heading.trim().slice(0, 30)}`)
  }

  // 用户设置面板
  const trigger = page.locator('.portal-user-trigger')
  if (await trigger.isVisible().catch(() => false)) {
    await trigger.click({ timeout: 5000, noWaitAfter: true }).catch((e) => console.log(`[smoke] settings err: ${String(e).slice(0, 120)}`))
    await page.waitForTimeout(600)
    const panel = await page.locator('.portal-settings-panel').isVisible().catch(() => false)
    console.log(`[smoke] settings panel visible: ${panel}`)
  } else {
    console.log('[smoke] portal-user-trigger NOT VISIBLE')
  }

  console.log(`[smoke] console errors: ${consoleErrors.length}`)
  consoleErrors.slice(0, 10).forEach((e) => console.log(`[smoke][console] ${e}`))
})
