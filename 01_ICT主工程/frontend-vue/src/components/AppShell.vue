<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  BrainCircuit,
  ChartNoAxesCombined,
  ClipboardCheck,
  Eye,
  EyeOff,
  GraduationCap,
  LayoutDashboard,
  LockKeyhole,
  Map,
  MessageCircleQuestion,
  Mic,
  Network,
  ShieldCheck,
  Smartphone,
  Settings,
  UserRound,
  X,
} from 'lucide-vue-next'
import { useStudent } from '@/composables/useStudent'
import { AUTHED_STORAGE_KEY, useAuth } from '@/composables/useAuth'
import { apiGet, apiPost } from '@/utils/api'
import ConnectionNotice from '@/components/ConnectionNotice.vue'

type NavItem = {
  to: string
  label: string
  desc: string
  icon: typeof LayoutDashboard
}

const route = useRoute()
const router = useRouter()
const authStorageKey = AUTHED_STORAGE_KEY
const isAuthed = ref(typeof window !== 'undefined' && sessionStorage.getItem(authStorageKey) === '1')
const phone = ref('')
const password = ref('')
const captcha = ref('')
const showPassword = ref(false)
const loginError = ref('')

// 4 位随机验证码：去掉易混淆字符 I O 0 1，字母大写；每个字符随机旋转+上下错位
type CaptchaChar = { ch: string; rotate: number; offsetY: number }
function genCaptcha(): CaptchaChar[] {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  return Array.from({ length: 4 }, () => ({
    ch: chars.charAt(Math.floor(Math.random() * chars.length)),
    rotate: Math.floor(Math.random() * 21) - 10,
    offsetY: Math.floor(Math.random() * 9) - 4,
  }))
}
const captchaChars = ref<CaptchaChar[]>(genCaptcha())
function refreshCaptcha() {
  captchaChars.value = genCaptcha()
  captcha.value = ''
  loginError.value = ''
}
const settingsOpen = ref(false)
const settingsMenuRef = ref<HTMLElement | null>(null)
const settingsTriggerRef = ref<HTMLButtonElement | null>(null)
const settingsPanelRef = ref<HTMLElement | null>(null)
const { studentId, major, goals } = useStudent()
const { authRequired, loadAuthConfig, getSessionToken, setSessionToken, clearSessionToken } = useAuth()
const studentIdInput = ref('')
const studentCredential = ref('')
const serverCaptchaId = ref('')
const serverCaptchaImage = ref('')
const loginPending = ref(false)

// 鉴权开态：验证码由后端签发（SVG 图片），点击刷新；关态沿用本地生成验证码。
async function refreshServerCaptcha() {
  captcha.value = ''
  loginError.value = ''
  const resp = await apiGet<{ captcha_id: string; image: string }>('/api/auth/captcha')
  if (resp.success && resp.data) {
    serverCaptchaId.value = resp.data.captcha_id
    serverCaptchaImage.value = resp.data.image
  } else {
    serverCaptchaId.value = ''
    serverCaptchaImage.value = ''
    loginError.value = '验证码获取失败，请点击验证码重试'
  }
}

watch(authRequired, (required) => {
  if (required && !serverCaptchaId.value) void refreshServerCaptcha()
  if (required && !getSessionToken()) {
    isAuthed.value = false
    sessionStorage.removeItem(authStorageKey)
  }
})

const nav: NavItem[] = [
  { to: '/', label: '总控首页', desc: '录屏演示主入口', icon: LayoutDashboard },
  { to: '/profile', label: '用户画像', desc: '对话式动态画像', icon: GraduationCap },
  { to: '/workshop', label: '资源工坊', desc: '多智能体协同生成', icon: BrainCircuit },
  { to: '/path', label: '路径推送', desc: '个性化步骤与资源推送', icon: Map },
  { to: '/exercise', label: '练习诊断', desc: '答题进度与错题诊断', icon: ClipboardCheck },
  { to: '/knowledge', label: '知识中枢', desc: '课程检索与知识图谱', icon: Network },
  { to: '/multimodal', label: '多模态实验室', desc: '视频、代码、语音资源', icon: Mic },
  { to: '/tutor', label: '智能辅导', desc: '多模态即时答疑', icon: MessageCircleQuestion },
  { to: '/evaluate', label: '评估进化', desc: '学习效果追踪与闭环优化', icon: ChartNoAxesCombined },
]

const current = computed(() => nav.find((n) => n.to === route.path) || nav[0])

