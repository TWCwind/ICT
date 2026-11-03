<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  ChartNoAxesCombined,
  Check,
  CircleAlert,
  CircleDot,
  ClipboardCheck,
  Database,
  Gauge,
  GitCompareArrows,
  History,
  Info,
  Lightbulb,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  TriangleAlert,
  WandSparkles,
} from 'lucide-vue-next'
import LearningLoopContext from '@/components/LearningLoopContext.vue'
import {
  evolveLearningStrategy,
  generateEvaluation,
  getEvaluationOverview,
  type EvaluationOverview,
} from '@/api/learningApi'
import { useStudent } from '@/composables/useStudent'

const { studentId } = useStudent()
const router = useRouter()
const overview = ref<EvaluationOverview | null>(null)
const latestReport = ref<any>(null)
const evolutionResult = ref<any>(null)
const loading = ref(true)
const refreshing = ref(false)
const evaluating = ref(false)
const evolving = ref(false)
const error = ref('')
const notice = ref('')
// Retained for the non-rendered legacy template below; the active view uses
// semantic bars so values remain readable without hover or canvas support.
const diagnosisEl = ref<HTMLElement | null>(null)
const activeDiagnosisTab = ref<'conclusion' | 'heat' | 'evidence'>('conclusion')
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | undefined
function showToast(message: string, duration = 2000) {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = message
  toastTimer = setTimeout(() => { toast.value = '' }, duration)
}

function selectDiagnosisTab(tab: 'conclusion' | 'heat' | 'evidence') {
  if (activeDiagnosisTab.value === tab) {
    // 重复点击当前诊断页签时，把诊断面板带回视野，避免“点了没反应”。
    diagnosisEl.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }
  activeDiagnosisTab.value = tab
}
const score = computed(() => clamp(overview.value?.score))
const mastery = computed(() => clamp(overview.value?.mastery))
const accuracy = computed(() => clamp(overview.value?.accuracy))
const engagement = computed(() => clamp(overview.value?.engagement))
const hasMasteryEvidence = computed(() => safeNumber(overview.value?.evidence?.knowledge_nodes) > 0)
const hasExerciseEvidence = computed(() => safeNumber(overview.value?.evidence?.exercise_attempts) > 0)
const hasEngagementEvidence = computed(() => [
  'resource_items', 'feedback_items', 'learning_events',
].some((key) => safeNumber(overview.value?.evidence?.[key]) > 0))
const missingEvidenceLabels = computed(() => {
  const missing: string[] = []
  if (!hasMasteryEvidence.value) missing.push('知识掌握')
  if (safeNumber(overview.value?.evidence?.feedback_items) === 0) missing.push('资源反馈')
  return missing
})
const isBusy = computed(() => loading.value || refreshing.value || evaluating.value || evolving.value)
const evidenceTotal = computed(() => {
  const evidence = overview.value?.evidence || {}
  const direct = safeNumber(evidence.total)
  if (direct > 0) return direct
  return ['exercise_attempts', 'knowledge_nodes', 'resource_items', 'feedback_items', 'learning_events']
    .reduce((sum, key) => sum + safeNumber(evidence[key]), 0)
})
const hasEvidence = computed(() => evidenceTotal.value > 0)
const scoreTone = computed(() => {
  if (!hasEvidence.value) return '证据不足'
  if (score.value >= 80) return '表现优秀'
  if (score.value >= 65) return '稳定提升'
  if (score.value >= 50) return '需要强化'
  return '优先干预'
})

function evidenceCountForDimension(label: string) {
  const evidence = overview.value?.evidence || {}
  if (label.includes('知识掌握')) return safeNumber(evidence.knowledge_nodes)
  if (label.includes('迁移应用')) return safeNumber(evidence.exercise_attempts)
  if (label.includes('学习投入')) return safeNumber(evidence.resource_items) + safeNumber(evidence.feedback_items) + safeNumber(evidence.learning_events)
  if (label.includes('资源匹配')) return safeNumber(evidence.feedback_items)
  if (label.includes('策略稳定')) return safeNumber(evidence.learning_events)
  return evidenceTotal.value
}

