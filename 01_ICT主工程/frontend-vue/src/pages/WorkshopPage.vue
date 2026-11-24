<script setup lang="ts">
import { computed, onMounted, ref, type Component } from 'vue'
import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Bot,
  Boxes,
  Check,
  CircleAlert,
  ClipboardCheck,
  Clock3,
  Download,
  ExternalLink,
  Eye,
  FileArchive,
  FileInput,
  FileQuestion,
  FileText,
  FlaskConical,
  Layers3,
  LoaderCircle,
  Maximize2,
  Network,
  PackageCheck,
  RefreshCw,
  Share2,
  Sparkles,
  Target,
  Trash2,
  Upload,
  UsersRound,
  Video,
  WandSparkles,
  X,
} from 'lucide-vue-next'
import MarkdownContent from '@/components/MarkdownContent.vue'
import MindmapCanvas from '@/components/MindmapCanvas.vue'
import { normaliseGeneratedMarkdown, renderMarkdown } from '@/utils/markdownRenderer'
import {
  deleteWorkshopResource,
  exportResourcePackage,
  generateResourcePackStream,
  getWorkshopKeywords,
  getWorkshopOverview,
  type ResourceSummary,
  type WorkshopOverview,
} from '@/api/learningApi'
import { useStudent } from '@/composables/useStudent'

type ResourceTypeOption = {
  value: string
  label: string
  short: string
  description: string
  icon: Component
  tone: string
}

const resourceTypes: ResourceTypeOption[] = [
  { value: 'lecture_doc', label: '讲解文档', short: '文档', description: '章节讲解、概念梳理、知识点总结', icon: FileText, tone: 'blue' },
  { value: 'mindmap', label: '思维导图', short: '导图', description: '知识点关系、层级结构可视化', icon: Share2, tone: 'cyan' },
  { value: 'question_bank', label: '练习题库', short: '题库', description: '诊断题、巩固题、阶段检测题', icon: ClipboardCheck, tone: 'violet' },
  { value: 'reading', label: '拓展阅读', short: '阅读', description: '背景知识、案例材料、延伸阅读', icon: BookOpen, tone: 'indigo' },
  { value: 'practice_case', label: '实验案例', short: '案例', description: '代码/建模任务、步骤说明', icon: FlaskConical, tone: 'purple' },
  { value: 'video_script', label: '视频脚本', short: '脚本', description: '录屏脚本、分镜提示、字幕草案', icon: Video, tone: 'sky' },
]

const agentLabels: Record<string, string> = {
  lecture: '课程讲解智能体',
  mindmap: '思维导图智能体',
  quiz: '题库设计智能体',
  reading: '拓展阅读智能体',
  practice: '实操案例智能体',
  video: '多模态脚本智能体',
  quality_check: '内容质量审查',
}

const { studentId, goals } = useStudent()
const overview = ref<WorkshopOverview | null>(null)
const overviewLoading = ref(true)
const overviewRefreshing = ref(false)
const generating = ref(false)
const exporting = ref(false)
const error = ref('')
const notice = ref('')
const uploadInput = ref<HTMLInputElement | null>(null)
const uploadMode = ref<'reference' | 'outline'>('reference')

const course = ref('')
const chapter = ref('')
const weakPoints = ref('')
const learningStyle = ref('')
const selectedTypes = ref<string[]>(['lecture_doc'])
const uploadedContext = ref<{ name: string; mode: string; text: string } | null>(null)
const showAllRecords = ref(false)
const deletingId = ref('')

const generatedResources = ref<ResourceSummary[]>([])
const selectedResource = ref<ResourceSummary | null>(null)
const selectedResourceIds = ref<string[]>([])
const previewContent = ref('')
const previewLoading = ref(false)
const previewError = ref('')
const previewExpanded = ref(false)
const exportUrl = ref('')
const liveTrace = ref<Array<{ key: string; label: string; role: string; status: string; verified: boolean }>>([])
let previewRequestId = 0

const visibleResources = computed(() => generatedResources.value)
const selectedTypeLabels = computed(() => resourceTypes.filter((item) => selectedTypes.value.includes(item.value)).map((item) => item.label))
const selectedCount = computed(() => selectedResourceIds.value.length)
const readablePreviewContent = computed(() => normaliseGeneratedMarkdown(previewContent.value))
const mindmapSource = computed(() => {
  const markdown = (readablePreviewContent.value || '').replace(/\r\n?/g, '\n')
  const blocks: string[] = []
  const fence = /```[a-zA-Z]*[ \t]*\n([\s\S]*?)```/g
  let match: RegExpExecArray | null
  while ((match = fence.exec(markdown))) blocks.push(match[1])
  for (const block of blocks) {
    if (/^\s*mindmap\b/i.test(block)) return block
  }
  const bare = /(^|\n)\s*mindmap\s*\n([\s\S]*)$/i.exec(markdown)
  return bare ? `mindmap\n${bare[2]}` : ''
})
const displayedResources = computed(() => showAllRecords.value ? visibleResources.value : visibleResources.value.slice(0, 4))
const contentKeywords = ref<string[]>([])
const keywordsLoading = ref(false)
const keywordsHint = ref('点击档案袋中的文件，从正文提取关键词')
let keywordsRequestId = 0

async function loadKeywords(resourceId: string) {
  if (!resourceId) return
  const requestId = ++keywordsRequestId
  keywordsLoading.value = true
  contentKeywords.value = []
  keywordsHint.value = '正在从正文提取关键词……'
  try {
    const data = await getWorkshopKeywords(studentId.value, resourceId)
    if (requestId !== keywordsRequestId) return
    contentKeywords.value = data.keywords || []
    keywordsHint.value = data.has_content ? '这份档案没有提取到合适的关键词' : '这份档案没有可提取的正文'
  } catch (reason: any) {
    if (requestId !== keywordsRequestId) return
    contentKeywords.value = []
    keywordsHint.value = reason?.message || '关键词提取失败'
  } finally {
    if (requestId === keywordsRequestId) keywordsLoading.value = false
  }
}
const qualityLabel = computed(() => {
  const quality = overview.value?.quality
  if (!quality) return '等待质量检查'
  if (quality.status === 'ready') return '质量检查可用'
  if (quality.status === 'pending') return '等待生成结果'
  return quality.status
})

const traceItems = computed(() => {
  if (liveTrace.value.length) return liveTrace.value
  const trace = selectedResource.value?.agent_trace
  if (Array.isArray(trace) && trace.length) {
    return trace.map((item, index) => ({
      key: `${item?.agent || 'agent'}-${index}`,
      label: agentLabels[item?.agent] || item?.agent || `协作角色 ${index + 1}`,
      role: item?.task || item?.role || '参与本资源的生成与校验',
      status: item?.status || 'returned',
      verified: true,
    }))
  }
  if (selectedResource.value?.agent) {
    return [{
      key: selectedResource.value.agent,
      label: agentLabels[selectedResource.value.agent] || '资源生成智能体',
      role: '资源已生成并保存，可在预览区阅读或加入导出清单',
      status: 'persisted',
      verified: true,
    }]
  }
  return []
})
const displayTraceItems = computed(() => {
  return traceItems.value.slice(0, 7)
})

