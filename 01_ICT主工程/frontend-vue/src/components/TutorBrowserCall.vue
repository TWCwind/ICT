<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Camera, CameraOff, Loader2, Mic, MicOff, Pause, Play, Send, Volume2, VolumeX } from 'lucide-vue-next'
import MarkdownContent from '@/components/MarkdownContent.vue'

type Phase = 'idle' | 'listening' | 'thinking' | 'speaking'

type Turn = { id: number; role: 'user' | 'assistant'; text: string; pending?: boolean }

const studentId = computed(() => localStorage.getItem('las_student_id') || 'demo');

const phase = ref<Phase>('idle')
const errorText = ref('')
const input = ref('')
const turns = ref<Turn[]>([])
const transcriptEl = ref<HTMLElement | null>(null)

/** 对话记录始终停在最后一条（恢复历史记录、新增问答时都滚到底）。 */
function scrollTranscript() {
  nextTick(() => {
    const el = transcriptEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}
const muted = ref(false)
const paused = ref(false)
const speakActive = ref(false)
const recognitionSupported = ref(true)
const speakSupported = ref(true)

type VoiceOption = { id: string; label: string; voiceURI: string; pitch: number; rate: number }

const VOICE_STORE_KEY = 'tutor_browser_voice_v1'
const voiceOptions = ref<VoiceOption[]>([])
const voiceChoice = ref('female-bright')
const saveStatus = ref('')
let sessionSavedAt = ''

const FEMALE_HINT = /xiaoxiao|xiaoyi|huihui|yaoyao|yaoyao|female|女/i
const MALE_HINT = /yunjian|yunxi|yunyang|kangkang|male|男/i

function firstChineseVoice(): string {
  if (typeof window === 'undefined' || !window.speechSynthesis) return ''
  const voices = window.speechSynthesis.getVoices()
  const zh = voices.find((v) => /^zh[-_]CN/i.test(v.lang)) || voices.find((v) => /^zh/i.test(v.lang))
  return zh ? zh.voiceURI : ''
}

function zhVoiceList(): SpeechSynthesisVoice[] {
  if (typeof window === 'undefined' || !window.speechSynthesis) return []
  return window.speechSynthesis.getVoices().filter((v) => /^zh/i.test(v.lang))
}

function buildVoiceOptions() {
  const voices = zhVoiceList()
  const female = voices.find((v) => FEMALE_HINT.test(v.name)) || voices[0]
  const male = voices.find((v) => MALE_HINT.test(v.name)) || voices.find((v) => v !== female) || voices[0]
  const presets: VoiceOption[] = [
    { id: 'female-bright', label: '女声 · 清亮', voiceURI: female?.voiceURI || '', pitch: 1.12, rate: 1.04 },
    { id: 'female-warm', label: '女声 · 温和', voiceURI: female?.voiceURI || '', pitch: 0.98, rate: 0.98 },
    { id: 'male-calm', label: '男声 · 沉稳', voiceURI: male?.voiceURI || '', pitch: 0.95, rate: 1.0 },
    { id: 'male-deep', label: '男声 · 浑厚', voiceURI: male?.voiceURI || '', pitch: 0.8, rate: 0.95 },
  ]
  const realVoices: VoiceOption[] = voices.slice(0, 8).map((v, index) => {
    const name = v.name.replace(/^Microsoft\s*/i, '').replace(/\s*-\s*Chinese.*$/i, '').trim() || `音色 ${index + 1}`
    const label = MALE_HINT.test(v.name) ? `男声 · ${name}` : FEMALE_HINT.test(v.name) ? `女声 · ${name}` : `中文音色 · ${name}`
    return { id: `voice:${v.voiceURI}`, label, voiceURI: v.voiceURI, pitch: 1, rate: 1.02 }
  })
  voiceOptions.value = [...presets, ...realVoices]
  if (!voiceOptions.value.some((item) => item.id === voiceChoice.value)) {
    voiceChoice.value = realVoices[0]?.id || 'female-bright'
  }
}

function currentVoiceOption(): VoiceOption {
  return voiceOptions.value.find((item) => item.id === voiceChoice.value) || voiceOptions.value[0] || {
    id: 'female-bright',
    label: '女声 · 清亮',
    voiceURI: '',
    pitch: 1.15,
    rate: 1.02,
  }
}

function selectVoice(id: string) {
  voiceChoice.value = id
  try {
    localStorage.setItem(VOICE_STORE_KEY, id)
  } catch {
    /* ignore */
  }
}

function previewVoice() {
  stopSpeaking()
  speak('同学们好，我是你的学习助手，接下来由我为你讲解这道题。', true)
}

function onVoiceChange(event: Event) {
  const target = event.target as HTMLSelectElement | null
  if (target) selectVoice(target.value)
}

function togglePauseOnly() {
  if (!speakActive.value) return
  if (paused.value) resumeSpeaking()
  else pauseSpeaking()
}

let recognition: any = null
let seq = 0
let currentUtterance: SpeechSynthesisUtterance | null = null
let speechQueue: string[] = []
let speechIndex = 0
let speechGeneration = 0

const cameraOn = ref(false)
const cameraError = ref('')
const cameraErrorDetail = ref('')
const cameraOpening = ref(false)
const videoEl = ref<HTMLVideoElement | null>(null)
let cameraStream: MediaStream | null = null

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop())
    cameraStream = null
  }
  if (videoEl.value) videoEl.value.srcObject = null
  cameraOn.value = false
}

