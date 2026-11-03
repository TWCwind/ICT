import { expect, test } from '@playwright/test'

test('tutor exposes the available local voice and avatar surface truthfully', async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem('zx-resource-agent-authed', '1')
    localStorage.setItem('las_student_id', 'demo_user_001')
  })
  await page.goto('/tutor')
  const surface = page.locator('.tutor-video-shell .tb-shell, .tutor-video-shell .realtime-tutor-panel')
  await expect(surface).toBeVisible({ timeout: 10_000 })
  const configResponse = await page.request.get('/api/voice/realtime/config')
  const config = await configResponse.json()
  if (config?.data?.enabled) {
    await expect(page.locator('.realtime-tutor-panel .digital-human-rig')).toBeVisible()
  } else {
    await expect(page.locator('.tutor-video-shell .tb-avatar')).toBeVisible()
    await expect(page.locator('.tutor-video-shell')).toContainText('语音辅导（浏览器模式）')
    await expect(page.locator('.tutor-video-shell')).not.toContainText(/已连接云端|数字人服务已连接/)
  }
})