function updateLiveTrace(agent: string, patch: Partial<{ label: string; role: string; status: string; verified: boolean }>) {
  const localizedPatch = { ...patch, label: agentLabels[agent] || patch.label || '资源生成智能体' }
  const index = liveTrace.value.findIndex((item) => item.key === agent)
  if (index < 0) {
    liveTrace.value.push({ key: agent, label: localizedPatch.label, role: patch.role || '等待后端处理', status: patch.status || 'pending', verified: Boolean(patch.verified) })
    return
  }
  liveTrace.value[index] = { ...liveTrace.value[index], ...localizedPatch }
}

function labelForType(type: string) {
  return resourceTypes.find((item) => item.value === type)?.label
    || overview.value?.distribution.find((item) => item.type === type)?.label
    || (type === 'quality_check' ? '质量审查' : '')
    || type
}

function completedResourceMessage(resource?: ResourceSummary) {
  if (!resource) return '生成流程已完成'
  return `${labelForType(resource.type)}已生成并保存，可在资源预览中阅读`
}

function splitWeakPoints() {
  return weakPoints.value
    .split(/[，,、;；\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function formatDate(value: string) {
  if (!value) return '未记录时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

function toggleResourceType(value: string) {
  error.value = ''
  notice.value = ''
  selectedTypes.value = selectedTypes.value.includes(value)
    ? selectedTypes.value.filter((item) => item !== value)
    : [...selectedTypes.value, value]
}

function chooseUpload(mode: 'reference' | 'outline') {
  uploadMode.value = mode
  uploadInput.value?.click()
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const extension = file.name.split('.').pop()?.toLowerCase()
  if (!['txt', 'md', 'csv', 'json'].includes(extension || '')) {
    error.value = '当前真实解析链路支持 TXT、Markdown、CSV 和 JSON；PDF、Word 请先转为文本后导入。'
    input.value = ''
    return
  }
  const text = await file.text()
  if (!text.trim()) {
    error.value = '导入文件没有可分析的文本内容。'
    input.value = ''
    return
  }
  uploadedContext.value = { name: file.name, mode: uploadMode.value, text: text.slice(0, 20_000) }
  notice.value = `${uploadMode.value === 'outline' ? '课程大纲' : '参考资料'}已解析：${file.name}（${text.length} 字符），生成时将发送到后端分析。`
  input.value = ''
}

async function loadOverview() {
  const initial = !overview.value
  if (initial) overviewLoading.value = true
  else overviewRefreshing.value = true
  error.value = ''
  try {
    const previousSelection = selectedResource.value?.id
    overview.value = await getWorkshopOverview(studentId.value)
    generatedResources.value = overview.value.latest || []
    const nextSelection = visibleResources.value.find((item) => item.id === previousSelection) || visibleResources.value[0]
    if (nextSelection) {
      await openResource(nextSelection)
    } else {
      selectedResource.value = null
      previewContent.value = ''
    }
  } catch (reason: any) {
    error.value = reason?.message || '资源工坊数据加载失败'
  } finally {
    overviewLoading.value = false
    overviewRefreshing.value = false
  }
}

async function generateResources() {
  if (generating.value) return
  const naturalRequest = weakPoints.value.trim()
  if (!course.value.trim() && !chapter.value.trim() && !naturalRequest) {
    error.value = '请描述要生成的课程资源、章节范围或具体学习需求。'
    return
  }
  if (!selectedTypes.value.length) {
    error.value = '请至少选择一种资源类型。'
    return
  }

  generating.value = true
  liveTrace.value = []
  error.value = ''
  notice.value = ''
  exportUrl.value = ''
  try {
    const inferredTopic = naturalRequest.split(/[，。；;\n]/).map((item) => item.trim()).find(Boolean) || naturalRequest
    const resolvedCourse = course.value.trim() || inferredTopic.slice(0, 48)
    const resolvedChapter = chapter.value.trim() || naturalRequest.slice(0, 96)
    const generationPayload = {
      student_id: studentId.value,
      requirement: {
        course: resolvedCourse,
        chapter: resolvedChapter,
        goals: goals.value || undefined,
        weak_points: splitWeakPoints(),
        resource_types: selectedTypes.value,
        style: learningStyle.value.trim(),
        source_documents: uploadedContext.value ? [uploadedContext.value] : [],
      },
    }
    const resources = await generateResourcePackStream(generationPayload, (event) => {
      if (event.type === 'start') {
        for (const agent of event.agents || []) updateLiveTrace(agent, { status: 'pending', role: '已由后端加入本轮处理队列' })
      } else if (event.type === 'agent_start' && event.agent) {
        updateLiveTrace(event.agent, { label: event.title || event.agent, status: 'running', role: '正在调用真实生成或质量检查流程' })
      } else if (event.type === 'agent_chunk' && event.agent) {
        updateLiveTrace(event.agent, { status: 'running', role: `正在生成${agentLabels[event.agent] || '学习资源'}内容` })
      } else if (event.type === 'agent_done' && event.agent) {
        updateLiveTrace(event.agent, { status: 'completed', role: completedResourceMessage(event.resource), verified: true })
      }
    })
    generatedResources.value = resources
    selectedResourceIds.value = resources.map((item) => item.id).filter(Boolean)
    if (resources[0]) await openResource(resources[0])
    notice.value = resources.length
      ? `后端已返回 ${resources.length} 份资源，已默认加入导出清单。`
      : '后端已完成请求，但本轮没有返回资源。请调整范围后重试。'
    await loadOverview()
  } catch (reason: any) {
    error.value = reason?.message || '资源生成失败，请保留当前配置后重试。'
  } finally {
    generating.value = false
  }
}

async function openResource(resource: ResourceSummary) {
  const requestId = ++previewRequestId
  const derivedUrl = resource.preview_url || (resource.content_uri ? `/${String(resource.content_uri).replace(/^\/+/, '')}` : '')
  const normalizedResource = { ...resource, preview_url: derivedUrl }
  selectedResource.value = normalizedResource
  void loadKeywords(resource.id)
  previewContent.value = resource.content || resource.summary || ''
  previewError.value = ''
  previewExpanded.value = false
  if (previewContent.value) return
  if (!derivedUrl) {
    previewError.value = '资源已生成，但后端没有返回可读取的正文地址。'
    return
  }

  previewLoading.value = true
  try {
    const response = await fetch(derivedUrl)
    if (!response.ok) throw new Error(`预览请求失败（${response.status}）`)
    const content = await response.text()
    if (requestId === previewRequestId) previewContent.value = content
  } catch (reason: any) {
    if (requestId === previewRequestId) previewError.value = reason?.message || '资源预览加载失败'
  } finally {
    if (requestId === previewRequestId) previewLoading.value = false
  }
}

async function removeResource(resource: ResourceSummary) {
  if (deletingId.value) return
  const confirmed = window.confirm(`确定从档案袋删除「${resource.title}」吗？\n对应的文档文件会一并删除，且无法恢复。`)
  if (!confirmed) return
  deletingId.value = resource.id
  error.value = ''
  try {
    await deleteWorkshopResource(studentId.value, resource.id)
    generatedResources.value = generatedResources.value.filter((item) => item.id !== resource.id)
    selectedResourceIds.value = selectedResourceIds.value.filter((id) => id !== resource.id)
    if (selectedResource.value?.id === resource.id) {
      selectedResource.value = null
      previewContent.value = ''
      previewError.value = ''
      previewExpanded.value = false
      contentKeywords.value = []
      keywordsHint.value = '点击档案袋中的文件，从正文提取关键词'
    }
    notice.value = `已从档案袋删除「${resource.title}」，对应文档也已移除。`
    await loadOverview()
  } catch (reason: any) {
    error.value = reason?.message || '删除档案失败，请稍后重试。'
  } finally {
    deletingId.value = ''
  }
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] as string))
}

function openPreviewWindow() {
  const resource = selectedResource.value
  const title = resource?.title || '资源预览'
  const body = renderMarkdown(previewContent.value || '')
  const html = [
    '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
    `<title>${escapeHtml(title)}</title>`,
    '<style>body{margin:0;padding:36px 44px;background:#fff;color:#2e4a42;',
    'font:14px/1.85 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}',
    'article{max-width:860px;margin:0 auto}h1,h2,h3,h4{color:#2e4a42;line-height:1.45}',
    'h1{font-size:24px}h2{font-size:19px;margin-top:28px}h3{font-size:16px}',
    'h4{font-size:14px}table{border-collapse:collapse;width:100%;margin:12px 0}',
    'th,td{border:1px solid #e8f6f2;padding:6px 10px;text-align:left}',
    'th{background:#f7fcfb}code{background:#f7fcfb;padding:1px 5px;border-radius:4px;font-size: 13px}',
    'pre{background:#f7fcfb;padding:14px;border-radius:8px;overflow:auto}',
    'blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid #8acab5;background:#f7fcfb}',
    'hr{border:0;border-top:1px solid #e8f6f2;margin:24px 0}</style></head><body><article>',
    body,
    '</article></body></html>',
  ].join('')
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const opened = window.open(url, '_blank')
  if (!opened) {
    URL.revokeObjectURL(url)
    if (resource?.preview_url) window.open(resource.preview_url, '_blank')
    return
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60000)
}

function toggleResourceSelection(resourceId: string) {
  selectedResourceIds.value = selectedResourceIds.value.includes(resourceId)
    ? selectedResourceIds.value.filter((item) => item !== resourceId)
    : [...selectedResourceIds.value, resourceId]
}

function toggleSelectAll() {
  const availableIds = visibleResources.value.map((item) => item.id).filter(Boolean)
  selectedResourceIds.value = selectedResourceIds.value.length === availableIds.length ? [] : availableIds
}

async function exportSelected() {
  if (exporting.value || !selectedResourceIds.value.length) return
  exporting.value = true
  error.value = ''
  notice.value = ''
  exportUrl.value = ''
  try {
    exportUrl.value = await exportResourcePackage(studentId.value, selectedResourceIds.value)
    if (!exportUrl.value) throw new Error('后端未返回下载地址')
    notice.value = '资源包已生成。请点击“下载 ZIP”保存到本地。'
  } catch (reason: any) {
    error.value = reason?.message || '资源包导出失败'
  } finally {
    exporting.value = false
  }
}

onMounted(loadOverview)
</script>

<template>
  <div class="competition-page workshop-command-page">
    <section class="shot-workshop" aria-label="资源工坊">
      <div v-if="error" class="shot-notice is-error" role="alert"><CircleAlert :size="18" />{{ error }}<button type="button" @click="loadOverview">重新同步</button></div>
      <div v-if="notice" class="shot-notice"><Check :size="18" />{{ notice }}</div>

      <div v-if="overviewLoading && !overview" class="shot-loading"><span class="os-spinner"></span><p>正在读取资源清单与协作角色……</p></div>
      <template v-else>
        <main class="shot-workshop__main">
          <header class="shot-workshop-hero"><div class="shot-workshop-copy"><h1>资源工坊</h1><p>选择资源类型，描述学习需求，再查看和导出生成结果。</p></div></header>

          <form class="shot-create" @submit.prevent="generateResources"><header><strong>快速创建资源</strong><small>可选择多种类型，生成结果会自动保存到档案袋。</small></header>
            <div class="shot-type-grid"><button v-for="item in resourceTypes" :key="item.value" type="button" :class="{ active: selectedTypes.includes(item.value) }" :aria-pressed="selectedTypes.includes(item.value)" @click="toggleResourceType(item.value)"><i :class="`tone-${item.tone}`"><component :is="item.icon" :size="25" /></i><strong>{{ item.label }}</strong><small>{{ item.description }}</small><Check v-if="selectedTypes.includes(item.value)" :size="14" /></button></div>
            <div class="shot-brief-fields"><label><span>课程 / 主题</span><input v-model="course" placeholder="输入要分析的真实课程或主题" /></label><label><span>章节 / 场景</span><input v-model="chapter" placeholder="输入章节、任务或应用场景" /></label></div>
            <div class="shot-brief-head"><label for="workshop-brief" class="workshop-brief-label">学习需求</label><small class="shot-char-count">{{ weakPoints.length }}/500</small></div>
            <textarea id="workshop-brief" v-model="weakPoints" maxlength="500" rows="3" placeholder="请输入你的需求，例如：&#10;“生成《Python 函数》章节的讲解文档，重点讲解函数定义、参数、返回值，并配有示例代码”&#10;或上传参考资料，我们将基于你的需求生成高质量资源。"></textarea>
            <footer><div><button type="button" @click="chooseUpload('reference')"><Upload :size="14" />上传参考资料</button><button type="button" @click="chooseUpload('outline')"><FileInput :size="14" />导入课程大纲</button><input ref="uploadInput" class="shot-file-input" type="file" accept=".txt,.md,.csv,.json" @change="handleUpload" /></div><button class="shot-generate" type="submit" :title="generating ? '正在生成资源' : !selectedTypes.length ? '请先选择资源类型' : (!course.trim() && !chapter.trim() && !weakPoints.trim()) ? '请先填写课程、章节或薄弱点，再生成资源' : '生成资源'" :disabled="generating || !selectedTypes.length || (!course.trim() && !chapter.trim() && !weakPoints.trim())"><LoaderCircle v-if="generating" class="spin" :size="17" /><WandSparkles v-else :size="17" />{{ generating ? '多智能体生成中' : '生成资源' }} <ArrowRight :size="16" /></button></footer>
          </form>

          <section class="shot-records" :class="{ 'is-expanded': showAllRecords }"><header><strong><i class="shot-section-mark"></i>档案袋</strong><button type="button" :disabled="visibleResources.length <= 4" :aria-expanded="showAllRecords" @click="showAllRecords = !showAllRecords">{{ showAllRecords ? '收起' : '查看全部' }} <ArrowRight :size="14" /></button></header><div class="shot-record-grid"><button v-for="resource in displayedResources" :key="resource.id" type="button" class="shot-record-card" :class="{ active: selectedResource?.id === resource.id, 'is-deleting': deletingId === resource.id }" :disabled="deletingId === resource.id" @click="openResource(resource)"><span><strong>{{ resource.title }}</strong><em>{{ resource.type_label || labelForType(resource.type) }}</em></span><small>{{ formatDate(resource.created_at) }}</small><i><Check :size="12" />已完成</i><span class="shot-record-del" role="button" tabindex="0" :aria-label="`删除档案 ${resource.title}`" :title="`删除「${resource.title}」`" @click.stop="removeResource(resource)" @keydown.enter.stop.prevent="removeResource(resource)"><Trash2 :size="13" /></span></button><div v-if="!visibleResources.length" class="shot-empty">档案袋还是空的，提交上方需求生成后会自动归档到这里。</div></div></section>
        </main>

        <aside class="shot-workshop__side">
        <section class="shot-progress"><header><strong><i class="shot-section-mark"></i>协同生成进度</strong><small>{{ generating ? `正在生成：${selectedTypeLabels.join('、')}` : selectedResource ? `已载入：${selectedResource.title}` : '等待提交真实生成任务' }}</small></header><ol><li v-for="agent in displayTraceItems" :key="agent.key" :class="{ current: agent.status === 'running' }"><i><Check v-if="agent.status === 'completed' || agent.status === 'persisted'" :size="13" /><LoaderCircle v-else-if="agent.status === 'running'" class="spin" :size="13" /><Clock3 v-else :size="13" /></i><span><strong>{{ agent.label }}</strong><small>{{ agent.role }}</small></span><em><LoaderCircle v-if="agent.status === 'running'" class="spin" :size="12" /><Check v-else-if="agent.verified" :size="13" />{{ agent.status === 'running' ? '处理中' : agent.verified ? '已完成' : '等待' }}</em></li></ol><p v-if="!displayTraceItems.length" class="shot-progress-empty">尚无本轮真实处理事件</p></section>
          <section class="shot-preview"><header><strong><i class="shot-section-mark"></i>资源预览</strong></header><div class="shot-preview-paper"><template v-if="selectedResource"><header><span><FileText :size="14" /><strong>{{ selectedResource.title }}</strong><em>{{ resourceTypes.find((item) => item.value === selectedResource?.type)?.short || labelForType(selectedResource.type) }}</em></span><button class="shot-preview-open" type="button" @click="previewExpanded = true"><Maximize2 :size="12" />查看全文</button></header><div class="shot-preview-content"><div v-if="previewLoading">正在载入正文……</div><MarkdownContent v-else-if="readablePreviewContent" :content="readablePreviewContent" /><p v-else-if="previewError">{{ previewError }}</p><p v-else>{{ selectedResource.summary || '该资源没有可预览正文。' }}</p></div></template><p v-else>生成或选择一份资源后查看预览。</p></div></section>
          <Teleport to="body"><div v-if="previewExpanded && selectedResource" class="shot-preview-modal" role="dialog" aria-modal="true" @click.self="previewExpanded = false"><article :class="{ 'is-mindmap': !!mindmapSource }"><header><strong>{{ selectedResource.title }}</strong><div><button type="button" @click="openPreviewWindow"><ExternalLink :size="13" />新标签打开</button><button type="button" @click="previewExpanded = false"><X :size="14" />关闭</button></div></header><div class="shot-preview-modal__body"><template v-if="mindmapSource"><MindmapCanvas :source="mindmapSource" /><details class="mindmap-raw"><summary>查看文字版结构</summary><MarkdownContent :content="readablePreviewContent" /></details></template><MarkdownContent v-else-if="readablePreviewContent" :content="readablePreviewContent" /><p v-else>{{ previewError || '该资源没有可预览正文。' }}</p></div></article></div></Teleport>
          <section v-if="selectedResource" class="shot-smart-recommend"><header><strong><i class="shot-section-mark"></i>内容标签</strong><small>{{ selectedResource ? '按当前档案正文提取' : '点击档案袋中的文件提取' }}</small></header><div><span v-for="tag in contentKeywords" :key="tag">{{ tag }}</span><small v-if="keywordsLoading">正在从正文提取关键词……</small><small v-else-if="!contentKeywords.length">{{ keywordsHint }}</small></div></section>
          <section class="shot-export"><button type="button" :disabled="!selectedCount || exporting" @click="exportSelected"><FileArchive :size="16" />{{ exporting ? '打包中' : `导出已选 ${selectedCount || ''}` }}</button><a v-if="exportUrl" :href="exportUrl" target="_blank" rel="noreferrer"><Download :size="16" />下载 ZIP</a></section>
        </aside>
      </template>
    </section>


  </div>
</template>

<style scoped>

.shot-progress-empty { margin: 34px 0 0; padding: 24px 12px; color: #a69fb4; border: 1px dashed #e8f6f2; border-radius: 10px; background: #f7fcfb; font-size: 12px; text-align: center; }
.workshop-command-page { display: grid; gap: 12px; padding-top: 18px; }.spin { animation: workshop-spin .8s linear infinite; }
.workshop-topbar { display: flex; align-items: center; justify-content: space-between; gap: 24px; min-height: 58px; padding-bottom: 13px; border-bottom: 1px solid var(--cp-line); }.workshop-heading { display: flex; align-items: center; gap: 22px; min-width: 0; }.workshop-heading > div { display: flex; align-items: baseline; gap: 14px; min-width: 0; }.workshop-heading h1 { margin: 0; font-size: clamp(24px,2.2vw,32px); line-height: 1.1; letter-spacing: -.045em; }.workshop-heading p { overflow: hidden; margin: 0; color: var(--cp-muted); font-size: 11.5px; white-space: nowrap; text-overflow: ellipsis; }.workshop-topbar .os-page-actions { display: flex; flex: 0 0 auto; gap: 8px; }.workshop-topbar .os-button { min-height: 38px; }
.workshop-flowbar { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); overflow: hidden; border: 1px solid var(--cp-line); border-radius: 13px; background: rgba(255,255,255,.9); box-shadow: var(--cp-shadow-soft); }.flow-step { position: relative; display: grid; grid-template-columns: 27px minmax(0,1fr); align-items: center; gap: 9px; min-height: 52px; padding: 7px 14px; }.flow-step:not(:last-child)::after { position: absolute; top: 11px; right: 0; width: 1px; height: 30px; background: var(--cp-line); content: ''; }.flow-step > b { display: grid; place-items: center; width: 27px; height: 27px; color: var(--cp-muted); border-radius: 8px; background: #f7fcfb; font-size: 11.5px; }.flow-step > i { display: grid; gap: 2px; min-width: 0; font-style: normal; }.flow-step strong { font-size: 12px; }.flow-step small { overflow: hidden; color: var(--cp-muted); font-size: 11px; white-space: nowrap; text-overflow: ellipsis; }.flow-step.is-current { color: #fff; background: linear-gradient(120deg,#8acab5,#8acab5); }.flow-step.is-current > b { color: var(--cp-blue); background: #fff; }.flow-step.is-current small { color: #e8f6f2; }.flow-step.is-current::after { display: none; }.flow-delivery { color: #f7fcfb; background: #2e4a42; }.flow-delivery > b { color: #b7e1d4; background: rgba(255,255,255,.1); }.flow-delivery small { color: #c2e5da; }
.workshop-alert { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; padding: 10px 13px; }.workshop-alert > span { display: grid; gap: 2px; }.workshop-alert strong { font-size: 12px; }.workshop-alert small { color: var(--os-ink-soft); font-size: 11px; }.workshop-alert .os-button { min-height: 33px; }.workshop-notice { display: flex; align-items: center; gap: 8px; padding: 9px 13px; color: #5f9e88; border: 1px solid rgba(138, 202, 181,.18); border-radius: 10px; background: #f7fcfb; font-size: 12px; font-weight: 720; }
.workshop-telemetry { display: grid; grid-template-columns: repeat(3,minmax(130px,.55fr)) minmax(240px,1.2fr); overflow: hidden; border: 1px solid var(--cp-line); border-radius: 11px; background: rgba(255,255,255,.8); }.workshop-telemetry > span { display: flex; align-items: center; gap: 7px; min-width: 0; min-height: 38px; padding: 0 13px; color: var(--cp-blue); }.workshop-telemetry > span + span { border-left: 1px solid var(--cp-line); }.workshop-telemetry i { color: var(--cp-muted); font-size: 11.5px; font-style: normal; }.workshop-telemetry strong { color: var(--cp-text); font-size: 13px; }.workshop-telemetry small { color: var(--cp-muted); font-size: 11px; }.quality-telemetry strong { overflow: hidden; font-size: 12px; white-space: nowrap; text-overflow: ellipsis; }
.workshop-shell { display: grid; grid-template-columns: minmax(330px,.68fr) minmax(0,1.8fr); align-items: start; gap: 12px; }.task-rail { position: sticky; top: 74px; overflow: hidden; padding: 0; }.resource-config { display: grid; gap: 11px; padding: 15px; }.section-heading { display: flex; align-items: center; gap: 9px; min-width: 0; }.section-heading > div { display: grid; gap: 2px; min-width: 0; }.section-heading h2 { margin: 0; font-size: 16px; letter-spacing: -.02em; }.section-heading p { margin: 0; color: var(--cp-muted); font-size: 11px; }.section-index { display: grid; place-items: center; flex: 0 0 29px; width: 29px; height: 29px; color: var(--cp-blue); border: 1px solid rgba(138, 202, 181,.17); border-radius: 8px; background: var(--cp-blue-soft); font-size: 11.5px; font-weight: 850; }
.config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }.config-grid label,.field-stack { display: grid; gap: 5px; color: var(--cp-text); font-size: 11.5px; font-weight: 760; }.config-grid em { color: var(--cp-blue); font-style: normal; }.field-stack > span { display: flex; align-items: center; justify-content: space-between; }.field-stack > span small { color: var(--cp-blue); font-size: 11px; }.resource-config :is(input,textarea) { width: 100%; border: 1px solid var(--cp-line-strong); border-radius: 9px; background: #f7fcfb; color: var(--cp-text); font: inherit; font-size: 12px; box-sizing: border-box; }.resource-config input { height: 36px; padding: 0 10px; }.resource-config textarea { min-height: 65px; padding: 8px 10px; resize: vertical; line-height: 1.5; }.resource-config :is(input,textarea):focus { border-color: var(--cp-blue); outline: 3px solid rgba(138, 202, 181,.08); }.resource-type-fieldset { min-width: 0; margin: 0; padding: 0; border: 0; }.resource-type-fieldset legend { width: 100%; margin-bottom: 6px; font-size: 11.5px; font-weight: 760; }.resource-type-fieldset legend small { margin-left: 4px; color: var(--cp-muted); font-size: 11px; }.resource-type-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }.resource-type-option { display: grid; grid-template-columns: 30px minmax(0,1fr) auto; align-items: center; gap: 7px; min-height: 44px; padding: 5px 7px; color: var(--cp-text); border: 1px solid var(--cp-line); border-radius: 9px; background: #f7fcfb; text-align: left; cursor: pointer; }.resource-type-option:hover { border-color: rgba(138, 202, 181,.35); }.resource-type-option.is-selected { color: var(--cp-blue-ink); border-color: rgba(138, 202, 181,.38); background: var(--cp-blue-soft); box-shadow: inset 2px 0 0 var(--cp-blue); }.type-code { display: grid; place-items: center; width: 28px; height: 28px; color: var(--cp-blue); border-radius: 7px; background: #fff; font-size: 11px; font-weight: 850; }.resource-type-option > span:nth-child(2) { display: grid; gap: 1px; min-width: 0; }.resource-type-option strong { font-size: 11.5px; }.resource-type-option small { overflow: hidden; color: var(--cp-muted); font-size: 11px; white-space: nowrap; text-overflow: ellipsis; }.generation-summary { display: grid; gap: 9px; padding-top: 10px; border-top: 1px solid var(--cp-line); }.generation-summary > span { display: flex; align-items: center; gap: 7px; color: var(--cp-blue); }.generation-summary > span i { display: grid; gap: 2px; min-width: 0; font-style: normal; }.generation-summary strong { color: var(--cp-text); font-size: 11px; }.generation-summary small { overflow: hidden; color: var(--cp-muted); font-size: 11px; white-space: nowrap; text-overflow: ellipsis; }.generate-button { width: 100%; min-height: 38px; }.generation-live { display: grid; gap: 7px; padding: 9px; color: #5f9e88; border-radius: 9px; background: #f7fcfb; }.generation-live > span:last-child { display: flex; justify-content: space-between; gap: 6px; }.generation-live strong,.generation-live small { font-size: 11px; }.generation-live small { color: #7a738c; }.indeterminate-track { position: relative; height: 4px; overflow: hidden; border-radius: 99px; background: #e8f6f2; }.indeterminate-track i { position: absolute; width: 38%; height: 100%; border-radius: inherit; background: linear-gradient(90deg,var(--cp-blue),var(--cp-cyan)); animation: workshop-progress 1.4s ease-in-out infinite; }
.agent-console { display: grid; gap: 7px; padding: 12px 15px 14px; color: #f7fcfb; background: linear-gradient(145deg,#2e4a42,#2e4a42); }.agent-console > header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.agent-console > header > span:first-child { display: flex; align-items: center; gap: 6px; color: #c2e5da; font-size: 11px; font-weight: 800; letter-spacing: .11em; }.agent-console-status { display: flex; align-items: center; gap: 5px; color: #c2e5da; font-size: 11px; }.agent-console-status i { width: 5px; height: 5px; border-radius: 50%; background: #a69fb4; }.agent-console-status i.is-live { background: #77c2ae; box-shadow: 0 0 0 3px rgba(119, 194, 174,.12); }.agent-console h3 { margin: 0; font-size: 12px; }.agent-list { display: grid; max-height: 145px; overflow-y: auto; scrollbar-width: thin; }.agent-list article { display: grid; grid-template-columns: 25px minmax(0,1fr) auto; align-items: center; gap: 7px; padding: 6px 0; border-top: 1px solid rgba(194, 229, 218,.15); }.agent-index { display: grid; place-items: center; width: 23px; height: 23px; color: #b7e1d4; border: 1px solid rgba(194, 229, 218,.2); border-radius: 6px; background: rgba(95, 158, 136,.32); font-size: 11px; font-weight: 800; }.agent-list article > span:nth-child(2) { display: grid; gap: 1px; min-width: 0; }.agent-list strong { font-size: 11px; }.agent-list small { overflow: hidden; color: #8acab5; font-size: 11px; white-space: nowrap; text-overflow: ellipsis; }.agent-state { color: #8acab5; font-size: 11px; text-transform: uppercase; }.agent-state.is-verified { color: #77c2ae; }.agent-empty { padding: 18px 0; color: #8acab5; text-align: center; font-size: 11px; }.agent-console > footer { display: flex; align-items: flex-start; gap: 7px; padding: 8px; color: #77c2ae; border: 1px solid rgba(119, 194, 174,.17); border-radius: 8px; background: rgba(46, 74, 66,.32); }.agent-console > footer span { display: grid; gap: 2px; }.agent-console > footer strong { color: #e8f6f2; font-size: 11px; }.agent-console > footer small { color: #8acab5; font-size: 11px; }
.resource-delivery { min-width: 0; overflow: hidden; padding: 0; }.delivery-header { display: flex; align-items: center; justify-content: space-between; gap: 14px; min-height: 64px; padding: 10px 13px; border-bottom: 1px solid var(--cp-line); }.delivery-actions { display: flex; gap: 7px; }.delivery-actions .os-button { min-height: 34px; }.download-ready { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 8px; margin: 9px 11px 0; padding: 8px 10px; color: #5f9e88; border: 1px solid rgba(138, 202, 181,.2); border-radius: 9px; background: #f7fcfb; text-decoration: none; }.download-ready > span { display: grid; gap: 1px; }.download-ready strong { font-size: 11.5px; }.download-ready small { color: var(--cp-muted); font-size: 11px; }.delivery-grid { display: grid; grid-template-columns: minmax(235px,.62fr) minmax(0,1.5fr); min-height: 602px; }.resource-queue { min-width: 0; border-right: 1px solid var(--cp-line); background: #f7fcfb; }.resource-queue > header { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 39px; padding: 0 10px; border-bottom: 1px solid var(--cp-line); }.resource-queue > header > span { display: flex; align-items: center; gap: 6px; color: var(--cp-text); font-size: 11.5px; font-weight: 800; }.resource-queue > header small { color: var(--cp-muted); font-size: 11px; }.resource-list { display: grid; align-content: start; max-height: 562px; overflow-y: auto; scrollbar-width: thin; }.resource-list article { position: relative; display: grid; grid-template-columns: 28px minmax(0,1fr); align-items: center; min-width: 0; border-bottom: 1px solid var(--cp-line); background: rgba(255,255,255,.78); }.resource-list article:hover { background: #f7fcfb; }.resource-list article.is-active { z-index: 1; background: var(--cp-blue-soft); box-shadow: inset 3px 0 0 var(--cp-blue); }.resource-check { display: grid; place-items: center; align-self: stretch; border-right: 1px solid var(--cp-line); cursor: pointer; }.resource-check input { width: 13px; height: 13px; accent-color: var(--cp-blue); }.resource-open { display: grid; grid-template-columns: 30px minmax(0,1fr) auto; align-items: center; gap: 7px; min-width: 0; padding: 9px 8px; color: var(--cp-text); border: 0; background: transparent; text-align: left; cursor: pointer; }.resource-symbol { display: grid; place-items: center; width: 28px; height: 28px; color: var(--cp-blue); border-radius: 7px; background: #fff; }.resource-open > span:nth-child(2) { display: grid; gap: 2px; min-width: 0; }.resource-open small { color: var(--cp-blue); font-size: 11px; font-weight: 750; }.resource-open strong,.resource-open em { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }.resource-open strong { font-size: 11.5px; }.resource-open em { color: var(--cp-muted); font-size: 11px; font-style: normal; }.resource-list article > time { grid-column: 2; display: flex; align-items: center; gap: 4px; margin: -5px 8px 7px 38px; color: var(--cp-muted); font-size: 11px; }
.resource-preview { display: grid; grid-template-rows: auto minmax(0,1fr); min-width: 0; overflow: hidden; background: #fff; }.resource-preview > header { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 54px; padding: 9px 13px; border-bottom: 1px solid var(--cp-line); background: #f7fcfb; }.resource-preview header > div { display: grid; gap: 2px; min-width: 0; }.resource-preview h3 { overflow: hidden; margin: 0; font-size: 13px; white-space: nowrap; text-overflow: ellipsis; }.resource-preview header small { overflow: hidden; color: var(--cp-muted); font-size: 11px; white-space: nowrap; text-overflow: ellipsis; }.resource-preview > header .os-button { min-height: 32px; }.preview-scroll { height: 547px; overflow: auto; padding: 18px 22px; scrollbar-width: thin; }.preview-state { display: grid; place-items: center; align-content: center; gap: 9px; min-height: 460px; padding: 25px; color: var(--cp-muted); text-align: center; }.preview-state p { max-width: 380px; margin: 0; font-size: 11px; line-height: 1.6; }.preview-state.is-error { color: #c2586f; }
.resource-delivery > .cp-empty-state { min-height: 560px; }.workshop-next { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; padding: 10px 13px; }.workshop-next > span { display: grid; place-items: center; width: 34px; height: 34px; color: var(--cp-blue); border-radius: 9px; background: var(--cp-blue-soft); }.workshop-next > div { display: grid; gap: 2px; }.workshop-next strong { font-size: 11.5px; }.workshop-next small { color: var(--cp-muted); font-size: 11px; }.workshop-next .os-button { min-height: 34px; }
@keyframes workshop-spin { to { transform: rotate(360deg); } } @keyframes workshop-progress { 0% { left: -42%; } 55% { left: 44%; } 100% { left: 105%; } }
@media (max-width: 1180px) { .workshop-heading { align-items: flex-start; flex-direction: column; gap: 3px; }.workshop-shell { grid-template-columns: 1fr; }.task-rail { position: static; display: grid; grid-template-columns: minmax(0,1.65fr) minmax(280px,.7fr); }.agent-console { min-height: 100%; }.resource-type-grid { grid-template-columns: repeat(3,minmax(0,1fr)); } }
@media (max-width: 900px) { .workshop-topbar { align-items: flex-start; }.workshop-heading > div { align-items: flex-start; flex-direction: column; gap: 3px; }.workshop-flowbar { grid-template-columns: 1fr 1fr; }.flow-step:nth-child(2)::after { display: none; }.workshop-telemetry { grid-template-columns: 1fr 1fr; }.workshop-telemetry > span:nth-child(3) { border-left: 0; border-top: 1px solid var(--cp-line); }.workshop-telemetry > span:nth-child(4) { border-top: 1px solid var(--cp-line); }.task-rail { grid-template-columns: 1fr; }.resource-type-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }.delivery-grid { grid-template-columns: 1fr; }.resource-queue { border-right: 0; border-bottom: 1px solid var(--cp-line); }.resource-list { grid-template-columns: 1fr 1fr; max-height: 300px; }.resource-list article:nth-child(odd) { border-right: 1px solid var(--cp-line); }.preview-scroll { height: 480px; } }
@media (max-width: 680px) { .workshop-command-page { padding-top: 12px; }.workshop-topbar { flex-direction: column; }.workshop-topbar .os-page-actions { width: 100%; }.workshop-topbar .os-page-actions .os-button { flex: 1; }.workshop-flowbar { grid-template-columns: 1fr; }.flow-step::after { display: none; }.workshop-alert { grid-template-columns: auto 1fr; }.workshop-alert .os-button { grid-column: span 2; }.workshop-telemetry { grid-template-columns: 1fr 1fr; }.delivery-header { align-items: stretch; flex-direction: column; }.delivery-actions { width: 100%; }.delivery-actions .os-button { flex: 1; }.resource-list { grid-template-columns: 1fr; }.resource-list article:nth-child(odd) { border-right: 0; }.resource-preview > header { align-items: stretch; flex-direction: column; }.workshop-next { grid-template-columns: auto 1fr; }.workshop-next .os-button { grid-column: span 2; } }
@media (max-width: 440px) { .workshop-heading > .os-eyebrow { display: none; }.config-grid,.resource-type-grid,.workshop-telemetry { grid-template-columns: 1fr; }.workshop-telemetry > span + span { border-top: 1px solid var(--cp-line); border-left: 0; }.resource-config { padding: 12px; }.delivery-actions { flex-direction: column; }.workshop-next { grid-template-columns: 1fr; }.workshop-next > span { display: none; }.workshop-next .os-button { grid-column: auto; } }
@media (max-width: 900px) {
  .workshop-topbar { flex-direction: column; }
  .workshop-topbar .os-page-actions { width: 100%; min-width: 0; }
}



.workshop-command-page{--w-ink:#17324f;--w-muted:#5d7188;--w-line:#dce4ed;--w-blue:#245fb5;max-width:1540px;margin:0 auto;padding:24px 28px 40px;color:var(--w-ink);font-size:16px;line-height:1.6}
.shot-workshop{display:grid;grid-template-columns:minmax(0,1fr) minmax(270px,320px);align-items:start;gap:28px}
.shot-workshop__main,.shot-workshop__side{display:grid;align-content:start;gap:24px;min-width:0}.shot-workshop__main{grid-template-rows:auto}
.shot-workshop-hero{height:auto;padding:0 0 4px;border:0;border-bottom:1px solid var(--w-line);border-radius:0;background:none;box-shadow:none;min-height:0}
.shot-workshop-copy h1{margin:0;font-size:30px;line-height:1.3;letter-spacing:-.025em;color:var(--w-ink)}
.shot-workshop-copy h1 span{display:none}.shot-workshop-copy>p{margin:6px 0 0;color:var(--w-muted);font-size:15px}
.shot-create,.shot-records,.shot-progress,.shot-preview,.shot-smart-recommend{min-width:0;padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}
.shot-create>header{display:flex;align-items:baseline;flex-wrap:wrap;gap:12px;margin-bottom:16px}.shot-create>header strong{font-size:20px}.shot-create>header small{font-size:14px;color:var(--w-muted)}
.shot-type-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 20px;margin:0 0 18px;border-top:1px solid var(--w-line)}
.shot-type-grid button{position:relative;display:grid;grid-template-columns:24px minmax(0,1fr);align-items:center;gap:2px 10px;min-height:78px;padding:12px 8px;color:var(--w-ink);border:0;border-bottom:1px solid var(--w-line);border-radius:0;background:transparent;text-align:left;cursor:pointer}
.shot-type-grid button.active{background:#f2f6fc;box-shadow:inset 3px 0 #245fb5;color:#184b8e}.shot-type-grid button>i{display:grid;grid-row:span 2;width:24px;height:24px;place-items:center;color:#315f94;border-radius:0;background:none;font-size:14px}.shot-type-grid button>i svg{width:20px;height:20px}.shot-type-grid button strong{font-size:15px}.shot-type-grid button small{font-size:13px;white-space:normal;color:var(--w-muted)}.shot-type-grid button>svg{position:absolute;right:8px;top:15px;width:18px;height:18px}
.shot-brief-fields{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:14px}.shot-brief-fields label{display:grid;gap:6px}.shot-brief-fields label span,.workshop-brief-label{font-size:14px;font-weight:650;color:#405873}.shot-brief-fields input,.shot-create>textarea{width:100%;min-height:46px;padding:10px 12px;border:1px solid #cbd6e2;border-radius:7px;background:#fff;color:var(--w-ink);font:inherit;font-size:15px}.shot-create>textarea{min-height:120px;resize:vertical;line-height:1.65}.shot-create>textarea:focus,.shot-brief-fields input:focus{outline:3px solid #a8c5e9;outline-offset:1px;border-color:#396da9}.shot-brief-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:6px}.shot-char-count{display:inline;margin:0;text-align:right;font-size:13px;color:var(--w-muted)}
.shot-create>footer{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:12px}.shot-create>footer>div{display:flex;flex-wrap:wrap;gap:8px}.shot-create>footer>div button,.shot-generate{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:8px 14px;border:1px solid #cbd6e2;border-radius:7px;background:#fff;color:#244c7a;font:inherit;font-size:14px;cursor:pointer}.shot-generate{border-color:#245fb5;background:#245fb5;color:white;font-weight:650}.shot-generate:disabled{opacity:.55;cursor:not-allowed}.shot-file-input{display:none}
.shot-records>header,.shot-progress>header,.shot-preview>header,.shot-smart-recommend>header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.shot-records>header strong,.shot-progress>header strong,.shot-preview>header strong,.shot-smart-recommend>header strong{font-size:18px}.shot-records header button,.shot-preview header button{display:inline-flex;align-items:center;gap:6px;min-height:40px;padding:6px 8px;border:0;background:none;color:#245fb5;font:inherit;font-size:14px;cursor:pointer}.shot-section-mark{display:none}
.shot-record-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px;border-top:1px solid var(--w-line)}.shot-record-grid>button{position:relative;display:grid;grid-template-columns:minmax(0,1fr) auto;align-content:center;gap:4px 12px;min-height:82px;padding:10px 36px 10px 8px;border:0;border-bottom:1px solid var(--w-line);border-radius:0;background:transparent;color:var(--w-ink);text-align:left;cursor:pointer}.shot-record-grid>button.active{background:#f1f6fd;box-shadow:inset 3px 0 #245fb5}.shot-record-grid>button>span:first-child{display:grid;gap:2px;min-width:0}.shot-record-grid>button strong{overflow:hidden;font-size:14px;white-space:nowrap;text-overflow:ellipsis}.shot-record-grid>button em{font-size:13px;color:var(--w-muted);font-style:normal}.shot-record-grid>button small,.shot-record-grid>button>i{font-size:12px;color:var(--w-muted);font-style:normal}.shot-record-grid>button>i{align-self:center;color:#287a61}.shot-record-del{position:absolute;right:6px;top:50%;transform:translateY(-50%);display:grid;place-items:center;width:36px;height:36px;color:#64758a;cursor:pointer}.shot-empty{grid-column:1/-1;padding:20px 4px;color:var(--w-muted);font-size:14px}
.shot-workshop__side>section{padding:0 0 20px;border-bottom:1px solid var(--w-line)}.shot-progress>header{align-items:flex-start;flex-direction:column;gap:3px}.shot-progress>header small,.shot-smart-recommend>header small{font-size:13px;color:var(--w-muted)}.shot-progress ol{display:grid;gap:0;margin:8px 0 0;padding:0;list-style:none}.shot-progress li{display:grid;grid-template-columns:30px minmax(0,1fr) auto;align-items:center;gap:10px;padding:12px 0;border-top:1px solid #e8edf3}.shot-progress li>i{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#eaf1f8;color:#315e91}.shot-progress li>span{display:grid;gap:2px}.shot-progress li strong{font-size:14px}.shot-progress li small{font-size:13px;color:var(--w-muted)}.shot-progress li em{display:flex;align-items:center;gap:4px;color:#376b9e;font-size:12px;font-style:normal}.shot-progress-empty{margin:12px 0 0;color:var(--w-muted);font-size:14px}
.shot-preview-paper{min-height:170px;max-height:360px;overflow:auto;padding:16px 18px;border:1px solid #dce4ed;border-radius:8px;background:#fff;color:#344b64}.shot-preview-paper>p{margin:0;font-size:14px;color:var(--w-muted)}.shot-preview-paper>header{display:flex;justify-content:space-between;gap:8px;padding-bottom:10px;border-bottom:1px solid var(--w-line)}.shot-preview-paper>header>span{display:flex;align-items:center;flex-wrap:wrap;gap:7px;min-width:0}.shot-preview-paper>header strong{font-size:14px}.shot-preview-paper>header em{font-size:12px;font-style:normal;color:var(--w-muted)}.shot-preview-open{flex-shrink:0}.shot-preview-content{padding-top:10px;font-size:14px;line-height:1.7}.shot-preview .shot-dots{display:none}.shot-smart-recommend>div{display:flex;flex-wrap:wrap;gap:8px}.shot-smart-recommend>div>span{padding:5px 9px;border-radius:5px;background:#edf3fa;color:#315f94;font-size:13px}.shot-smart-recommend>div>small{font-size:14px;color:var(--w-muted)}.shot-export{display:flex;flex-wrap:wrap;gap:10px}.shot-export button,.shot-export a{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:8px 13px;border:1px solid #cbd6e2;border-radius:7px;background:#fff;color:#315f94;font:inherit;font-size:14px;text-decoration:none;cursor:pointer}.shot-export button:disabled{opacity:.5}
.shot-notice{display:flex;align-items:center;gap:10px;padding:12px 14px;border:1px solid #dce4ed;border-radius:8px;background:#f7f9fc;color:var(--w-ink);font-size:14px}.shot-notice.is-error{border-color:#e2baba;background:#fff8f7;color:#8b3030}.shot-notice button{min-height:40px;margin-left:auto;color:inherit;border:1px solid currentColor;border-radius:6px;background:white;padding:5px 12px;cursor:pointer}.shot-loading{display:flex;align-items:center;gap:12px;padding:16px;color:var(--w-muted)}.shot-workshop :is(button,a):focus-visible{outline:3px solid #77a2d4;outline-offset:3px}
@media(max-width:1100px){.shot-workshop{grid-template-columns:minmax(0,1fr) 280px;gap:20px}.shot-type-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.workshop-command-page{padding:20px}.shot-workshop{grid-template-columns:minmax(0,1fr)}.shot-workshop__side{grid-template-columns:1fr 1fr;column-gap:20px}.shot-workshop__side>.shot-progress,.shot-workshop__side>.shot-preview{grid-column:auto}.shot-workshop__side>.shot-smart-recommend,.shot-workshop__side>.shot-export{grid-column:1/-1}}
@media(max-width:520px){.workshop-command-page{padding:16px}.shot-workshop__side{grid-template-columns:minmax(0,1fr)}.shot-workshop__side>*{grid-column:1/-1}.shot-type-grid{grid-template-columns:1fr 1fr;column-gap:10px}.shot-brief-fields{grid-template-columns:1fr}.shot-create>footer{align-items:stretch;flex-direction:column}.shot-create>footer>div,.shot-create>footer>div button,.shot-generate{width:100%}.shot-record-grid{grid-template-columns:1fr}.shot-preview-paper{max-height:300px}}


</style>