async function startCamera() {
  cameraError.value = ''
  cameraErrorDetail.value = ''
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraError.value = '当前浏览器不支持摄像头调用，请使用 Edge / Chrome 并允许摄像头权限。'
    return
  }
  if (cameraStream) stopCamera()
  cameraOpening.value = true
  const attempts: MediaStreamConstraints[] = [
    { video: { width: 960, height: 540 }, audio: false },
    { video: { facingMode: 'user' }, audio: false },
    { video: true, audio: false },
  ]
  let stream: MediaStream | null = null
  let lastError: any = null
  for (const constraints of attempts) {
    try {
      stream = await navigator.mediaDevices.getUserMedia(constraints)
      break
    } catch (error: any) {
      lastError = error
      // 权限被拒/没有设备时换参数也没用，直接跳出给出针对性提示
      const name = String(error?.name || '')
      if (name === 'NotAllowedError' || name === 'SecurityError' || name === 'NotFoundError') break
    }
  }
  cameraOpening.value = false
  if (!stream) {
    await explainCameraFailure(lastError)
    return
  }
  cameraStream = stream
  if (videoEl.value) {
    videoEl.value.srcObject = stream
    await videoEl.value.play().catch(() => undefined)
  }
  cameraOn.value = true
  stream.getVideoTracks().forEach((track) => {
    track.addEventListener('ended', () => {
      cameraOn.value = false
      cameraStream = null
    })
  })
}

/** 把浏览器抛出的错误翻译成用户能动手处理的中文，并尽量给出真实原因。 */
async function explainCameraFailure(error: any) {
  const name = String(error?.name || '')
  const message = String(error?.message || '')
  cameraErrorDetail.value = name ? `${name}${message ? ` · ${message}` : ''}` : ''
  let devices = 0
  try {
    const list = await navigator.mediaDevices?.enumerateDevices?.()
    devices = (list || []).filter((item) => item.kind === 'videoinput').length
  } catch {
    devices = 0
  }
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    cameraError.value = '摄像头权限被拒绝：点地址栏左侧的锁形图标 → 摄像头 → 允许，然后点「重试」。'
    return
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    cameraError.value = '没有检测到摄像头设备：请确认摄像头已插好或笔记本自带相机未在设备管理器里被禁用。'
    return
  }
  if (name === 'NotReadableError' || name === 'TrackStartError' || name === 'AbortError') {
    cameraError.value = devices
      ? `摄像头被占用或系统未放行（检测到 ${devices} 个摄像头）：关掉会议软件/其他页面的摄像头，并检查「Windows 设置 → 隐私和安全性 → 相机」允许桌面应用访问，然后点「重试」。`
      : '摄像头无法访问：系统里没有可用的摄像头设备，或被隐私设置拦住了。'
    return
  }
  cameraError.value = `摄像头打开失败：${message || name || '未知错误'}`
}

