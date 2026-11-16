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
    '<style>body{margin:0;padding:36px 44px;background:#fff;color:#1f2d3d;',
    'font:14px/1.85 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}',
    'article{max-width:860px;margin:0 auto}h1,h2,h3,h4{color:#12335f;line-height:1.45}',
    'h1{font-size:24px}h2{font-size:19px;margin-top:28px}h3{font-size:16px}',
    'h4{font-size:14px}table{border-collapse:collapse;width:100%;margin:12px 0}',
    'th,td{border:1px solid #dbe6f6;padding:6px 10px;text-align:left}',
    'th{background:#f3f7ff}code{background:#f3f6fb;padding:1px 5px;border-radius:4px;font-size:12px}',
    'pre{background:#f7f9fd;padding:14px;border-radius:8px;overflow:auto}',
    'blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid #1769ff;background:#f5f9ff}',
    'hr{border:0;border-top:1px solid #e6eefb;margin:24px 0}</style></head><body><article>',
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
            <label for="workshop-brief" class="workshop-brief-label">学习需求</label><textarea id="workshop-brief" v-model="weakPoints" maxlength="500" rows="3" placeholder="请输入你的需求，例如：&#10;“生成《Python 函数》章节的讲解文档，重点讲解函数定义、参数、返回值，并配有示例代码”&#10;或上传参考资料，我们将基于你的需求生成高质量资源。"></textarea>
            <small class="shot-char-count">{{ weakPoints.length }}/500</small>
            <footer><div><button type="button" @click="chooseUpload('reference')"><Upload :size="14" />上传参考资料</button><button type="button" @click="chooseUpload('outline')"><FileInput :size="14" />导入课程大纲</button><input ref="uploadInput" class="shot-file-input" type="file" accept=".txt,.md,.csv,.json" @change="handleUpload" /></div><button class="shot-generate" type="submit" :disabled="generating || !selectedTypes.length || (!course.trim() && !chapter.trim() && !weakPoints.trim())"><LoaderCircle v-if="generating" class="spin" :size="17" /><WandSparkles v-else :size="17" />{{ generating ? '多智能体生成中' : '生成资源' }} <ArrowRight :size="16" /></button></footer>
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

.workshop-command-page{--w-ink:#17324f;--w-muted:#5d7188;--w-line:#dce4ed;--w-blue:#245fb5;max-width:1540px;margin:0 auto;padding:24px 28px 40px;color:var(--w-ink);font-size:16px;line-height:1.6}
.shot-workshop{display:grid;grid-template-columns:minmax(0,1fr) minmax(270px,320px);align-items:start;gap:28px}
.shot-workshop__main,.shot-workshop__side{display:grid;align-content:start;gap:24px;min-width:0}
.shot-workshop-hero{padding:0 0 4px;border:0;border-bottom:1px solid var(--w-line);border-radius:0;background:none;box-shadow:none;min-height:0}
.shot-workshop-copy h1{margin:0;font-size:30px;line-height:1.3;letter-spacing:-.025em;color:var(--w-ink)}
.shot-workshop-copy h1 span{display:none}.shot-workshop-copy>p{margin:6px 0 0;color:var(--w-muted);font-size:15px}
.shot-create,.shot-records,.shot-progress,.shot-preview,.shot-smart-recommend{min-width:0;padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}
.shot-create>header{display:flex;align-items:baseline;flex-wrap:wrap;gap:12px;margin-bottom:16px}.shot-create>header strong{font-size:20px}.shot-create>header small{font-size:14px;color:var(--w-muted)}
.shot-type-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 20px;margin:0 0 18px;border-top:1px solid var(--w-line)}
.shot-type-grid button{position:relative;display:grid;grid-template-columns:24px minmax(0,1fr);align-items:center;gap:2px 10px;min-height:78px;padding:12px 8px;color:var(--w-ink);border:0;border-bottom:1px solid var(--w-line);border-radius:0;background:transparent;text-align:left;cursor:pointer}
.shot-type-grid button.active{background:#f2f6fc;box-shadow:inset 3px 0 #245fb5;color:#184b8e}.shot-type-grid button>i{display:grid;grid-row:span 2;width:24px;height:24px;place-items:center;color:#315f94;border-radius:0;background:none;font-size:14px}.shot-type-grid button>i svg{width:20px;height:20px}.shot-type-grid button strong{font-size:15px}.shot-type-grid button small{font-size:13px;white-space:normal;color:var(--w-muted)}.shot-type-grid button>svg{position:absolute;right:8px;top:15px;width:18px;height:18px}
.shot-brief-fields{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:14px}.shot-brief-fields label{display:grid;gap:6px}.shot-brief-fields label span,.workshop-brief-label{font-size:14px;font-weight:650;color:#405873}.shot-brief-fields input,.shot-create>textarea{width:100%;min-height:46px;padding:10px 12px;border:1px solid #cbd6e2;border-radius:7px;background:#fff;color:var(--w-ink);font:inherit;font-size:15px}.shot-create>textarea{min-height:120px;resize:vertical;line-height:1.65}.shot-create>textarea:focus,.shot-brief-fields input:focus{outline:3px solid #a8c5e9;outline-offset:1px;border-color:#396da9}.shot-char-count{display:block;text-align:right;font-size:13px;color:var(--w-muted);margin-top:3px}
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