async function submitLogin() {
  loginError.value = ''
  if (authRequired.value) {
    await submitLoginAuthed()
    return
  }
  if (!/^1\d{10}$/.test(phone.value.trim())) {
    loginError.value = '请输入 11 位手机号'
    return
  }
  if (password.value !== 'demo123') {
    loginError.value = '测试密码为 demo123'
    return
  }
  // 字母不区分大小写
  const codeStr = captchaChars.value.map((c) => c.ch).join('')
  if (captcha.value.trim().toUpperCase() !== codeStr.toUpperCase()) {
    refreshCaptcha()
    loginError.value = '验证码不正确，请输入新验证码'
    return
  }
  isAuthed.value = true
  sessionStorage.setItem(authStorageKey, '1')
  refreshCaptcha()
}

// 鉴权开态登录：学号 + 服务端验证码 → 后端签发绑定该学号的会话令牌。
async function submitLoginAuthed() {
  const sid = studentIdInput.value.trim()
  if (!sid) {
    loginError.value = '请输入学号'
    return
  }
  if (!studentCredential.value) {
    loginError.value = '请输入登录凭据'
    return
  }
  if (!captcha.value.trim()) {
    loginError.value = '请输入验证码'
    return
  }
  if (!serverCaptchaId.value) {
    await refreshServerCaptcha()
    return
  }
  loginPending.value = true
  const resp = await apiPost<{ student_id: string; token: string; expires_at: number }>('/api/auth/login', {
    student_id: sid,
      credential: studentCredential.value,
    captcha_id: serverCaptchaId.value,
    captcha_code: captcha.value.trim(),
  })
  loginPending.value = false
  if (!resp.success || !resp.data?.token) {
    void refreshServerCaptcha()
    loginError.value = resp.error?.message || '登录失败，请重试'
    return
  }
  const studentIdChanged = sid !== studentId.value
  setSessionToken(resp.data.token)
  studentId.value = resp.data.student_id
  isAuthed.value = true
  sessionStorage.setItem(authStorageKey, '1')
  captcha.value = ''
  studentIdInput.value = ''
  studentCredential.value = ''
  if (studentIdChanged) {
    // 学号从默认 learner-* 换成登录学号：整页刷新让各页按新学号重新取数
    window.location.reload()
  }
}

function logout() {
  sessionStorage.removeItem(authStorageKey)
  clearSessionToken()
  isAuthed.value = false
  settingsOpen.value = false
  void router.replace('/')
}

async function toggleSettings() {
  if (settingsOpen.value) {
    settingsOpen.value = false
    return
  }
  settingsOpen.value = true
  await nextTick()
  const initialFocus = settingsPanelRef.value?.querySelector<HTMLElement>('input, textarea')
    || settingsPanelRef.value?.querySelector<HTMLElement>('button, a')
  initialFocus?.focus()
}

function closeSettings(restoreFocus = false) {
  if (!settingsOpen.value) return
  settingsOpen.value = false
  if (restoreFocus) {
    void nextTick(() => settingsTriggerRef.value?.focus())
  }
}

function handleSettingsKeydown(event: KeyboardEvent) {
  if (settingsOpen.value && event.key === 'Escape') {
    event.preventDefault()
    closeSettings(true)
  }
}

function handleOutsidePointerDown(event: PointerEvent) {
  if (settingsOpen.value && !settingsMenuRef.value?.contains(event.target as Node | null)) {
    closeSettings()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleSettingsKeydown)
  document.addEventListener('pointerdown', handleOutsidePointerDown)
  void loadAuthConfig()
  if (!isAuthed.value && route.path !== '/') {
    void router.replace('/')
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleSettingsKeydown)
  document.removeEventListener('pointerdown', handleOutsidePointerDown)
})
</script>