function toggleCamera() {
  if (cameraOn.value) stopCamera()
  else void startCamera()
}

const busy = computed(() => phase.value === 'thinking')
const statusText = computed(() => {
  if (phase.value === 'listening') return '正在聆听，请说话…'
  if (phase.value === 'thinking') return 'AI 老师正在组织回答…'
  if (phase.value === 'speaking') return 'AI 老师正在朗读…'
  return '点击麦克风开始说话，或直接打字提问'
})

function plainText(markdown: string) {
  return String(markdown || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!\[[^\]]*]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/[*_>~]/g, '')
    .replace(/\|/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function pickAnswer(payload: any) {
  const data = payload?.data || {}
  const markdown = typeof data.markdown === 'string' ? data.markdown : ''
  if (markdown.trim()) return markdown
  const answer = data.answer
  if (typeof answer === 'string') return answer
  if (answer && typeof answer.text === 'string') return answer.text
  return ''
}

function toggleMute() {
  muted.value = !muted.value
  // 静音 = 把音量调到 0：不打断、不重发，朗读进度继续往前走
  const target = muted.value ? 0 : 1
  if (currentUtterance) {
    try {
      currentUtterance.volume = target
    } catch {
      /* 有的引擎不支持中途改音量 */
    }
  }
  if (!speakActive.value || paused.value) return
  // 引擎不会对「正在播的这一句」应用音量变化，只能等它播完。
  // 为了点下去立刻生效，这里把当前这一小段（≤12 字）用新音量重发一次：
  //   静音方向 = 无声重走一小段（听不出来）；开声方向 = 立刻出声，不回到开头。
  speechGeneration += 1
  window.speechSynthesis.cancel()
  currentUtterance = null
  playFrom(Math.min(speechIndex, Math.max(0, speechQueue.length - 1)), speechGeneration)
}

function stopSpeaking() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  speechGeneration += 1
  window.speechSynthesis.cancel()
  currentUtterance = null
  speechQueue = []
  speechIndex = 0
  paused.value = false
  speakActive.value = false
  if (phase.value === 'speaking') phase.value = 'idle'
}

function splitSentences(text: string): string[] {
  const clean = plainText(text)
  if (!clean) return []
  const raw = clean.split(/(?<=[。！？!?；;，,、：:])\s*/g).map((item) => item.trim()).filter(Boolean)
  const merged: string[] = []
  let buffer = ''
  for (const piece of raw) {
    const candidate = buffer ? `${buffer}${piece}` : piece
    // 切得细一点：静音/切换音色时需要重读当前片段，片段越短越不容易察觉
    if (candidate.length >= 12) {
      merged.push(candidate)
      buffer = ''
    } else {
      buffer = candidate
    }
  }
  if (buffer) merged.push(buffer)
  return merged.length ? merged : [clean]
}

function resolveVoice(option: VoiceOption): SpeechSynthesisVoice | undefined {
  const voices = zhVoiceList()
  if (option.voiceURI) {
    const hit = voices.find((v) => v.voiceURI === option.voiceURI)
    if (hit) return hit
  }
  return voices.find((v) => /^zh[-_]CN/i.test(v.lang)) || voices[0]
}

function playFrom(index: number, generation: number) {
  if (generation !== speechGeneration) return
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  if (index >= speechQueue.length) {
    speechQueue = []
    speechIndex = 0
    paused.value = false
    speakActive.value = false
    if (phase.value === 'speaking') phase.value = 'idle'
    return
  }
  speechIndex = index
  const option = currentVoiceOption()
  const utterance = new SpeechSynthesisUtterance(speechQueue[index])
  utterance.lang = 'zh-CN'
  utterance.rate = option.rate
  utterance.pitch = option.pitch
  utterance.volume = muted.value ? 0 : 1
  const voice = resolveVoice(option)
  if (voice) utterance.voice = voice
  const advance = () => {
    if (generation !== speechGeneration) return
    playFrom(index + 1, generation)
  }
  utterance.onend = advance
  utterance.onerror = advance
  currentUtterance = utterance
  phase.value = 'speaking'
  window.speechSynthesis.speak(utterance)
}

