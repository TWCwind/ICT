<script setup lang="ts">
import { ref, watch, type Component } from 'vue'
import { RouterLink } from 'vue-router'
import {
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  ClipboardCheck,
  Code2,
  FileText,
  GraduationCap,
  Layers3,
  Map,
  Network,
  PenTool,
  Route,
  Sparkles,
  Video,
} from 'lucide-vue-next'
import { getDashboardOverview, type DashboardOverview } from '@/api/learningApi'
import { useStudent } from '@/composables/useStudent'

type Capability = {
  eyebrow: string
  title: string
  desc: string
  to: string
  action: string
  icon: Component
  preview: string[]
}

type PathNode = {
  label: string
  desc: string
  status: 'done' | 'active' | 'next'
}

type ResourceType = {
  label: string
  icon: Component
  desc: string
}

const { studentId } = useStudent()
const liveOverview = ref<DashboardOverview | null>(null)
const liveState = ref<'loading' | 'ready' | 'empty' | 'error'>('loading')
const liveError = ref('')
let liveRequestVersion = 0

async function loadLiveOverview() {
  const requestVersion = ++liveRequestVersion
  liveState.value = 'loading'
  liveError.value = ''
  try {
    const overview = await getDashboardOverview(studentId.value)
    if (requestVersion !== liveRequestVersion) return
    liveOverview.value = overview
    liveState.value = overview?.metrics?.length ? 'ready' : 'empty'
  } catch (error) {
    if (requestVersion !== liveRequestVersion) return
    liveOverview.value = null
    liveState.value = 'error'
    liveError.value = error instanceof Error ? error.message : '实时学习证据暂时不可用'
  }
}

watch(studentId, () => void loadLiveOverview(), { immediate: true })

const capabilities: Capability[] = [
  {
    eyebrow: 'Profile',
    title: '一句话，形成动态学习画像。',
    desc: '学生只需要描述专业、课程章节、目标和薄弱点，系统即可抽取知识基础、认知风格、易错模式、模态偏好等关键维度。',
    to: '/profile',
    action: '进入用户画像',
    icon: GraduationCap,
    preview: ['软件工程', '需求分析与建模', '图解偏好', '用例图 / 需求访谈'],
  },
  {
    eyebrow: 'Agent Workshop',
    title: '多智能体协同，不止生成一份资料。',
    desc: '讲解、题库、导图、拓展阅读、实操案例和视频脚本由不同角色智能体协同产出，并沉淀为可复用学习资源。',
    to: '/workshop',
    action: '进入资源工坊',
    icon: BrainCircuit,
    preview: ['讲解文档', '思维导图', '练习题库', '实操案例'],
  },
  {
    eyebrow: 'Learning Path',
    title: '把资源变成真正可执行的学习路径。',
    desc: '结合画像、练习诊断和知识图谱，系统动态安排学习顺序，并精准推送文档、视频、题库和实操任务。',
    to: '/path',
    action: '查看路径推送',
    icon: Route,
    preview: ['概念补强', '例题训练', '项目实操', '阶段测评'],
  },
]

const pathNodes: PathNode[] = [
  { label: '基础诊断', desc: '识别知识起点', status: 'done' },
  { label: '概念补强', desc: '聚焦薄弱章节', status: 'active' },
  { label: '例题训练', desc: '对比易错概念', status: 'next' },
  { label: '项目实操', desc: '迁移到真实任务', status: 'next' },
  { label: '阶段测评', desc: '形成学习证据', status: 'next' },
  { label: '动态调整', desc: '更新画像与推荐', status: 'next' },
]

const resourceTypes: ResourceType[] = [
  { label: '讲解文档', icon: FileText, desc: '课程重点结构化讲解' },
  { label: '思维导图', icon: Network, desc: '知识点关系可视化' },
  { label: '练习题库', icon: ClipboardCheck, desc: '按薄弱点生成训练题' },
  { label: '拓展阅读', icon: BookOpenCheck, desc: '补充背景与案例材料' },
  { label: '实操案例', icon: Code2, desc: '面向任务的实践步骤' },
  { label: '视频 / 动画', icon: Video, desc: '短视频脚本与讲解设计' },
]
</script>