const dimensions = computed(() => (overview.value?.dimensions || []).map((item) => {
  const label = String(item.label || '未命名维度')
  const evidenceCount = evidenceCountForDimension(label)
  return {
    label,
    value: clamp(item.value),
    evidenceCount,
    observed: evidenceCount > 0,
  }
}))

const evidenceCards = computed(() => {
  const evidence = overview.value?.evidence || {}
  return [
    { key: 'exercise_attempts', label: '练习作答', value: safeNumber(evidence.exercise_attempts), icon: ClipboardCheck, detail: '已提交的有效作答记录' },
    { key: 'knowledge_nodes', label: '知识节点', value: safeNumber(evidence.knowledge_nodes), icon: BrainCircuit, detail: '存在掌握度记录的节点' },
    { key: 'resource_items', label: '资源成果', value: safeNumber(evidence.resource_items), icon: Database, detail: '已进入资源库存的成果' },
    { key: 'feedback_items', label: '资源反馈', value: safeNumber(evidence.feedback_items), icon: Activity, detail: '可用于策略判断的行为' },
    { key: 'learning_events', label: '学习事件', value: safeNumber(evidence.learning_events), icon: History, detail: '画像、路径、辅导与评估事件' },
  ]
})

const reportSummary = computed(() => String(
  latestReport.value?.summary
  || latestReport.value?.conclusion
  || latestReport.value?.notes
  || '',
))
const reportFindings = computed(() => toTextList(
  latestReport.value?.findings
  || latestReport.value?.recommendations
  || latestReport.value?.next_actions,
))
const PROFILE_KEY_LABELS: Record<string, string> = {
  knowledge_base_level: '知识基础',
  mistake_patterns: '易错模式',
  cognitive_style: '认知风格',
  pace_preference: '节奏偏好',
  modality_preference: '模态偏好',
  weak_points: '薄弱知识点',
  strengths: '学习优势',
  goals: '学习目标',
  major: '专业方向',
  score: '综合得分',
}
function profileKeyLabel(key: string) {
  return PROFILE_KEY_LABELS[key] || key.replace(/_/g, ' ')
}
const evolutionUpdates = computed(() => Object.entries(evolutionResult.value?.profile_updates || {}).map(([key, value]) => ({ key, label: profileKeyLabel(key), value: String(value ?? '') })))
const evaluationModeLabel = computed(() => latestReport.value?.analysis_mode === 'llm' ? '大模型综合分析' : '本地证据规则分析')
const diagnosisItems = computed(() => {
  if (activeDiagnosisTab.value === 'heat') {
    return [...dimensions.value]
      .sort((a, b) => a.value - b.value)
      .slice(0, 5)
      .map((item) => ({
        title: item.label,
        detail: item.observed ? `当前证据计算值 ${item.value}%` : '尚无对应学习记录，暂不判断',
        severity: item.observed ? (item.value < 60 ? '高' : '中') : '待采集',
      }))
  }
  if (activeDiagnosisTab.value === 'evidence') {
    return evidenceCards.value
      .filter((item) => item.value > 0)
      .map((item) => ({ title: item.label, detail: `${item.detail}：${item.value} 条`, severity: '证据' }))
  }
  return (overview.value?.weak_points || []).slice(0, 5).map((item) => ({
    title: item,
    detail: reportFindings.value.find((finding) => finding.includes(item)) || '来自错题标签、知识节点或画像证据',
    severity: '关注',
  }))
})
const radarDescription = computed(() => dimensions.value.length
  ? `能力维度：${dimensions.value.map((item) => `${item.label} ${item.observed ? `${item.value} 分` : '暂无证据'}`).join('，')}`
  : '暂无可绘制的评估维度')