function speak(text: string, force = false) {
  if (!speakSupported.value || typeof window === 'undefined' || !window.speechSynthesis) {
    phase.value = 'idle'
    return
  }
  const sentences = splitSentences(text)
  if (!sentences.length) {
    phase.value = 'idle'
    return
  }
  speechGeneration += 1
  window.speechSynthesis.cancel()
  speechQueue = sentences
  speechIndex = 0
  paused.value = false
  speakActive.value = true
  playFrom(0, speechGeneration)
}

function pauseSpeaking() {
  if (typeof window === 'undefined' || !window.speechSynthesis || !speechQueue.length || paused.value) return
  speechGeneration += 1
  paused.value = true
  window.speechSynthesis.cancel()
  currentUtterance = null
  if (phase.value === 'speaking') phase.value = 'idle'
}

function resumeSpeaking() {
  if (!speechQueue.length || !paused.value) return
  speechGeneration += 1
  paused.value = false
  window.speechSynthesis.cancel()
  playFrom(Math.min(speechIndex, speechQueue.length - 1), speechGeneration)
}

function togglePause() {
  togglePauseOnly()
}

async function ask(question: string) {
  const text = question.trim()
  if (!text || busy.value) return
  errorText.value = ''
  input.value = ''
  stopSpeaking()
  const userTurn: Turn = { id: ++seq, role: 'user', text }
  const replyTurn: Turn = { id: ++seq, role: 'assistant', text: '', pending: true }
  turns.value = [...turns.value, userTurn, replyTurn]
  scrollTranscript()
  phase.value = 'thinking'

  try {
    const response = await fetch('/api/tutor/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: studentId.value, question: text }),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok || payload?.success === false) {
      throw new Error(payload?.message || `辅导请求失败：HTTP ${response.status}`)
    }
    const answer = pickAnswer(payload)
    replyTurn.text = answer || '这次没有拿到有效回答，换个问法再试一次。'
    replyTurn.pending = false
    turns.value = [...turns.value]
    scrollTranscript()
    persistTurns()
    speak(replyTurn.text)
    if (phase.value === 'thinking') phase.value = 'idle'
    void saveSession()
  } catch (error: any) {
    replyTurn.pending = false
    replyTurn.text = error?.message || '辅导请求失败，请稍后重试。'
    turns.value = [...turns.value]
    persistTurns()
    errorText.value = replyTurn.text
    phase.value = 'idle'
  }
}

const micPermission = ref<'unknown' | 'granted' | 'denied' | 'insecure' | 'unsupported'>('unknown')

/** 先显式申请一次麦克风权限：这样浏览器会真的弹授权框，而不是 SpeechRecognition 静默失败。 */
async function ensureMicAccess(): Promise<boolean> {
  if (typeof window === 'undefined') return false
  if (!window.isSecureContext) {
    micPermission.value = 'insecure'
    errorText.value = '当前地址不是「安全上下文」，浏览器会直接禁用麦克风。请用 http://127.0.0.1:5173/tutor 打开本页（用局域网 IP 或公网域名打开时属于不安全来源）。'
    return false
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    micPermission.value = 'unsupported'
    errorText.value = '这个浏览器不支持麦克风采集，请用 Edge / Chrome，或直接打字提问。'
    return false
  }
  if (micPermission.value === 'granted') return true
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    stream.getTracks().forEach((track) => track.stop())
    micPermission.value = 'granted'
    return true
  } catch (error: any) {
    micPermission.value = 'denied'
    const name = String(error?.name || '')
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError' || name === 'SecurityError') {
      errorText.value = '麦克风被拒绝。点地址栏左侧的锁形/麦克风图标 → 把「麦克风」改成「允许」→ 刷新页面；若还不行，到 edge://settings/content/microphone 里允许 127.0.0.1，并在「Windows 设置 → 隐私和安全性 → 麦克风」里允许桌面应用访问麦克风。'
    } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      errorText.value = '没有检测到麦克风设备，请插上麦克风或使用带麦克风的摄像头，然后重试。'
    } else if (name === 'NotReadableError' || name === 'TrackStartError') {
      errorText.value = '麦克风被其他程序占用（会议软件、录屏软件等），关掉后再试。'
    } else {
      errorText.value = `麦克风打开失败：${name || '未知错误'}。可以先用文字提问。`
    }
    return false
  }
}