<template>
  <div class="apple-home">
    <section class="apple-hero">
      <div class="apple-hero-copy">
        <div class="apple-kicker">
          <Sparkles :size="18" />
          <span>AI Learning Agent</span>
        </div>
        <h1>为每一位学生，生成专属学习路径。</h1>
        <p>
          基于学习画像、多智能体协同与多模态资源生成，帮助学生从知识短板到能力提升，
          获得更精准、更高效的学习体验。
        </p>
        <div class="apple-hero-actions">
          <RouterLink class="apple-primary-btn" to="/profile">
            开始构建学习画像
            <ArrowRight :size="18" />
          </RouterLink>
          <RouterLink class="apple-text-btn" to="/path">
            查看学习路径示例
          </RouterLink>
        </div>
      </div>

      <div class="product-preview-shell" aria-label="系统产品预览">
        <div class="preview-glow"></div>
        <div class="preview-device">
          <div class="preview-toolbar">
            <span></span>
            <span></span>
            <span></span>
            <strong>慧思智学平台</strong>
          </div>
          <div class="preview-screen">
            <div class="preview-left">
              <small>Learning Profile</small>
              <h2>需求分析与建模</h2>
              <p>已识别：图解偏好、案例驱动、用例图与需求访谈混淆</p>
              <div class="preview-tags">
                <span>画像生成中</span>
                <span>资源沉淀</span>
                <span>路径更新</span>
              </div>
            </div>
            <div class="preview-flow">
              <div class="flow-line"></div>
              <div class="flow-item active">
                <GraduationCap :size="19" />
                <span>学习画像</span>
              </div>
              <div class="flow-item">
                <BrainCircuit :size="19" />
                <span>Agent 协作</span>
              </div>
              <div class="flow-item">
                <Map :size="19" />
                <span>路径推送</span>
              </div>
            </div>
          </div>
          <div class="preview-bottom">
            <div>
              <strong>6</strong>
              <span>画像维度</span>
            </div>
            <div>
              <strong>5+</strong>
              <span>资源类型</span>
            </div>
            <div>
              <strong>API</strong>
              <span>真实接口</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="live-evidence" aria-live="polite" aria-label="本地实时学习证据">
      <div class="live-evidence-heading">
        <div>
          <span class="section-label">LOCAL EVIDENCE</span>
          <h2>把每一次学习行为，沉淀为可解释证据。</h2>
          <p>以下数据来自当前学习者的本地接口，不是页面预置数字。</p>
        </div>
        <span class="live-evidence-status" :class="`is-${liveState}`">
          <span class="live-status-dot"></span>
          {{ liveState === 'ready' ? '接口已同步' : liveState === 'loading' ? '正在同步' : liveState === 'empty' ? '等待建立画像' : '暂时不可用' }}
        </span>
      </div>

      <div v-if="liveState === 'ready' && liveOverview" class="live-evidence-body">
        <div class="live-metric-grid">
          <article v-for="metric in liveOverview.metrics.slice(0, 4)" :key="metric.key" class="live-metric-card">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}<small>{{ metric.unit }}</small></strong>
          </article>
        </div>
        <div class="live-focus-card">
          <div>
            <span>当前优先突破</span>
            <strong>{{ liveOverview.focus.headline || liveOverview.focus.primary }}</strong>
            <p>{{ liveOverview.focus.recommended_action }}</p>
          </div>
          <RouterLink :to="liveOverview.next_actions[0]?.route || '/profile'">
            {{ liveOverview.next_actions[0]?.cta || '进入学习闭环' }}
            <ArrowRight :size="16" />
          </RouterLink>
        </div>
      </div>
      <div v-else-if="liveState === 'error'" class="live-evidence-empty">
        <span>{{ liveError }}</span>
        <button type="button" @click="loadLiveOverview">重新读取</button>
      </div>
      <div v-else-if="liveState === 'empty'" class="live-evidence-empty">
        当前学习者尚未产生学习证据，先从用户画像开始建立个性化闭环。
      </div>
      <div v-else class="live-evidence-empty">正在从本地学习服务读取真实证据…</div>
    </section>

    <section class="apple-section apple-intro">
      <span class="section-label">核心能力</span>
      <h2>从“我哪里不会”，到“下一步该学什么”。</h2>
      <p>
        首页展示完整学习闭环：画像采集、资源生成、练习诊断、路径推送与效果评估，
        但表达方式保持克制，让比赛演示更像成熟产品发布。
      </p>
    </section>

    <section class="capability-story">
      <article v-for="item in capabilities" :key="item.title" class="story-panel">
        <div class="story-copy">
          <div class="story-icon">
            <component :is="item.icon" :size="23" />
          </div>
          <span>{{ item.eyebrow }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
          <RouterLink :to="item.to">
            {{ item.action }}
            <ArrowRight :size="17" />
          </RouterLink>
        </div>
        <div class="story-visual">
          <div class="story-screen">
            <div class="screen-line strong"></div>
            <div class="screen-line"></div>
            <div class="screen-line short"></div>
            <div class="story-chip-grid">
              <span v-for="tag in item.preview" :key="tag">{{ tag }}</span>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="path-showcase">
      <div class="path-copy">
        <span class="section-label">路径推送</span>
        <h2>让学习顺序被看见。</h2>
        <p>
          系统根据画像、知识掌握情况和资源覆盖度动态规划学习步骤。
          每个节点都对应清晰目标和下一步资源，不再让学生在资料堆里迷路。
        </p>
      </div>
      <div class="path-rail">
        <article v-for="(node, index) in pathNodes" :key="node.label" class="path-node" :class="node.status">
          <span class="path-index">{{ String(index + 1).padStart(2, '0') }}</span>
          <div>
            <strong>{{ node.label }}</strong>
            <p>{{ node.desc }}</p>
          </div>
          <em>{{ node.status === 'done' ? '已完成' : node.status === 'active' ? '进行中' : '推荐下一步' }}</em>
        </article>
      </div>
    </section>

    <section class="resource-showcase">
      <div class="resource-stage">
        <div class="resource-main-window">
          <div class="resource-window-head">
            <Layers3 :size="20" />
            <span>多模态资源生成</span>
          </div>
          <h2>同一个薄弱点，可以获得多种学习表达。</h2>
          <p>针对“用例图 / 需求访谈混淆”，系统会同步组织讲解、导图、练习和实操任务。</p>
          <div class="resource-progress">
            <span style="width: 72%"></span>
          </div>
        </div>

        <div class="resource-orbit">
          <article v-for="item in resourceTypes" :key="item.label" class="resource-pill">
            <component :is="item.icon" :size="20" />
            <div>
              <strong>{{ item.label }}</strong>
              <span>{{ item.desc }}</span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section class="apple-final-cta">
      <div>
        <PenTool :size="28" />
        <h2>从今天开始，让学习路径真正属于你。</h2>
        <p>先构建画像，再生成资源，最后让系统持续根据学习证据更新推荐。</p>
      </div>
      <RouterLink class="apple-primary-btn" to="/profile">
        进入智能体系统
        <ArrowRight :size="18" />
      </RouterLink>
    </section>

    <footer class="apple-home-footer">
      <CheckCircle2 :size="16" />
      <span>慧思智学平台 · 多智能体个性化学习资源生成系统</span>
    </footer>
  </div>
</template>

<style scoped>
.live-evidence {
  margin: 18px 0 0;
  padding: 28px 30px;
  border: 1px solid rgba(49, 110, 232, .14);
  border-radius: 26px;
  background: linear-gradient(135deg, rgba(255,255,255,.96), rgba(239,247,255,.88));
  box-shadow: 0 18px 44px rgba(39, 92, 166, .08);
}
.live-evidence-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.live-evidence-heading h2 { margin: 8px 0 7px; color: #102c58; font-size: clamp(22px, 2.4vw, 32px); letter-spacing: -.03em; }
.live-evidence-heading p { margin: 0; color: #68809f; font-size: 14px; }
.live-evidence-status { display: inline-flex; align-items: center; gap: 8px; min-height: 34px; padding: 7px 12px; border-radius: 999px; background: #edf5ff; color: #2563c7; font-size: 12px; font-weight: 800; white-space: nowrap; }
.live-evidence-status.is-error { color: #b54708; background: #fff4e8; }
.live-evidence-status.is-empty { color: #64748b; background: #f1f5f9; }
.live-status-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 4px color-mix(in srgb, currentColor 16%, transparent); }
.live-evidence-body { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(260px, .7fr); gap: 16px; margin-top: 24px; }
.live-metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.live-metric-card { min-height: 108px; padding: 16px; border: 1px solid rgba(49,110,232,.12); border-radius: 17px; background: rgba(255,255,255,.84); }
.live-metric-card span, .live-focus-card span { display: block; color: #7185a1; font-size: 12px; font-weight: 760; }
.live-metric-card strong { display: block; margin-top: 12px; color: #123c7a; font-size: 30px; line-height: 1; }
.live-metric-card small { margin-left: 3px; color: #7890ae; font-size: 12px; font-weight: 700; }
.live-focus-card { display: flex; flex-direction: column; justify-content: space-between; gap: 15px; padding: 18px; border-radius: 17px; background: linear-gradient(145deg, #143c79, #216cd5); color: #fff; }
.live-focus-card span { color: rgba(255,255,255,.7); }
.live-focus-card strong { display: block; margin-top: 7px; font-size: 18px; line-height: 1.45; }
.live-focus-card p { margin: 7px 0 0; color: rgba(255,255,255,.78); font-size: 13px; line-height: 1.55; }
.live-focus-card a { display: inline-flex; align-items: center; align-self: flex-start; gap: 6px; padding: 9px 12px; border-radius: 10px; background: rgba(255,255,255,.16); color: #fff; font-size: 13px; font-weight: 800; }
.live-evidence-empty { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 20px; padding: 16px; border-radius: 14px; background: rgba(255,255,255,.72); color: #637997; font-size: 14px; line-height: 1.6; }
.live-evidence-empty button { min-height: 40px; padding: 7px 13px; border: 1px solid #b6cff5; border-radius: 9px; background: #fff; color: #1f63c4; font-weight: 800; cursor: pointer; }
.live-evidence a:focus-visible, .live-evidence button:focus-visible { outline: 3px solid #184ea8; outline-offset: 3px; }
@media (max-width: 800px) { .live-evidence { padding: 22px 18px; } .live-evidence-heading { flex-direction: column; gap: 12px; } .live-evidence-body { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .live-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .live-evidence-empty { align-items: flex-start; flex-direction: column; } }
</style>