<template>
  <div class="portal-shell" :class="{ 'portal-shell-locked': !isAuthed }">
    <header class="portal-header">
      <RouterLink class="portal-brand" to="/">
        <span class="portal-brand-mark">
          <img src="/assets/huisi-learning-logo.png" alt="慧思智学平台标志" />
        </span>
        <span class="portal-brand-copy">
          <strong>慧思智学平台</strong>
          <small>个性化智慧学习平台</small>
        </span>
      </RouterLink>

      <nav class="portal-nav" aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="portal-nav-link"
          :title="item.desc"
        >
          <component :is="item.icon" :size="20" stroke-width="2" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div ref="settingsMenuRef" class="portal-user-menu">
        <button ref="settingsTriggerRef" class="portal-user-trigger" type="button" aria-controls="portal-settings-panel" :aria-expanded="settingsOpen" aria-label="打开用户设置" @click="toggleSettings">
          <UserRound :size="17" />
          <span>用户设置</span>
          <Settings :size="15" />
        </button>
        <section v-if="settingsOpen" id="portal-settings-panel" ref="settingsPanelRef" class="portal-settings-panel" aria-label="用户设置面板">
          <header><strong>用户设置</strong><button type="button" aria-label="关闭用户设置" @click="closeSettings(true)"><X :size="17" /></button></header>
            <label><span>学习者 ID</span><input v-model="studentId" autocomplete="off" :disabled="authRequired" /></label>
          <label><span>专业方向</span><input v-model="major" placeholder="例如：软件工程" autocomplete="off" /></label>
          <label><span>学习目标</span><textarea v-model="goals" rows="3" placeholder="描述希望达成的能力或成果"></textarea></label>
          <footer><RouterLink to="/profile" @click="closeSettings()">完善用户画像</RouterLink><button type="button" @click="logout">退出登录</button></footer>
        </section>
      </div>
    </header>

    <ConnectionNotice />

    <main class="portal-main" :class="{ 'portal-main-home': route.path === '/' }">
      <slot />
    </main>

    <section v-if="!isAuthed" class="login-gate" aria-label="登录注册">
      <div class="bg-float-item"></div>
      <div class="bg-float-item"></div>
      <div class="bg-float-item"></div>
      <div class="bg-float-item"></div>
      <div class="bg-float-item"></div>
      <div class="bg-float-item"></div>
      <div class="bg-float-item"></div>
      <div class="bg-float-item"></div>
      <form class="login-card" @submit.prevent="submitLogin">
        <div class="login-title">
          <h1>登录 / 注册</h1>
          <p>AI个性化学习智能体</p>
        </div>

        <label class="login-field" v-if="!authRequired">
          <Smartphone :size="28" stroke-width="2.2" />
          <input v-model="phone" inputmode="numeric" maxlength="11" placeholder="手机号" autocomplete="tel" />
        </label>

        <label class="login-field login-field-active" v-else>
          <UserRound :size="28" stroke-width="2.2" />
          <input v-model="studentIdInput" placeholder="学号" autocomplete="username" aria-label="学号" />
        </label>
        <label v-if="authRequired" class="login-field login-field-active">
          <LockKeyhole :size="28" stroke-width="2.2" />
          <input v-model="studentCredential" type="password" placeholder="登录凭据" autocomplete="current-password" aria-label="登录凭据" />
        </label>

        <label class="login-field login-field-active" v-if="!authRequired">
          <LockKeyhole :size="28" stroke-width="2.2" />
          <input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="密码"
            autocomplete="current-password"
          />
          <button class="login-eye" type="button" @click="showPassword = !showPassword" :aria-label="showPassword ? '隐藏密码' : '显示密码'">
            <EyeOff v-if="showPassword" :size="26" stroke-width="2.2" />
            <Eye v-else :size="26" stroke-width="2.2" />
          </button>
        </label>

        <div class="login-field login-captcha-field">
          <ShieldCheck :size="30" stroke-width="2.15" />
          <input v-model="captcha" maxlength="4" placeholder="验证码" aria-label="验证码" autocomplete="off" />
          <button v-if="authRequired" type="button" class="captcha-box captcha-clickable" aria-label="刷新验证码" title="看不清？点击刷新验证码" @click="refreshServerCaptcha"><img v-if="serverCaptchaImage" :src="serverCaptchaImage" alt="验证码" style="width: 100%; height: 100%; object-fit: contain;" /></button>
          <button v-else type="button" class="captcha-box captcha-clickable" aria-label="刷新验证码" title="看不清？点击切换验证码" @click="refreshCaptcha"><span v-for="(item, i) in captchaChars" :key="i" class="captcha-char" :style="`transform: rotate(${item.rotate}deg) translateY(${item.offsetY}px);`">{{ item.ch }}</span></button>
        </div>

        <button class="login-submit" type="submit">{{ loginPending ? '登录中…' : '登录并进入系统' }}</button>

        <div class="login-tip">
          <span v-if="!authRequired">测试账号：任意 11 位手机号，密码 demo123（验证码点击可刷新，字母不区分大小写）</span>
            <span v-else>请输入学号、登录凭据和验证码；账户由管理员配置。</span>
          <strong v-if="loginError">{{ loginError }}</strong>
        </div>
      </form>
    </section>
  </div>
</template>