function startListening() {
  if (!recognition || busy.value) return
  errorText.value = ''
  stopSpeaking()
  if (!recognitionSupported.value) {
    errorText.value = '这个浏览器不支持语音识别，请用 Edge / Chrome，或直接打字提问。'
    return
  }
  void ensureMicAccess().then((granted) => {
    if (!granted) {
      phase.value = 'idle'
      return
    }
    try {
      recognition.start()
    } catch {
      phase.value = 'idle'
    }
  })
}

function stopListening() {
  if (!recognition) return
  try {
    recognition.stop()
  } catch {
    /* ignore */
  }
  if (phase.value === 'listening') phase.value = 'idle'
}

function toggleMic() {
  if (phase.value === 'listening') stopListening()
  else startListening()
}

function sendTyped() {
  void ask(input.value)
}

const TURN_STORE_KEY = () => `tutor_browser_turns_v1:${studentId.value}`
const SAVED_STORE_KEY = () => `tutor_browser_saved_v1:${studentId.value}`
let sessionStartedAt = new Date().toISOString()

function persistTurns() {
  try {
    const clean = turns.value.filter((t) => !t.pending).map((t) => ({ id: t.id, role: t.role, text: t.text }))
    localStorage.setItem(TURN_STORE_KEY(), JSON.stringify(clean))
  } catch {
    /* ignore */
  }
}

function restoreTurns() {
  try {
    const raw = localStorage.getItem(TURN_STORE_KEY())
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return
    const restored: Turn[] = parsed
      .filter((t: any) => t && typeof t.text === 'string' && (t.role === 'user' || t.role === 'assistant'))
      .map((t: any, index: number) => ({ id: Number(t.id) || index + 1, role: t.role, text: t.text }))
    turns.value = restored
    seq = restored.reduce((max, t) => Math.max(max, t.id), 0)
    if (restored.length) saveStatus.value = `已恢复上次的 ${restored.length} 条对话记录`
    scrollTranscript()
  } catch {
    /* ignore */
  }
}

function transcriptSignature(): string {
  const messages = turns.value.filter((t) => !t.pending && t.text.trim())
  if (!messages.length) return ''
  return `${messages.length}|${messages[messages.length - 1].text.slice(0, 60)}`
}

async function saveSession() {
  const signature = transcriptSignature()
  if (!signature) return
  let saved = ''
  try {
    saved = localStorage.getItem(SAVED_STORE_KEY()) || ''
  } catch {
    /* ignore */
  }
  if (saved === signature) return
  const messages = turns.value.filter((t) => !t.pending && t.text.trim())
  try {
    const response = await fetch('/api/tutor/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
      body: JSON.stringify({
        student_id: studentId.value,
        started_at: sessionStartedAt,
        ended_at: new Date().toISOString(),
        messages: messages.map((t) => ({ role: t.role, content: t.text, timestamp: new Date().toISOString() })),
        meta: { source: 'browser_voice_call' },
      }),
    })
    const payload = await response.json().catch(() => ({}))
    if (payload?.success) {
      try {
        localStorage.setItem(SAVED_STORE_KEY(), signature)
      } catch {
        /* ignore */
      }
      const weak = payload?.data?.analysis?.weak_points || []
      saveStatus.value = weak.length
        ? `已留痕：对话已存为学习证据（薄弱点：${weak.slice(0, 3).join('、')}）`
        : '已留痕：对话已存为学习证据'
    } else {
      saveStatus.value = '对话留痕保存失败，稍后会重试。'
    }
  } catch {
    saveStatus.value = '对话留痕保存失败（后端未连通）。'
  }
}

