import { ref } from 'vue'
import { apiGet } from '@/utils/api'

// 多用户隔离（会话级）：后端 AUTH_REQUIRED=1 时，登录接口签发绑定学号的
// 会话令牌，所有 API 请求以 X-Session-Token 头携带（见 utils/api.ts）；
// 关态（默认）不产生任何影响——不发令牌、不校验、登录门走原演示流程。
const tokenKey = 'las_session_token'
export const AUTHED_STORAGE_KEY = 'zx-resource-agent-authed'

export const authRequired = ref(false)
const authConfigLoaded = ref(false)

/** 拉取后端鉴权开关（每个应用实例只请求一次；失败按关态处理，不打断页面）。 */
export async function loadAuthConfig(): Promise<void> {
  if (authConfigLoaded.value) return
  authConfigLoaded.value = true
  const resp = await apiGet<{ auth_required: boolean }>('/api/auth/config')
  if (resp.success && resp.data) authRequired.value = Boolean(resp.data.auth_required)
}

export function getSessionToken(): string {
  return typeof window === 'undefined' ? '' : localStorage.getItem(tokenKey) || ''
}

export function setSessionToken(token: string) {
  localStorage.setItem(tokenKey, token)
}

export function clearSessionToken() {
  localStorage.removeItem(tokenKey)
}

export function useAuth() {
  return {
    authRequired,
    loadAuthConfig,
    getSessionToken,
    setSessionToken,
    clearSessionToken,
  }
}