async function loadEvaluation(options: { background?: boolean } = {}) {
  const background = Boolean(options.background && overview.value)
  if (background) refreshing.value = true
  else loading.value = true
  error.value = ''
  try {
    const data = await getEvaluationOverview(studentId.value)
    overview.value = data
    if (!evaluating.value) latestReport.value = data.latest_report || null
    await nextTick()
  } catch (reason: any) {
    error.value = reason?.message || '评估证据加载失败'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function runEvaluation() {
  if (isBusy.value) return
  evaluating.value = true
  error.value = ''
  evolutionResult.value = null
  try {
    const result = await generateEvaluation(studentId.value)
    latestReport.value = result?.report || result || null
    await loadEvaluation({ background: true })
    showToast('已生成新的评估报告：左侧分数、诊断结论与行动计划都已按最新证据更新。', 2000)
  } catch (reason: any) {
    error.value = reason?.message || '评估报告生成失败'
  } finally {
    evaluating.value = false
  }
}

async function evolveStrategy() {
  if (!overview.value || isBusy.value) return
  evolving.value = true
  error.value = ''
  try {
    evolutionResult.value = await evolveLearningStrategy(studentId.value, {
      score: score.value,
      topic: overview.value.weak_points?.[0] || '当前课程',
      weak_points: overview.value.weak_points || [],
      action: score.value < 60 ? 'negative' : 'review',
      evidence: overview.value.evidence || {},
    })
    showToast(evolutionResult.value?.evolved
      ? '已更新你的学习画像：新的易错点与学习节奏已写入，之后的学习路径与资源推送会按新版本推荐。'
      : evolutionResult.value?.reason || '本次证据还没达到画像更新门槛，画像保持不变；多完成几次练习与资源反馈后再试即可。', 2000)
    await loadEvaluation({ background: true })
  } catch (reason: any) {
    error.value = reason?.message || '策略进化失败'
  } finally {
    evolving.value = false
  }
}

function startReinforcement() {
  void router.push({ path: '/profile', query: { round: String(Date.now()), source: 'evaluate' } })
}

function showEvidence() {
  activeDiagnosisTab.value = 'evidence'
  void nextTick(() => diagnosisEl.value?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
}

function safeNumber(value: unknown) {
  const number = Number(value)
  return Number.isFinite(number) ? Math.max(0, number) : 0
}

function clamp(value: unknown) {
  return Math.max(0, Math.min(100, safeNumber(value)))
}

function toTextList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => typeof item === 'string' ? item : JSON.stringify(item)).filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

function safeRoute(route: unknown) {
  const value = String(route || '')
  return /^\/(profile|workshop|exercise|knowledge|path|tutor|multimodal|evaluate)$/.test(value) ? value : '/path'
}

function formatTime(value: string) {
  if (!value) return '已记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

function timelineTone(value: string) {
  const allowed = ['primary', 'amber', 'cyan', 'indigo', 'evolution', 'green', 'neutral']
  return allowed.includes(value) ? `tone-${value}` : 'tone-neutral'
}

onMounted(() => { void loadEvaluation() })
</script>

<template>
  <div class="competition-page evaluate-command-page">
    <section class="shot-evaluate" aria-label="学习效果评估与策略进化">
      <header class="shot-evaluate__head"><div><h1>学习效果评估与策略进化</h1><p>查看当前表现与证据，选择下一步补强行动。</p></div><div class="shot-actions"><em v-if="overview && !error && !loading"><Check :size="18" />证据已同步</em><button type="button" :disabled="isBusy" @click="loadEvaluation({ background: true })"><RefreshCw :size="16" />刷新证据</button><button class="is-primary" type="button" :disabled="isBusy" @click="runEvaluation"><LoaderCircle v-if="evaluating" class="spin" :size="16" /><WandSparkles v-else :size="16" />{{ evaluating ? '评估生成中' : '生成智能评估' }}</button></div></header>
      <div v-if="error" class="shot-notice is-error" role="alert"><CircleAlert :size="18" />{{ error }}<button type="button" @click="loadEvaluation()">重新加载</button></div>
      <div v-if="loading && !overview" class="shot-loading"><span class="os-spinner"></span><p>正在汇总学习证据与能力维度……</p></div>
      <template v-else-if="overview">
        <main class="shot-evaluate-main">
          <section class="shot-score-row">
            <article class="shot-score"><header><CircleDot :size="18" />综合学习指数</header><div class="shot-score-ring"><strong>{{ Math.round(score) }}</strong><span>/ 100</span></div><progress class="shot-score-progress" :value="score" max="100" aria-label="综合学习指数">{{ score }}</progress><h2>{{ scoreTone }}</h2><p>汇总 {{ evidenceTotal }} 条本地证据 · {{ latestReport ? evaluationModeLabel : '尚未生成分析报告' }}</p><small v-if="missingEvidenceLabels.length" class="shot-score-caveat">当前缺少{{ missingEvidenceLabels.join('、') }}证据，分值作为阶段参考</small><div class="shot-score-weakpoints"><span v-for="item in overview.weak_points.slice(0, 2)" :key="item"><TriangleAlert :size="16" />{{ item }}</span></div><footer><button type="button" @click="showEvidence"><ClipboardCheck :size="18" />查看证据</button><button type="button" @click="startReinforcement"><TrendingUp :size="18" />启动补强</button></footer></article>
            <article class="shot-capability"><header><strong><BrainCircuit class="shot-panel-icon" :size="17" />多维能力画像</strong><small>分值来自接口；无记录的维度标为待采集</small></header><ul class="shot-capability-bars" aria-label="多维能力数值对比"><li v-for="item in dimensions" :key="item.label" :class="{ 'is-unobserved': !item.observed }"><span>{{ item.label }}</span><div class="shot-capability-track" role="progressbar" :aria-label="`${item.label} ${item.observed ? `${item.value}%` : '暂无证据'}`" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="item.observed ? item.value : undefined" :aria-valuetext="item.observed ? `${item.value}%` : '暂无对应证据'"><b v-if="item.observed" :style="{ width: `${item.value}%` }"></b></div><strong>{{ item.observed ? `${item.value}%` : '待采集' }}</strong></li></ul><p class="shot-capability-note">条形表示当前证据计算值，长度不代表人与人之间的排名。</p></article>
          </section>

          <section class="shot-diagnosis-row"><article ref="diagnosisEl" class="shot-diagnosis"><nav><button type="button" :class="{ active: activeDiagnosisTab === 'conclusion' }" @click="activeDiagnosisTab = 'conclusion'">诊断结论</button><button type="button" :class="{ active: activeDiagnosisTab === 'heat' }" @click="activeDiagnosisTab = 'heat'">薄弱点热区</button><button type="button" :class="{ active: activeDiagnosisTab === 'evidence' }" @click="activeDiagnosisTab = 'evidence'">证据明细</button></nav><h3>{{ activeDiagnosisTab === 'evidence' ? '证据来源' : '关键问题' }}</h3><ol><li v-for="(item,index) in diagnosisItems" :key="`${item.title}-${index}`"><i>{{ index+1 }}</i><span><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></span><em>{{ item.severity }}</em></li><li v-if="!diagnosisItems.length"><span><strong>暂无可分析内容</strong><small>请先完成练习、知识学习或资源反馈。</small></span></li></ol></article>
            <article class="shot-action-plan"><header><strong><ClipboardCheck class="shot-panel-icon" :size="17" />闭环行动计划</strong></header><ul><li v-for="(item,index) in overview.suggestions.slice(0,4)" :key="`${item.title}-${index}`"><i>{{ index+1 }}</i><span><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></span><RouterLink :to="safeRoute(item.route)">去完成 <ArrowRight :size="18" /></RouterLink></li><li v-if="!overview.suggestions.length"><span>当前证据不足，暂不生成行动计划。</span></li></ul></article></section>

          <details class="shot-eval-timeline"><summary>学习记录 · {{ overview.timeline.length }} 条</summary><div><article v-for="(item,index) in overview.timeline.slice(0,5)" :key="item.id || index"><i aria-hidden="true"><component :is="[Database,BrainCircuit,Target,Gauge,TrendingUp][index]" :size="20" /></i><strong>{{ item.title || '学习记录' }}</strong><small>{{ item.detail || item.title }}</small><time>{{ formatTime(item.created_at) }}</time></article></div></details>
        </main>

        <aside class="shot-engine"><header><h2>策略进化引擎</h2><p>根据已有学习记录判断是否调整策略。</p></header><details class="evaluation-evidence"><summary>证据来源 · {{ evidenceTotal }} 条</summary><ul><li v-for="item in evidenceCards" :key="item.key"><component :is="item.icon" :size="24" /><span><strong>{{ item.label }}</strong><small>{{ item.detail }}：{{ item.value }}</small></span></li></ul></details><section><h3>关联知识点</h3><div><span v-for="item in overview.weak_points.slice(0,3)" :key="item">{{ item }}</span><span v-if="!overview.weak_points.length">暂无</span></div><h3>后端判定结果</h3><dl v-if="evolutionUpdates.length"><div v-for="item in evolutionUpdates" :key="item.key"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></div></dl><p v-else>{{ evolutionResult?.reason || '点击下方按钮后，后端会依据当前证据判定是否需要写入新画像快照。' }}</p></section><button type="button" :disabled="isBusy || !hasEvidence" @click="evolveStrategy"><LoaderCircle v-if="evolving" class="spin" :size="16" /><GitCompareArrows v-else :size="16" />{{ evolving ? '进化判定中' : '提交进化判定' }}</button></aside>
      <details class="shot-loop-chain">
        <summary>闭环串联：证据 → 评估 → 策略 → 画像</summary>
        <LearningLoopContext
          stage="08"
          stage-label="效果评估"
          task="汇总证据并判断下一轮学习策略"
          input="全流程行为、掌握度、练习与反馈证据"
          process="评估智能体分析，进化引擎独立判定"
          :output="overview ? `${score} 分 · ${evidenceTotal} 条证据` : '等待证据汇总'"
          next-to="/profile"
          next-label="新一轮画像"
          status="评估结果回流下一轮学习闭环"
        />
      </details>
      </template>
    </section>


    <Teleport to="body">
      <div v-if="toast" class="shot-toast" role="status" aria-live="polite"><Check :size="16" />{{ toast }}</div>
    </Teleport>
  </div>
</template>

<style scoped>

.evaluate-command-page{--e-ink:#18324d;--e-muted:#5d7188;--e-line:#dce4ed;max-width:1540px;margin:0 auto;padding:24px 28px 40px;color:var(--e-ink);font-size:16px;line-height:1.6}
.shot-evaluate{display:grid;grid-template-columns:minmax(0,1fr) 280px;align-items:start;gap:22px;min-width:0;max-width:100%;color:var(--e-ink)}
.shot-evaluate__head,.shot-evaluate>.shot-notice,.shot-evaluate>.shot-loading{grid-column:1/-1}.shot-evaluate__head{display:flex;justify-content:space-between;align-items:center;gap:20px;padding-bottom:14px;border-bottom:1px solid var(--e-line)}.shot-evaluate__head h1{margin:0;font-size:28px;line-height:1.3;letter-spacing:-.025em}.shot-evaluate__head p{margin:5px 0 0;color:var(--e-muted);font-size:15px}.shot-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.shot-actions em{display:flex;align-items:center;gap:6px;margin-right:8px;color:#28674e;font-size:14px;font-style:normal}.shot-actions button,.shot-score footer button,.shot-engine>button{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:8px 13px;border:1px solid #cbd6e2;border-radius:7px;background:#fff;color:#274e78;font:inherit;font-size:14px;cursor:pointer}.shot-actions button.is-primary,.shot-engine>button{border-color:#245fb5;background:#245fb5;color:#fff}.shot-actions button:disabled,.shot-engine>button:disabled{opacity:.55;cursor:not-allowed}
.shot-evaluate-main{display:grid;align-content:start;gap:22px;min-width:0}.shot-score-row{display:grid;grid-template-columns:minmax(205px,.65fr) minmax(0,1.35fr);align-items:start;min-width:0;border-top:1px solid var(--e-line);border-bottom:1px solid var(--e-line)}.shot-score-row>article{align-self:start;min-width:0;padding:18px 20px}.shot-score{display:flex;flex-direction:column;align-items:flex-start;gap:8px;border-right:1px solid var(--e-line)}.shot-score>header{display:flex;align-items:center;gap:7px;color:#365a7f;font-size:15px;font-weight:650}.shot-score-ring{display:flex;align-items:baseline;gap:5px;width:auto;height:auto;border-radius:0;background:none}.shot-score-ring strong{font-size:36px;line-height:1;color:#245fb5}.shot-score-ring span{font-size:14px;color:var(--e-muted)}.shot-score-progress{display:block;width:min(220px,100%);height:8px;appearance:none;border:0;border-radius:8px;background:#e8edf3}.shot-score-progress::-webkit-progress-bar{border-radius:8px;background:#e8edf3}.shot-score-progress::-webkit-progress-value{border-radius:8px;background:#3479c8}.shot-score-progress::-moz-progress-bar{border-radius:8px;background:#3479c8}.shot-score h2{margin:0;font-size:20px}.shot-score p{margin:0;font-size:14px;line-height:1.55;color:var(--e-muted)}.shot-score-caveat{font-size:13px;line-height:1.5;color:#744d24}.shot-score-weakpoints{display:flex;flex-wrap:wrap;gap:6px}.shot-score-weakpoints>span{display:inline-flex;align-items:center;gap:4px;padding:4px 7px;border-radius:4px;background:#fbf4e8;color:#79511d;font-size:13px}.shot-score footer{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}.shot-score footer button{min-height:40px;padding:6px 9px;font-size:13px}
.shot-capability>header{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px 12px;margin-bottom:12px}.shot-capability>header strong{display:flex;align-items:center;gap:8px;font-size:17px}.shot-capability>header small,.shot-capability-note{font-size:13px;color:var(--e-muted)}.shot-capability-bars{display:grid;gap:12px;margin:0;padding:0;list-style:none}.shot-capability-bars li{display:grid;grid-template-columns:minmax(95px,150px) minmax(40px,1fr) minmax(60px,82px);align-items:center;gap:10px}.shot-capability-bars li>span,.shot-capability-bars li>strong{font-size:14px}.shot-capability-bars li>strong{text-align:right}.shot-capability-track{height:10px;overflow:hidden;border-radius:10px;background:#e8edf3}.shot-capability-track b{display:block;height:100%;border-radius:inherit;background:#3479c8}.shot-capability-bars li.is-unobserved .shot-capability-track{background:repeating-linear-gradient(135deg,#eef1f4,#eef1f4 4px,#fff 4px,#fff 8px)}.shot-capability-note{margin:12px 0 0}
.shot-diagnosis-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:24px}.shot-diagnosis-row>article{min-width:0}.shot-diagnosis,.shot-action-plan{padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}.shot-diagnosis nav{display:flex;gap:4px;overflow-x:auto;border-bottom:1px solid var(--e-line)}.shot-diagnosis nav button{flex-shrink:0;min-height:44px;padding:8px 10px;border:0;border-bottom:2px solid transparent;background:none;color:#435c76;font:inherit;font-size:14px;cursor:pointer}.shot-diagnosis nav button.active{border-color:#245fb5;color:#1b579c;font-weight:650}.shot-diagnosis h3,.shot-action-plan>header{margin:14px 0 6px;font-size:17px}.shot-action-plan>header{display:flex;align-items:center;gap:8px}.shot-diagnosis ol,.shot-action-plan ul{margin:0;padding:0;list-style:none}.shot-diagnosis li,.shot-action-plan li{display:grid;grid-template-columns:27px minmax(0,1fr) auto;align-items:center;gap:10px;padding:12px 0;border-top:1px solid #e8edf3}.shot-diagnosis li>i,.shot-action-plan li>i{display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#edf3fa;color:#315e91;font-size:13px;font-style:normal}.shot-diagnosis li>span,.shot-action-plan li>span{display:grid;gap:2px;min-width:0}.shot-diagnosis li strong,.shot-action-plan li strong{font-size:14px}.shot-diagnosis li small,.shot-action-plan li small{font-size:13px;line-height:1.5;color:var(--e-muted)}.shot-diagnosis li em{font-size:12px;color:#8b5425;font-style:normal}.shot-action-plan li>a{display:inline-flex;align-items:center;gap:4px;min-height:40px;color:#245fb5;font-size:13px;text-decoration:none}.shot-action-plan li>a svg{width:18px;height:18px}
.shot-engine{display:grid;align-content:start;gap:0;min-width:0;padding:0 0 0 20px;border-left:1px solid var(--e-line);border-radius:0;background:transparent;box-shadow:none}.shot-engine>header{padding:0 0 12px}.shot-engine h2{margin:0;font-size:19px}.shot-engine>header p{margin:4px 0 0;color:var(--e-muted);font-size:14px}.evaluation-evidence{border-top:1px solid var(--e-line);border-bottom:1px solid var(--e-line)}.evaluation-evidence summary,.shot-eval-timeline summary{min-height:48px;display:flex;align-items:center;cursor:pointer;color:#315578;font-size:15px;font-weight:650}.evaluation-evidence ul{display:grid;margin:0;padding:0;list-style:none}.evaluation-evidence li{display:grid;grid-template-columns:24px 1fr;align-items:center;gap:9px;padding:9px 0;border-top:1px solid #e8edf3;color:#376a9c}.evaluation-evidence li>span{display:grid;gap:2px}.evaluation-evidence li strong{font-size:14px}.evaluation-evidence li small{font-size:13px;color:var(--e-muted)}.shot-engine>section{padding:14px 0;border-bottom:1px solid var(--e-line)}.shot-engine h3{margin:0 0 8px;font-size:15px}.shot-engine section>div{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}.shot-engine section>div span{padding:4px 8px;background:#edf3f8;border-radius:4px;color:#315e91;font-size:13px}.shot-engine dl{display:grid;gap:8px;margin:0}.shot-engine dl>div{display:grid;grid-template-columns:85px 1fr;gap:7px}.shot-engine dt,.shot-engine dd,.shot-engine section>p{margin:0;font-size:13px;line-height:1.55}.shot-engine dd{overflow-wrap:anywhere;color:var(--e-muted)}.shot-engine>button{box-sizing:border-box;width:100%;margin:14px 0 0}.shot-eval-timeline{min-width:0;border-top:1px solid var(--e-line);border-bottom:1px solid var(--e-line)}.shot-eval-timeline>div{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;padding:0 0 14px}.shot-eval-timeline article{display:grid;gap:5px;padding:10px;background:#f5f8fb;border-radius:6px}.shot-eval-timeline article>i{display:none}.shot-eval-timeline article strong{font-size:14px}.shot-eval-timeline article small,.shot-eval-timeline article time{font-size:13px;color:var(--e-muted)}.shot-loop-chain{grid-column:1/-1;color:#315578}.shot-loop-chain summary{min-height:44px;cursor:pointer}.shot-loop-chain[open]{padding:12px;border:1px solid var(--e-line);border-radius:8px}.shot-notice{display:flex;align-items:center;gap:10px;padding:12px 14px;border:1px solid #e5c7c7;border-radius:7px;background:#fff8f7;color:#833434;font-size:14px}.shot-notice button{min-height:40px;margin-left:auto;border:1px solid #c5a0a0;border-radius:6px;background:white;padding:6px 12px;color:inherit;cursor:pointer}.shot-loading{padding:20px;color:var(--e-muted)}.shot-evaluate :is(button,a,summary):focus-visible{outline:3px solid #82a8d2;outline-offset:3px}
@media(max-width:1050px){.evaluate-command-page{padding-inline:22px}.shot-evaluate{grid-template-columns:minmax(0,1fr) 250px;gap:18px}.shot-score-row{grid-template-columns:minmax(180px,.65fr) minmax(0,1.35fr)}}
@media(max-width:820px){.shot-evaluate{grid-template-columns:1fr}.shot-evaluate__head,.shot-evaluate>.shot-notice,.shot-evaluate>.shot-loading,.shot-evaluate-main,.shot-engine,.shot-loop-chain{grid-column:1}.shot-engine{padding:16px 0 0;border-top:1px solid var(--e-line);border-left:0}.shot-score-row{grid-template-columns:1fr 1.5fr}.shot-diagnosis-row{gap:18px}}
@media(max-width:560px){.evaluate-command-page{padding:18px 16px 30px}.shot-evaluate__head{align-items:flex-start;flex-direction:column}.shot-evaluate__head h1{font-size:24px}.shot-actions{width:100%}.shot-actions button{flex:1}.shot-actions em{width:100%}.shot-score-row,.shot-diagnosis-row{grid-template-columns:1fr}.shot-score{align-self:start;border-right:0;border-bottom:1px solid var(--e-line)}.shot-score-row>article{padding:16px 8px}.shot-capability-bars li{grid-template-columns:minmax(85px,1fr) minmax(38px,1fr) 68px;gap:8px}.shot-diagnosis-row{gap:22px}.shot-action-plan li{grid-template-columns:24px minmax(0,1fr)}.shot-action-plan li>a{grid-column:2}.shot-eval-timeline>div{grid-template-columns:1fr}.shot-loop-chain{font-size:14px}}

</style>