onMounted(() => {
  try {
    const savedVoice = localStorage.getItem(VOICE_STORE_KEY)
    if (savedVoice) voiceChoice.value = savedVoice
  } catch {
    /* ignore */
  }
  buildVoiceOptions()
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => buildVoiceOptions()
  }
  restoreTurns()
  const w = window as any
  const Recognition = w.SpeechRecognition || w.webkitSpeechRecognition
  speakSupported.value = typeof window !== 'undefined' && 'speechSynthesis' in window
  if (!Recognition) {
    recognitionSupported.value = false
    return
  }
  recognition = new Recognition()
  recognition.lang = 'zh-CN'
  recognition.continuous = false
  recognition.interimResults = false
  recognition.maxAlternatives = 1
  recognition.onstart = () => {
    phase.value = 'listening'
  }
  recognition.onerror = (event: any) => {
    phase.value = 'idle'
    const code = String(event?.error || '')
    if (code === 'not-allowed' || code === 'service-not-allowed') {
      errorText.value = '浏览器没有麦克风权限：点地址栏左侧图标把「麦克风」设为允许后刷新；识别服务本身就要求联网，也可以用文字提问。'
    } else if (code === 'no-speech') {
      errorText.value = '没有听到声音，请再说一次。'
    } else if (code === 'network') {
      errorText.value = '语音识别服务连不上（Edge 的识别需要联网），可以改用文字提问。'
    } else {
      errorText.value = `语音识别失败：${code || '未知错误'}`
    }
  }
  recognition.onend = () => {
    if (phase.value === 'listening') phase.value = 'idle'
  }
  recognition.onresult = (event: any) => {
    const transcript = String(event?.results?.[0]?.[0]?.transcript || '').trim()
    if (transcript) void ask(transcript)
    else phase.value = 'idle'
  }
})

onBeforeUnmount(() => {
  persistTurns()
  void saveSession()
  stopCamera()
  if (recognition) {
    try {
      recognition.abort()
    } catch {
      /* ignore */
    }
    recognition = null
  }
  if (typeof window !== 'undefined' && window.speechSynthesis) window.speechSynthesis.cancel()
  currentUtterance = null
})
</script>

