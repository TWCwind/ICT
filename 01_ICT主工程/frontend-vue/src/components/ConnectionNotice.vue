<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const offline = ref(false)
const navigationFailed = ref(false)
const checking = ref(false)
const recovered = ref(false)
let timer: ReturnType<typeof setInterval> | undefined
let controller: AbortController | undefined
let disposed = false
let removeRouterError: (() => void) | undefined

async function checkConnection() {
  if (checking.value || disposed) return
  checking.value = true
  controller = new AbortController()
  const timeout = setTimeout(() => controller?.abort(), 4000)
  try {
    const response = await fetch('/api/health', { cache: 'no-store', signal: controller.signal })
    const body = await response.json()
    if (!response.ok || body.success !== true) throw new Error('Service unavailable')
    if (!disposed) {
      if (offline.value) recovered.value = true
      offline.value = false
    }
  } catch {
    if (!disposed) {
      offline.value = true
      recovered.value = false
    }
  } finally {
    clearTimeout(timeout)
    checking.value = false
  }
}

function refreshPage() { window.location.reload() }
function checkOnFocus() { void checkConnection() }
onMounted(() => {
  removeRouterError = router.onError(() => { navigationFailed.value = true })
  void checkConnection()
  timer = setInterval(checkOnFocus, 10000)
  window.addEventListener('focus', checkOnFocus)
  window.addEventListener('online', checkOnFocus)
})
onUnmounted(() => {
  disposed = true
  clearInterval(timer)
  controller?.abort()
  removeRouterError?.()
  window.removeEventListener('focus', checkOnFocus)
  window.removeEventListener('online', checkOnFocus)
})
</script>

<template>
  <aside v-if="offline || navigationFailed || recovered" class="connection-notice" role="status" aria-live="polite" aria-label="服务连接状态">
    <div>
      <strong>{{ offline ? '本地服务暂时未连接' : navigationFailed ? '页面未能加载' : '服务已恢复连接' }}</strong>
      <p>{{ offline ? '当前页面可能是之前保留的页面。请保持路演启动窗口运行，并使用启动窗口显示的网址。操作未成功时请勿重复提交。' : '请刷新页面重新加载数据；刷新前请保存尚未提交的输入。' }}</p>
    </div>
    <button v-if="offline" type="button" :disabled="checking" @click="checkConnection">{{ checking ? '正在检查…' : '重新检查连接' }}</button>
    <button v-else type="button" @click="refreshPage">刷新页面</button>
  </aside>
</template>

<style scoped>
.connection-notice { position: relative; z-index: 2000; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 24px; background: #fff7e6; color: #593b0c; border-bottom: 1px solid #e7c782; }
.connection-notice strong { font-size: 16px; }
.connection-notice p { margin: 4px 0 0; font-size: 14px; line-height: 1.6; }
.connection-notice button { flex-shrink: 0; min-height: 44px; padding: 8px 16px; border: 1px solid #876021; border-radius: 8px; color: #593b0c; background: white; cursor: pointer; }
.connection-notice button:focus-visible { outline: 3px solid #2563eb; outline-offset: 3px; }
@media (max-width: 600px) { .connection-notice { flex-direction: column; align-items: stretch; padding: 12px 16px; gap: 8px; } }
</style>