<template>
  <div class="tb-shell">
    <header class="tb-head">
      <div>
        <strong><Mic :size="16" /> 语音辅导（浏览器模式）</strong>
        <p>实时语音通道未配置，已切换为浏览器语音：Edge 内置识别把你说的话转成文字，AI 回答后用系统语音朗读。</p>
      </div>
      <span class="tb-chip" :class="`is-${phase}`">{{ statusText }}</span>
    </header>

    <div class="tb-body">
      <div class="tb-stage">
        <p class="tb-col-title">AI 辅导老师</p>
        <div class="tb-avatar" :class="{ 'is-active': phase !== 'idle' }">
          <span class="tb-avatar-ring"></span>
          <span class="tb-avatar-core">AI</span>
        </div>
        <p class="tb-stage-hint" v-if="!turns.length">试着说：「这篇文章的核心结论是什么？」或者「帮我讲讲二叉树遍历」。</p>

        <div class="tb-actions">
          <button
            type="button"
            class="tb-mic"
            :class="{ 'is-on': phase === 'listening' }"
            :disabled="!recognitionSupported || busy"
            @click="toggleMic"
          >
            <Loader2 v-if="phase === 'thinking'" class="spin" :size="18" />
            <MicOff v-else-if="phase === 'listening'" :size="18" />
            <Mic v-else :size="18" />
            <span>{{ phase === 'listening' ? '停止聆听' : '开始说话' }}</span>
          </button>
          <button
            type="button"
            class="tb-toggle tb-pause"
            :class="{ 'is-on': paused }"
            :aria-pressed="paused"
            :disabled="!speakActive"
            @click="togglePauseOnly"
          >
            <Play v-if="paused" :size="16" />
            <Pause v-else :size="16" />
            <span>{{ paused ? '继续朗读' : '暂停朗读' }}</span>
          </button>
          <button
            type="button"
            class="tb-toggle tb-speak"
            :class="{ 'is-on': !muted }"
            :aria-pressed="!muted"
            @click="toggleMute"
          >
            <Volume2 v-if="!muted" :size="16" />
            <VolumeX v-else :size="16" />
            <span>{{ muted ? '已静音' : '声音开启' }}</span>
          </button>
        </div>

        <div class="tb-voice">
          <label for="tb-voice-select">音色</label>
          <select id="tb-voice-select" :value="voiceChoice" @change="onVoiceChange">
            <option v-for="option in voiceOptions" :key="option.id" :value="option.id" :data-voice="option.voiceURI">{{ option.label }}</option>
          </select>
          <button type="button" class="tb-voice-preview" @click="previewVoice">试听</button>
        </div>
        <p v-if="saveStatus" class="tb-save-status">{{ saveStatus }}</p>
        <p v-if="!recognitionSupported" class="tb-warn">当前浏览器不支持语音识别，请用 Edge / Chrome，或直接文字提问。</p>
        <p v-if="errorText" class="tb-warn">{{ errorText }}</p>
      </div>

      <div class="tb-cam">
        <p class="tb-col-title">我的画面</p>
        <div class="tb-cam-screen" :class="{ 'is-on': cameraOn }">
          <video v-show="cameraOn" ref="videoEl" autoplay playsinline muted></video>
          <div v-if="!cameraOn" class="tb-cam-placeholder">
            <span class="tb-cam-me">ME</span>
            <p>等待打开摄像头</p>
          </div>
          <span v-if="cameraOn" class="tb-cam-live"><i></i> 摄像头已开启</span>
        </div>
        <button type="button" class="tb-toggle" :class="{ 'is-on': cameraOn }" :disabled="cameraOpening" @click="toggleCamera">
          <CameraOff v-if="cameraOn" :size="16" />
          <Camera v-else :size="16" />
          <span>{{ cameraOn ? '关闭摄像头' : cameraOpening ? '正在打开…' : '打开摄像头' }}</span>
        </button>
        <div v-if="cameraError" class="tb-cam-error">
          <p class="tb-warn">{{ cameraError }}</p>
          <div class="tb-cam-error-actions">
            <button type="button" class="tb-cam-retry" @click="startCamera">重试</button>
            <span v-if="cameraErrorDetail" class="tb-cam-error-detail">{{ cameraErrorDetail }}</span>
          </div>
        </div>
      </div>

      <div class="tb-transcript" aria-live="polite" ref="transcriptEl">
        <p class="tb-col-title">对话记录</p>
        <p v-if="!turns.length" class="tb-empty">对话会显示在这里，通话后可保存学习过程留痕。</p>
        <article v-for="turn in turns" :key="turn.id" class="tb-turn" :class="`is-${turn.role}`">
          <span class="tb-turn-role">{{ turn.role === 'user' ? '我' : 'AI 老师' }}</span>
          <div v-if="turn.role === 'assistant'" class="tb-turn-body markdown-body">
            <span v-if="turn.pending" class="tb-pending"><Loader2 class="spin" :size="14" /> 正在思考…</span>
            <MarkdownContent v-else :content="turn.text" />
          </div>
          <p v-else class="tb-turn-body">{{ turn.text }}</p>
        </article>
      </div>
    </div>

    <form class="tb-composer" @submit.prevent="sendTyped">
      <input v-model="input" type="text" placeholder="也可以直接打字提问，回车发送…" :disabled="busy" />
      <button type="submit" :disabled="busy || !input.trim()">
        <Loader2 v-if="busy" class="spin" :size="16" />
        <Send v-else :size="16" />
      </button>
    </form>
  </div>
</template>