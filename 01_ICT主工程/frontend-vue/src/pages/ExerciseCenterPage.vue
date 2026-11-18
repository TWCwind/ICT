<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { generatePathStageQuestions, getPathOverview, type PathOverview } from '@/api/learningApi'
import { useStudent } from '@/composables/useStudent'
import { activeQuestionBankStorageKey, readActiveQuestionBankIds } from '@/utils/practiceStorage'
import { hashText } from '@/utils/hashText'
import type { TagGalaxyEngine } from '@/composables/useTagGalaxyScene'
import {
  baseCourseCatalog,
  majorCatalog,
  majorSpecificCourseCatalog,
  practiceCourseCatalog,
  professionalCourseCatalog,
} from '@/data/practiceCatalogs'
// 练习页（1346 行）只在点「开始做题」后才需要，异步加载可以把它从练习中心首屏 chunk 里拆走。
const ExercisePage = defineAsyncComponent(() => import('@/pages/ExercisePage.vue'))
// three 只在「历史星系」页签里用到，改成按需加载：练习页首屏不再背 ~600KB 的 3D 引擎。
type ResourceItem = {
  id: string
  type: string
  tags: string[]
  content_uri: string
  title?: string
  created_at?: string
  meta?: Record<string, any>
}

type WorkshopPageKey = 'builder' | 'wrongBook' | 'tagGalaxy' | 'diagnosis'
type ExercisePageExpose = {
  loadSession: (forceRefresh?: boolean) => Promise<boolean>
  resetForNewPaper: () => Promise<boolean>
  finishExam: () => Promise<boolean>
  hasActiveExam: () => boolean
  focusPracticeHeading: () => void
}

const { studentId } = useStudent()
const route = useRoute()

// 专业 / 课程目录数据见 ../data/practiceCatalogs.ts
const selectedMajorCategory = ref('工学')
const selectedMajor = ref('软件工程')
const customMajor = ref('')
const selectedCourseCategory = ref('软件工程专业课程')
const selectedCourse = ref('软件需求分析与建模')
const customCourseCategory = ref('')
const customCourse = ref('')
const activePage = ref<WorkshopPageKey>('builder')
const hasUserSelectedExercisePage = ref(false)
const exerciseContextReady = ref(false)
const practiceStarted = ref(false)
const pendingPage = ref<WorkshopPageKey | null>(null)
const showExamLeaveDialog = ref(false)
const courseLocked = ref(false)
const exerciseResetSeed = ref(0)
const exercisePageRef = ref<ExercisePageExpose | null>(null)
const specificKnowledgePoint = ref('用例建模中的系统边界识别')
const knowledgePoint = ref('参与者识别、用例粒度、include/extend 关系、业务场景抽象')
const weaknessDetail = ref('不会区分用户目标和功能点，容易把按钮、页面、接口都写成用例。')
const specialRequirement = ref('题目尽量结合校园预约、在线选课、实验室管理等业务场景，案例题要能训练完整分析过程。')
const requirement = ref<Record<string, any> | null>(null)
const generating = ref(false)
const events = ref<any[]>([])
const resources = ref<ResourceItem[]>([])
const selectedQuestionBankIds = ref<string[]>(readActiveQuestionBankIds(studentId.value))
const error = ref('')
const closedLoopStatus = ref('题库生成后会自动进入训练诊断。')
const questionDifficulty = ref('mixed')
const activeExerciseQuestionLimit = ref(50)
const activeExerciseDifficulty = ref('mixed')
const questionTypeCounts = ref<Record<string, number>>({
  single_choice: 4,
  multiple_choice: 2,
  true_false: 2,
  blank: 0,
  short_answer: 1,
  case_analysis: 1,
  calculation: 0,
  matching: 0,
  ordering: 0,
})
const pathOverview = ref<PathOverview | null>(null)
const currentPathStage = ref<Record<string, any> | null>(null)
const pathContextLoading = ref(false)

const questionBankResources = computed(() => resources.value.filter((r) => r.type === 'question_bank'))
const activeQuestionBankIds = computed(() => selectedQuestionBankIds.value)
const requestedStageId = computed(() => String(route.query.stage || ''))
const requestedBankId = computed(() => String(route.query.bank || ''))
const shouldAutoStartStageBank = computed(() => String(route.query.autostart || '') === '1')
const pathCourseTitle = computed(() => pathOverview.value?.title || '当前学习路径')
const pathStageTitle = computed(() => String(currentPathStage.value?.title || '等待路径阶段'))
const pathStageGoal = computed(() => String(currentPathStage.value?.goal || currentPathStage.value?.checkpoint || '请先在路径推送中选择当前学习阶段。'))
const pathStageMastery = computed(() => Math.max(0, Math.min(100, Number(currentPathStage.value?.mastery) || 0)))
const pathStageProgressText = computed(() => {
  const answered = Number(currentPathStage.value?.answered_count) || 0
  const target = Number(currentPathStage.value?.target_count) || totalQuestionCount.value
  return `${answered} / ${Math.max(1, target)} 题`
})
const questionTypeOptions = [
  { value: 'single_choice', label: '单选题', hint: '概念辨析、基础判断' },
  { value: 'multiple_choice', label: '多选题', hint: '多条件识别、组合判断' },
  { value: 'true_false', label: '判断题', hint: '快速检测易错概念' },
  { value: 'blank', label: '填空题', hint: '关键词、定义、公式补全' },
  { value: 'short_answer', label: '简答题', hint: '步骤说明、原因分析' },
  { value: 'case_analysis', label: '案例分析', hint: '真实场景迁移应用' },
  { value: 'calculation', label: '计算题', hint: '公式推导、数值求解' },
  { value: 'matching', label: '匹配题', hint: '概念与解释配对' },
  { value: 'ordering', label: '排序题', hint: '流程、步骤、时序排序' },
]
const wrongBook = ref<any | null>(null)
const wrongBookLoading = ref(false)
const wrongBookError = ref('')
const galaxyRefreshing = ref(false)
const galaxyRefreshFeedback = ref('')
const selectedWrongRecordIds = ref<string[]>([])
const openCourseFolders = ref<Record<string, boolean>>({})
const exerciseRadarImpact = ref<Record<string, number>>({})
// 星系引擎状态见 @/composables/useTagGalaxyScene
const prefersReducedMotion = ref(false)
const activeGalaxyTag = ref('')

// 星系引擎按需加载：只有真的打开「错题标签星系」页签时才 import 这份 1400 行的 3D 代码。
const galaxyCanvas = ref<HTMLCanvasElement | null>(null)
const galaxyZoom = ref(1)
const masteredGalaxyStars = ref<any[]>([])
const galaxyEngine = shallowRef<TagGalaxyEngine | null>(null)
let galaxyEngineLoading: Promise<TagGalaxyEngine> | null = null

async function loadGalaxyEngine() {
  if (galaxyEngine.value) return galaxyEngine.value
  if (!galaxyEngineLoading) {
    galaxyEngineLoading = import('@/composables/useTagGalaxyScene').then(({ createTagGalaxyScene }) => {
      const engine = createTagGalaxyScene({
        isActive: () => activePage.value === 'tagGalaxy',
        nodes: () => tagGalaxy.value.nodes,
        links: () => tagGalaxy.value.links,
        reducedMotion: () => prefersReducedMotion.value,
        activeTag: activeGalaxyTag,
        canvasRef: galaxyCanvas,
        zoomRef: galaxyZoom,
        masteredStarsRef: masteredGalaxyStars,
      })
      if (pendingGalaxyReset) {
        engine.resetGalaxyScene({ version: true })
        pendingGalaxyReset = false
      }
      galaxyEngine.value = engine
      return engine
    })
  }
  return galaxyEngineLoading
}

async function startTagGalaxy() {
  await loadGalaxyEngine()
  await galaxyEngine.value?.start()
}

function stopTagGalaxy() {
  galaxyEngine.value?.stop()
}

function disposeTagGalaxyScene() {
  galaxyEngine.value?.dispose()
  galaxyEngine.value = null
  galaxyEngineLoading = null
}

function refreshGalaxyFocusState() {
  return galaxyEngine.value?.refreshFocus() ?? false
}

// 引擎还没加载时（第一次进星系页签前）先把「需要重建」记下来，等引擎就绪再补上，
// 否则「刷新星系」在首帧之前触发会被吞掉。
let pendingGalaxyReset = false
function resetGalaxyScene(options?: { version?: boolean }) {
  if (galaxyEngine.value) {
    galaxyEngine.value.resetGalaxyScene(options)
  } else {
    pendingGalaxyReset = true
  }
}

function markNeedsRebuild() {
  galaxyEngine.value?.markNeedsRebuild()
}

function clearSignature() {
  galaxyEngine.value?.clearSignature()
}

function withGalaxy<T>(call: (engine: TagGalaxyEngine) => T, fallback: T): T {
  return galaxyEngine.value ? call(galaxyEngine.value) : fallback
}

const onGalaxyClick = (event: MouseEvent) => withGalaxy((e) => { e.onGalaxyClick(event); return undefined }, undefined)
const onGalaxyPointerMove = (event: MouseEvent) => withGalaxy((e) => { e.onGalaxyPointerMove(event); return undefined }, undefined)
const onGalaxyPointerLeave = () => withGalaxy((e) => { e.onGalaxyPointerLeave(); return undefined }, undefined)
const onGalaxyWheel = (event: WheelEvent) => withGalaxy((e) => { e.onGalaxyWheel(event); return undefined }, undefined)
const onGalaxyKeydown = (event: KeyboardEvent) => withGalaxy((e) => { e.onGalaxyKeydown(event); return undefined }, undefined)
let galaxyRefreshFeedbackTimer: number | null = null
const redoSession = ref<{
  scope: 'single' | 'course' | 'all'
  title: string
  queue: any[]
  index: number
  completed: boolean
  correct: number
  wrong: number
} | null>(null)
const redoAnswer = ref('')
const redoResult = ref<any | null>(null)
const totalQuestionCount = computed(() => {
  return questionTypeOptions.reduce((sum, option) => sum + normalizedTypeCount(option.value), 0)
})
const questionDifficultyLabel = computed(() => ({
  mixed: '由易到难混合',
  easy: '基础巩固',
  medium: '中等应用',
  hard: '综合提升',
}[questionDifficulty.value] || '自定义难度'))
const selectedQuestionTypes = computed(() => {
  const types = questionTypeOptions.map((option) => option.value).filter((type) => normalizedTypeCount(type) > 0)
  return types.length ? types : ['single_choice']
})
const majorOptions = computed(() => {
  const majors = majorCatalog.find((item) => item.category === selectedMajorCategory.value)?.majors || ['其它']
  return majors.includes('其它') ? majors : [...majors, '其它']
})
const courseCatalog = computed(() => {
  if (selectedMajor.value === '其它' || selectedMajorCategory.value === '其它') {
    return [{ category: '其它', courses: ['其它'] }]
  }
  const majorCourses = professionalCourseCatalog[selectedMajorCategory.value] || []
  const specificCourses = majorSpecificCourseCatalog[selectedMajor.value] || []
  return [...specificCourses, ...majorCourses, ...baseCourseCatalog, ...practiceCourseCatalog, { category: '其它', courses: ['其它'] }]
})
const courseOptions = computed(() => {
  const courses = courseCatalog.value.find((item) => item.category === selectedCourseCategory.value)?.courses || ['其它']
  return courses.includes('其它') ? courses : [...courses, '其它']
})
const effectiveMajor = computed(() => selectedMajor.value === '其它' ? customMajor.value.trim() || '自定义专业' : selectedMajor.value)
const effectiveCourseCategory = computed(() => selectedCourseCategory.value === '其它' ? customCourseCategory.value.trim() || '自定义课程类别' : selectedCourseCategory.value)
const effectiveCourse = computed(() => selectedCourse.value === '其它' ? customCourse.value.trim() || '自定义课程内容' : selectedCourse.value)
const abilityRadar = computed(() => {
  const rawValues = wrongBook.value?.ability_radar || []
  const values = rawValues.length ? rawValues : [
    { name: '基础知识掌握能力', score: 0, total: 0 },
    { name: '逻辑思维', score: 0, total: 0 },
    { name: '运算处理能力', score: 0, total: 0 },
    { name: '抽象概括能力', score: 0, total: 0 },
    { name: '应用迁移能力', score: 0, total: 0 },
    { name: '错因复盘能力', score: 0, total: 0 },
  ]
  const impacts = exerciseRadarImpact.value
  return values.map((item: any) => {
    const delta = Number(impacts[item.name] || 0)
    const score = Math.max(0, Math.min(100, Number(item.score ?? 0) + delta))
    return { ...item, score, training_delta: delta }
  })
})
const radarPoints = computed(() => abilityRadar.value.map((item: any, index: number) => radarPoint(index, Number(item.score) || 0)).join(' '))
const radarOldPoints = computed(() => abilityRadar.value.map((item: any, index: number) => radarPoint(index, Number(item.old_score ?? 0) || 0)).join(' '))
const radarSignature = computed(() => `${wrongBookStats.value.totalWrong}-${wrongBookStats.value.tagCount}-${radarOldPoints.value}-${radarPoints.value}`)
const currentRedoRecord = computed(() => redoSession.value?.queue[redoSession.value.index] || null)
const currentRedoIsMultiple = computed(() => isMultipleQuestion(currentRedoRecord.value))
const redoOptions = computed(() => {
  const record = currentRedoRecord.value
  const options = normalizeOptions(record?.options || [])
  if (!options.length && record?.stem) {
    const stemOptions = normalizeOptions([record.stem])
    if (stemOptions.length > 1) return stemOptions
  }
  if (!options.length && record?.type === 'true_false') return normalizeOptions(['A. 正确', 'B. 错误'])
  return options
})
const wrongBookStats = computed(() => {
  const groups = wrongBook.value?.groups || []
  const courseCount = groups.reduce((sum: number, group: any) => sum + (group.courses?.length || 0), 0)
  const totalWrong = groups.reduce((sum: number, group: any) => sum + (Number(group.count) || 0), 0)
  return {
    totalWrong,
    courseCount,
    tagCount: wrongBook.value?.tag_summary?.length || 0,
  }
})
const courseFolders = computed(() => {
  return (wrongBook.value?.groups || []).flatMap((major: any) =>
    (major.courses || []).map((course: any) => ({
      major: major.major,
      course: course.course,
      count: course.count,
      items: course.items || [],
      key: folderKey(major.major, course.course),
    }))
  )
})
const allCourseFoldersOpen = computed(() => {
  return !!courseFolders.value.length && courseFolders.value.every((folder: any) => openCourseFolders.value[folder.key])
})
const selectedWrongRecords = computed(() => {
  const ids = new Set(selectedWrongRecordIds.value)
  return (wrongBook.value?.records || []).filter((record: any) => ids.has(String(record.id)))
})
const redoAllButtonText = computed(() => selectedWrongRecords.value.length ? `重做已选 ${selectedWrongRecords.value.length} 题` : '一键重做')
const tagGalaxy = computed(() => {
  const records = wrongBook.value?.records || []
  const nodeMap = new Map<string, any>()
  const linkMap = new Map<string, any>()
  const clusterMap = new Map<string, number>()

  for (const record of records) {
    const tags = Array.isArray(record.tags) ? record.tags.map((tag: any) => String(tag).trim()).filter(Boolean) : []
    const major = String(record.major || effectiveMajor.value || '通用能力')
    const course = String(record.course || effectiveCourse.value || '综合练习')
    const knowledge = String(record.knowledge_point || record.chapter || '综合知识点')
    const clusterKey = `${major} / ${course}`
    if (!clusterMap.has(clusterKey)) clusterMap.set(clusterKey, clusterMap.size)

    for (const tag of tags) {
      const node = nodeMap.get(tag) || {
        tag,
        count: 0,
        major,
        course,
        knowledge,
        clusterKey,
        courses: new Set<string>(),
        points: new Set<string>(),
      }
      node.count += 1
      node.courses.add(course)
      node.points.add(knowledge)
      nodeMap.set(tag, node)
    }

    for (let i = 0; i < tags.length; i += 1) {
      for (let j = i + 1; j < tags.length; j += 1) {
        const [a, b] = [tags[i], tags[j]].sort()
        const key = `${a}::${b}`
        const link = linkMap.get(key) || { source: a, target: b, weight: 0, reason: clusterKey }
        link.weight += 2
        linkMap.set(key, link)
      }
    }
  }

  const rawLinks = Array.from(linkMap.values())
  const activeTag = activeGalaxyTag.value
  const relatedEntries = activeTag
    ? rawLinks
        .filter((link: any) => link.source === activeTag || link.target === activeTag)
        .map((link: any) => ({
          tag: link.source === activeTag ? link.target : link.source,
          weight: Number(link.weight) || 1,
        }))
        .sort((a, b) => b.weight - a.weight || a.tag.localeCompare(b.tag))
    : []
  const relatedOrder = new Map(relatedEntries.map((item, index) => [item.tag, { ...item, index }]))
  const maxRelatedWeight = Math.max(1, ...relatedEntries.map((item) => item.weight))
  const clusters = Math.max(1, clusterMap.size)
  const nodes = Array.from(nodeMap.values()).map((node: any, index) => {
    const clusterIndex = clusterMap.get(node.clusterKey) || 0
    const clusterAngle = (Math.PI * 2 * clusterIndex) / clusters
    const orbit = 88 + Math.min(70, node.count * 12)
    const drift = (hashText(node.tag) % 100) / 100
    const local = (index * 0.72 + drift * 2.4) % (Math.PI * 2)
    const hue = (clusterIndex * 61 + 206) % 360
    const relation = relatedOrder.get(node.tag)
    const focusMode = Boolean(activeTag)
    const isCenter = activeTag === node.tag
    const isRelated = Boolean(relation)
    const relationIndex = relation?.index ?? index
    const relationWeight = relation?.weight ?? 0
    const focusAngle = relationIndex * 2.399963 + drift * 0.5
    const focusOrbit = isCenter
      ? 0
      : isRelated
        ? 78 + (relationIndex % 3) * 34 + (maxRelatedWeight - relationWeight) * 9
        : 220 + (index % 4) * 36
    const focusY = isCenter
      ? 0
      : isRelated
        ? Math.sin(focusAngle * 1.4) * 48
        : Math.sin(local * 1.3) * 84
    return {
      ...node,
      x: focusMode ? Math.cos(focusAngle) * focusOrbit : Math.cos(clusterAngle) * orbit + Math.cos(local) * 36,
      y: focusMode ? focusY : Math.sin(local * 1.3) * 58,
      z: focusMode ? Math.sin(focusAngle) * focusOrbit : Math.sin(clusterAngle) * orbit + Math.sin(local) * 36,
      hue,
      color: `hsl(${hue} 82% 56%)`,
      focusMode,
      isCenter,
      isRelated,
      relationWeight,
      orbitRadius: focusOrbit,
      orbitPhase: focusAngle,
      orbitSpeed: isRelated ? 0.35 + (relationIndex % 5) * 0.08 : 0.16,
      courses: Array.from(node.courses),
      points: Array.from(node.points),
    }
  })
  const nodeSet = new Set(nodes.map((node: any) => node.tag))
  const links = rawLinks.filter((link: any) => nodeSet.has(link.source) && nodeSet.has(link.target))
  return { nodes, links, clusters: Array.from(clusterMap.keys()) }
})

function syncMajorCategory() {
  selectedMajor.value = majorOptions.value[0] || ''
  syncCourseCatalog()
  syncCustomizationDefaults()
}

function syncMajor() {
  syncCourseCatalog()
  syncCustomizationDefaults()
}

function syncCourseCatalog() {
  selectedCourseCategory.value = courseCatalog.value[0]?.category || '其它'
  selectedCourse.value = courseOptions.value[0] || ''
  syncCustomizationDefaults()
}

function syncCourse() {
  selectedCourse.value = courseOptions.value[0] || ''
  syncCustomizationDefaults()
}

function syncCustomizationDefaults() {
  const course = effectiveCourse.value
  const major = effectiveMajor.value
  const presets: Record<string, { point: string; range: string; weakness: string; special: string }> = {
    软件需求分析与建模: {
      point: '用例建模中的系统边界识别',
      range: '参与者识别、用例粒度、include/extend 关系、业务场景抽象',
      weakness: '不会区分用户目标和功能点，容易把按钮、页面、接口都写成用例。',
      special: '题目尽量结合校园预约、在线选课、实验室管理等业务场景，案例题要能训练完整分析过程。',
    },
    数据结构: {
      point: '链表、栈、队列与树结构的适用场景判断',
      range: '时间复杂度、空间复杂度、递归、遍历、查找与排序',
      weakness: '容易只记住结构定义，不会根据题目场景判断应该选哪种数据结构。',
      special: '增加代码阅读题和复杂度分析题，题目要覆盖基础概念到应用迁移。',
    },
    计算机网络: {
      point: 'TCP/IP 分层模型与可靠传输机制',
      range: '三次握手、四次挥手、拥塞控制、HTTP、DNS、网络安全基础',
      weakness: '容易混淆不同协议所在层级，不会解释协议机制背后的原因。',
      special: '增加协议流程排序题和网络故障排查案例题。',
    },
    机器学习: {
      point: '监督学习模型选择与过拟合判断',
      range: '训练集/测试集、损失函数、正则化、评估指标、交叉验证',
      weakness: '能记住算法名称，但不会根据数据特征选择模型和解释评估指标。',
      special: '增加指标计算题和真实业务分类场景案例题。',
    },
    会计学原理: {
      point: '借贷记账法与会计分录编制',
      range: '会计要素、账户结构、试算平衡、凭证与账簿',
      weakness: '容易判断错借贷方向，对经济业务和会计科目的对应关系不稳定。',
      special: '增加经济业务场景题和分录纠错题。',
    },
    民法: {
      point: '民事法律关系与合同效力判断',
      range: '主体、客体、意思表示、代理、违约责任、侵权责任',
      weakness: '读案例时容易漏掉关键事实，不能稳定提取法律关系。',
      special: '增加案例分析题，要求按事实、争点、规则、结论展开。',
    },
  }
  const preset = presets[course] || {
    point: `${course}的核心概念与典型应用`,
    range: `${course}的基础概念、关键流程、常见误区、综合应用`,
    weakness: `我想针对${major}专业中${course}的易混概念和应用题进行训练。`,
    special: '题目需要从基础理解逐步过渡到综合应用，并给出适合比赛录屏展示的诊断闭环。',
  }
  specificKnowledgePoint.value = preset.point
  knowledgePoint.value = preset.range
  weaknessDetail.value = preset.weakness
  specialRequirement.value = preset.special
}

function doClarify() {
  error.value = ''
  const dialogueRequirement = [
    `具体知识点：${specificKnowledgePoint.value}`,
    `关联知识范围：${knowledgePoint.value}`,
    `薄弱点：${weaknessDetail.value}`,
    `特殊定制需求：${specialRequirement.value}`,
  ].filter((item) => !item.endsWith('：')).join('\n')
  const weakPoints = extractWeakPoints(weaknessDetail.value || dialogueRequirement)
  requirement.value = {
    major_category: selectedMajorCategory.value,
    major: effectiveMajor.value,
    course_category: effectiveCourseCategory.value,
    course: effectiveCourse.value,
    chapter: specificKnowledgePoint.value || effectiveCourse.value,
    specific_knowledge_point: specificKnowledgePoint.value,
    knowledge_points: knowledgePoint.value,
    goals: dialogueRequirement,
    weak_points: weakPoints,
    special_requirements: specialRequirement.value,
    preferred_resources: ['question_bank'],
    constraints: { source: 'major_course_dialogue', difficulty: questionDifficulty.value },
    dialogue_requirement: dialogueRequirement,
  }
  applyQuizConfig()
  closedLoopStatus.value = '已根据专业、课程和对话内容生成题库需求。'
  activePage.value = 'builder'
}

function extractWeakPoints(text: string) {
  const patterns = ['不懂', '不会', '不理解', '没听懂', '搞不清', '混淆', '容易错', '短板是', '薄弱点是', '卡在']
  const items: string[] = []
  for (const part of text.split(/[。；;\n]/)) {
    if (patterns.some((p) => part.includes(p))) items.push(part.trim())
  }
  return items.length ? items.slice(0, 6) : [text.slice(0, 80)]
}

function setActiveQuestionBankIds(ids: string[]) {
  selectedQuestionBankIds.value = [...new Set(ids.map(String).filter(Boolean))]
  try {
    window.localStorage.setItem(
      activeQuestionBankStorageKey(studentId.value),
      JSON.stringify(selectedQuestionBankIds.value),
    )
  } catch {
    // localStorage 不可用时仍可在当前页面使用生成题库。
  }
}

function applyActiveQuestionBankConfig(banks: ResourceItem[]) {
  const configs = banks
    .map((bank) => bank.meta?.requirement?.question_config || bank.meta?.question_config || null)
    .filter((config) => config && typeof config === 'object')
  const configuredCount = configs.reduce((sum, config) => sum + Math.max(0, Number(config.count) || 0), 0)
  activeExerciseQuestionLimit.value = configuredCount ? Math.max(1, Math.min(50, configuredCount)) : 50
  activeExerciseDifficulty.value = String(configs[configs.length - 1]?.difficulty || 'mixed')
}

async function loadPathContext() {
  pathContextLoading.value = true
  try {
    const data = await getPathOverview(studentId.value)
    pathOverview.value = data
    const requested = (data.nodes || []).find((node: any) => String(node.id || '') === requestedStageId.value)
    const fallback = data.current_stage || (data.nodes || []).find((node: any) => ['current', 'active', 'warning'].includes(String(node.status)))
    const stage = requested && requested.status !== 'locked' ? requested : fallback
    currentPathStage.value = stage || null
    if (!stage) {
      error.value = '当前没有可用的学习阶段，请先到路径推送生成学习路径。'
      if (!hasUserSelectedExercisePage.value) activePage.value = 'builder'
      return
    }
    specificKnowledgePoint.value = String(stage.title || '')
    knowledgePoint.value = String(stage.goal || stage.checkpoint || '')
    weaknessDetail.value = `围绕路径节点“${stage.title || '当前阶段'}”检测掌握情况。`
    specialRequirement.value = '题目仅覆盖当前路径阶段，完成后自动更新掌握度并判定是否进入下一阶段。'
    const target = Number(stage.target_count) || 0
    if (target) activeExerciseQuestionLimit.value = Math.max(1, Math.min(50, target))
  } catch (reason: any) {
    error.value = reason?.message || '当前路径阶段加载失败'
    currentPathStage.value = null
    if (!hasUserSelectedExercisePage.value) activePage.value = 'builder'
  } finally {
    pathContextLoading.value = false
  }
}

async function restoreActiveQuestionBanks() {
  try {
    const resp = await fetch(`/api/resources?student_id=${encodeURIComponent(studentId.value)}`)
    if (!resp.ok) return
    const payload = await resp.json()
    if (!payload?.success) return
    const banks = (payload.data?.resources || []).filter((resource: ResourceItem) => (
      resource.type === 'question_bank'
      && resource.id
      && resource.meta?.requirement?.constraints?.source === 'path_stage_quiz'
      && String(resource.meta?.requirement?.constraints?.path_stage_id || '') === String(currentPathStage.value?.id || '')
    ))
    resources.value = banks
    if (!banks.length) {
      setActiveQuestionBankIds([])
      activeExerciseQuestionLimit.value = Math.max(1, Math.min(50, totalQuestionCount.value || 10))
      activeExerciseDifficulty.value = 'mixed'
      if (!hasUserSelectedExercisePage.value) activePage.value = 'builder'
      return
    }
    const orderedBanks = [...banks].sort((left: ResourceItem, right: ResourceItem) => {
      const leftTime = Date.parse(left.created_at || '') || 0
      const rightTime = Date.parse(right.created_at || '') || 0
      return leftTime - rightTime
    })
    const latestBank = orderedBanks[orderedBanks.length - 1]
    const availableIds = new Set(banks.map((resource: ResourceItem) => String(resource.id)))
    const stageBankIds = Array.isArray(currentPathStage.value?.question_bank_ids)
      ? currentPathStage.value!.question_bank_ids.map(String).filter((id: string) => availableIds.has(id))
      : []
    const preferredId = availableIds.has(requestedBankId.value)
      ? requestedBankId.value
      : String(currentPathStage.value?.active_question_bank_id || latestBank.id)
    const restoredIds = preferredId && availableIds.has(preferredId)
      ? [preferredId]
      : stageBankIds.length ? [stageBankIds[stageBankIds.length - 1]] : [latestBank.id]
    setActiveQuestionBankIds(restoredIds)
    applyActiveQuestionBankConfig(banks.filter((bank: ResourceItem) => restoredIds.includes(String(bank.id))))
    if (!hasUserSelectedExercisePage.value) activePage.value = 'diagnosis'
  } catch {
    setActiveQuestionBankIds([])
  }
}

async function doGenerate(): Promise<boolean> {
  if (!requirement.value || generating.value) return false
  applyQuizConfig()
  events.value = []
  resources.value = []
  generating.value = true
  error.value = ''
  closedLoopStatus.value = '正在根据专业、课程和学习短板生成个性化题库...'
  const generatedQuestionBankIds: string[] = []

  const consumeChunk = (chunk: string) => {
    const line = chunk.split('\n').find((item) => item.startsWith('data: '))
    if (!line) return
    try {
      const data = JSON.parse(line.slice(6))
      if (data?.error) {
        error.value = String(data.error)
        return
      }
      const evt = data.event
      if (!evt) return
      events.value.push(evt)
      if (evt.type === 'agent_done' && evt.resource) {
        const resource = evt.resource as ResourceItem
        resources.value.unshift(resource)
        if (resource.type === 'question_bank' && resource.id && !generatedQuestionBankIds.includes(resource.id)) {
          generatedQuestionBankIds.push(resource.id)
        }
      }
    } catch {
      // 忽略不完整 SSE 片段。
    }
  }

  try {
    const resp = await fetch('/api/exercise/generate-bank', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: studentId.value, requirement: requirement.value, stream: true }),
    })

    if (!resp.ok || !resp.body) throw new Error('流式生成连接失败')

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const parts = buf.split('\n\n')
      buf = parts.pop() || ''
      for (const chunk of parts) consumeChunk(chunk)
    }
    buf += decoder.decode()
    if (buf.trim()) consumeChunk(buf)

    if (!generatedQuestionBankIds.length) {
      error.value = error.value || '生成流程没有返回可用题库，请重新生成。'
      return false
    }
    applyActiveQuestionBankConfig(questionBankResources.value.filter((bank) => generatedQuestionBankIds.includes(bank.id)))
    setActiveQuestionBankIds(generatedQuestionBankIds)
    return true
  } catch (e: any) {
    error.value = e?.message || '题库生成服务连接失败'
    return false
  } finally {
    generating.value = false
  }
}

function applyQuizConfig() {
  if (!requirement.value) return
  const typeCounts = Object.fromEntries(
    questionTypeOptions
      .map((option) => [option.value, normalizedTypeCount(option.value)])
      .filter(([, count]) => Number(count) > 0)
  )
  requirement.value = {
    ...(requirement.value || {}),
    question_config: {
      count: Math.max(1, Math.min(50, totalQuestionCount.value || 1)),
      difficulty: questionDifficulty.value,
      types: selectedQuestionTypes.value,
      type_counts: typeCounts,
    },
  }
}

function normalizedTypeCount(type: string) {
  return Math.max(0, Math.min(20, Number(questionTypeCounts.value[type]) || 0))
}

function goCustomize() {
  courseLocked.value = true
  doClarify()
  activePage.value = 'builder'
}

function resetCourseWorkflow() {
  courseLocked.value = false
  selectedMajorCategory.value = '工学'
  activePage.value = 'builder'
  pendingPage.value = null
  showExamLeaveDialog.value = false
  requirement.value = null
  events.value = []
  resources.value = []
  error.value = ''
  closedLoopStatus.value = '已重新开始专业课程选择，错题本数据已保留。'
  redoSession.value = null
  redoAnswer.value = ''
  redoResult.value = null
  selectedWrongRecordIds.value = []
  practiceStarted.value = false
  exerciseResetSeed.value += 1
  syncMajorCategory()
}

async function generateFromCustomize() {
  if (!currentPathStage.value || generating.value || totalQuestionCount.value <= 0) return
  generating.value = true
  error.value = ''
  closedLoopStatus.value = `正在为路径阶段“${pathStageTitle.value}”生成专属题库...`
  const typeCounts = Object.fromEntries(
    questionTypeOptions
      .map((option) => [option.value, normalizedTypeCount(option.value)])
      .filter(([, count]) => Number(count) > 0),
  )
  try {
    const data = await generatePathStageQuestions(studentId.value, {
      stageId: String(currentPathStage.value.id || ''),
      difficulty: questionDifficulty.value as 'mixed' | 'easy' | 'medium' | 'hard',
      count: Math.max(1, Math.min(50, totalQuestionCount.value)),
      questionTypes: selectedQuestionTypes.value,
      typeCounts,
    })
    const bank = data?.question_bank as ResourceItem | undefined
    if (!bank?.id) throw new Error('题库模型没有返回可用题库')
    resources.value = Array.isArray(data?.resources) ? data.resources : [bank]
    currentPathStage.value = data?.stage || currentPathStage.value
    setActiveQuestionBankIds([bank.id])
    activeExerciseQuestionLimit.value = Math.max(1, Math.min(50, Number(data?.stage?.target_count) || totalQuestionCount.value))
    activeExerciseDifficulty.value = questionDifficulty.value
    closedLoopStatus.value = `已载入“${pathStageTitle.value}”专属题库；每次提交都会更新阶段掌握度，达到 80% 后自动进入下一阶段。`
    activePage.value = 'diagnosis'
    practiceStarted.value = true
    exerciseResetSeed.value += 1
  } catch (reason: any) {
    error.value = reason?.message || '阶段题库生成失败'
    closedLoopStatus.value = '阶段题库尚未生成，请检查模型配置后重试。'
  } finally {
    generating.value = false
  }
}

async function refreshExerciseLoop() {
  closedLoopStatus.value = activeQuestionBankIds.value.length
    ? `已同步 ${activeQuestionBankIds.value.length} 份个性化题库，可在智能做题中开始练习。`
    : '当前阶段还没有题库，请先在题库定制中选择难度、数量和题型。'
  await nextTick()
}

function emptyWrongBookData() {
  return {
    groups: [],
    records: [],
    ability_radar: [],
    tag_summary: [],
    stats: { total: 0, correct: 0, wrong: 0, accuracy: 0, weak_tags: [], corrections: [] },
  }
}

function masteredGalaxyStorageKey() {
  return `workshop_mastered_galaxy_stars:${studentId.value}`
}

function loadMasteredGalaxyStars() {
  try {
    const raw = window.localStorage.getItem(masteredGalaxyStorageKey())
    const parsed = raw ? JSON.parse(raw) : []
    masteredGalaxyStars.value = Array.isArray(parsed) ? parsed.slice(0, 120) : []
  } catch {
    masteredGalaxyStars.value = []
  }
}

function saveMasteredGalaxyStars() {
  try {
    window.localStorage.setItem(masteredGalaxyStorageKey(), JSON.stringify(masteredGalaxyStars.value.slice(0, 120)))
  } catch {
  }
}

function recordMasteredGalaxyStar(record: any) {
  const tags = Array.isArray(record?.tags) ? record.tags.map((tag: any) => String(tag).trim()).filter(Boolean) : []
  const tag = tags[0] || String(record?.tag || record?.knowledge_point || '已掌握错题')
  const id = `${record?.id || record?.question_id || tag}-${Date.now()}`
  masteredGalaxyStars.value = [
    {
      id,
      tag,
      tags,
      major: record?.major || effectiveMajor.value,
      course: record?.course || effectiveCourse.value,
      point: record?.knowledge_point || record?.chapter || '错题重做正确',
      created_at: Date.now(),
      hue: 42 + (hashText(id) % 62),
    },
    ...masteredGalaxyStars.value,
  ].slice(0, 120)
  saveMasteredGalaxyStars()
  markNeedsRebuild()
}

function applyExerciseRadarImpact(payload: any) {
  const question = payload?.question || {}
  const text = `${question.type || ''} ${(question.tags || []).join(' ')} ${question.stem || ''}`
  const correct = Boolean(payload?.correct)
  const baseDelta = correct ? 0.9 : -1.15
  const next = { ...exerciseRadarImpact.value }
  const names = abilityRadar.value.map((item: any) => String(item.name))
  for (const name of names) {
    let weight = 0.34
    if (/基础|知识|概念/.test(name) && /概念|基础|判断|填空|定义/.test(text)) weight = 1
    if (/逻辑/.test(name) && /逻辑|推理|关系|选择|多选/.test(text)) weight = 1
    if (/运算|处理/.test(name) && /计算|公式|数值|运算/.test(text)) weight = 1
    if (/抽象|概括/.test(name) && /建模|抽象|UML|用例|结构|设计/.test(text)) weight = 1
    if (/应用|迁移/.test(name) && /案例|场景|应用|项目|业务/.test(text)) weight = 1
    if (/错因|复盘/.test(name)) weight = correct ? 0.8 : 1
    const current = Number(next[name] || 0)
    next[name] = Math.max(-18, Math.min(18, Number((current + baseDelta * weight).toFixed(2))))
  }
  exerciseRadarImpact.value = next
}

async function loadWrongBook() {
  wrongBookLoading.value = true
  wrongBookError.value = ''
  try {
    const resp = await fetch(`/api/exercise/wrong-book?student_id=${encodeURIComponent(studentId.value)}`)
    if (!resp.ok) throw new Error('错题本服务暂不可用')
    const payload = await resp.json()
    if (payload.success) {
      wrongBook.value = payload.data || emptyWrongBookData()
      // The persisted summary is authoritative after every answer; clear the
      // optimistic delta so the same answer is not counted twice.
      exerciseRadarImpact.value = {}
      const liveIds = new Set((wrongBook.value.records || []).map((record: any) => String(record.id)))
      selectedWrongRecordIds.value = selectedWrongRecordIds.value.filter((id) => liveIds.has(String(id)))
      await nextTick()
      if (courseFolders.value.length && !Object.values(openCourseFolders.value).some(Boolean)) {
        const first = courseFolders.value[0]
        openCourseFolders.value = { [first.key]: true }
      }
      return true
    } else {
      throw new Error(payload.error?.message || '错题本数据加载失败')
    }
  } catch (e: any) {
    if (!wrongBook.value) wrongBook.value = emptyWrongBookData()
    wrongBookError.value = e?.message || '错题本服务暂不可用'
    return false
  } finally {
    wrongBookLoading.value = false
  }
}

function switchDirect(page: WorkshopPageKey) {
  activePage.value = page
}

async function startPractice() {
  if (!exerciseContextReady.value || practiceStarted.value) return
  closedLoopStatus.value = '正在载入本轮练习题目...'
  practiceStarted.value = true
  await nextTick()
  exercisePageRef.value?.focusPracticeHeading()
}

function trySwitchPage(page: WorkshopPageKey) {
  if (page === activePage.value) {
    if (page === 'builder') {
      closedLoopStatus.value = '已定位到当前阶段题库定制区，可继续调整难度、数量和题型。'
    }
    return
  }
  hasUserSelectedExercisePage.value = true
  if (activePage.value === 'diagnosis' && page !== 'diagnosis' && exercisePageRef.value?.hasActiveExam?.()) {
    pendingPage.value = page
    showExamLeaveDialog.value = true
    return
  }
  switchDirect(page)
}

async function confirmSubmitExamAndLeave() {
  const target = pendingPage.value
  const submitted = await exercisePageRef.value?.finishExam?.()
  if (!submitted) return
  showExamLeaveDialog.value = false
  pendingPage.value = null
  if (target) switchDirect(target)
}

function cancelSubmitExamAndLeave() {
  showExamLeaveDialog.value = false
  pendingPage.value = null
}

function folderKey(major: string, course: string) {
  return `${major}::${course}`
}

function toggleCourseFolder(major: string, course: string) {
  const key = folderKey(major, course)
  openCourseFolders.value = {
    ...openCourseFolders.value,
    [key]: !openCourseFolders.value[key],
  }
}

function showAllCourseFolders() {
  openCourseFolders.value = Object.fromEntries(courseFolders.value.map((folder: any) => [folder.key, true]))
}

function hideAllCourseFolders() {
  openCourseFolders.value = {}
}

function toggleAllCourseFolders() {
  if (allCourseFoldersOpen.value) hideAllCourseFolders()
  else showAllCourseFolders()
}

function startRedoSession(scope: 'single' | 'course' | 'all', records: any[], title: string) {
  const seen = new Set<string>()
  const queue = records.filter((record) => {
    const key = recordKey(record)
    if (!record?.question_id || seen.has(key)) return false
    seen.add(key)
    return true
  })
  if (!queue.length) return
  redoSession.value = {
    scope,
    title,
    queue,
    index: 0,
    completed: false,
    correct: 0,
    wrong: 0,
  }
  redoAnswer.value = ''
  redoResult.value = null
}

function openRedo(record: any) {
  startRedoSession('single', [record], '重做本题')
}

function openRedoCourse(major: any, course: any) {
  startRedoSession('course', course.items || [], `${major.major} / ${course.course}`)
}

function openRedoAll() {
  const picked = selectedWrongRecords.value.length ? selectedWrongRecords.value : wrongBook.value?.records || []
  startRedoSession('all', picked, selectedWrongRecords.value.length ? '已选错题重做' : '全部错题重做')
}

function openTagGalaxy(tag = '') {
  activeGalaxyTag.value = tag
  trySwitchPage('tagGalaxy')
}

async function refreshTagGalaxy() {
  if (galaxyRefreshing.value) return
  galaxyRefreshing.value = true
  galaxyRefreshFeedback.value = ''
  if (galaxyRefreshFeedbackTimer !== null) {
    window.clearTimeout(galaxyRefreshFeedbackTimer)
    galaxyRefreshFeedbackTimer = null
  }

  const loaded = await loadWrongBook()
  if (loaded && activePage.value === 'tagGalaxy') {
    resetGalaxyScene({ version: true })
    await nextTick()
    await startTagGalaxy()
    galaxyRefreshFeedback.value = '已刷新'
  } else {
    galaxyRefreshFeedback.value = '刷新失败'
  }

  galaxyRefreshing.value = false
  galaxyRefreshFeedbackTimer = window.setTimeout(() => {
    galaxyRefreshFeedback.value = ''
    galaxyRefreshFeedbackTimer = null
  }, 1800)
}

// 星系渲染（THREE 场景/动画/交互）已拆到 @/composables/useTagGalaxyScene
const activeGalaxyNode = computed(() => {
  return tagGalaxy.value.nodes.find((node: any) => node.tag === activeGalaxyTag.value) || tagGalaxy.value.nodes[0] || null
})

function isMultipleQuestion(question: any) {
  const type = String(question?.type || '').toLowerCase()
  return type === 'multiple_choice' || type.includes('multiple') || type.includes('多选')
}

function answerKeys(value = redoAnswer.value) {
  return String(value || '').split(/[,，、\s]+/).map((item) => item.trim().toUpperCase()).filter(Boolean)
}

function isRedoOptionSelected(key: string) {
  return currentRedoIsMultiple.value ? answerKeys().includes(key) : redoAnswer.value === key
}

function onRedoOptionChange(key: string, event: Event) {
  if (currentRedoIsMultiple.value) {
    const checked = Boolean((event.target as HTMLInputElement | null)?.checked)
    const keys = new Set(answerKeys())
    if (checked) keys.add(key)
    else keys.delete(key)
    redoAnswer.value = Array.from(keys).sort().join(',')
    return
  }
  redoAnswer.value = key
}

function recordKey(record: any) {
  return String(record?.question_id || record?.stem || record?.id || '')
}

function toggleWrongRecordSelection(record: any, checked: boolean) {
  const id = String(record?.id || '')
  if (!id) return
  if (checked) {
    if (!selectedWrongRecordIds.value.includes(id)) selectedWrongRecordIds.value = [...selectedWrongRecordIds.value, id]
  } else {
    selectedWrongRecordIds.value = selectedWrongRecordIds.value.filter((item) => item !== id)
  }
}

function onWrongRecordSelection(record: any, event: Event) {
  toggleWrongRecordSelection(record, Boolean((event.target as HTMLInputElement | null)?.checked))
}

function toggleSelectCourseWrongRecords(course: any) {
  const ids = (course.items || []).map((item: any) => String(item.id)).filter(Boolean)
  const selected = new Set(selectedWrongRecordIds.value)
  const everySelected = ids.length && ids.every((id: string) => selected.has(id))
  selectedWrongRecordIds.value = everySelected
    ? selectedWrongRecordIds.value.filter((id) => !ids.includes(id))
    : Array.from(new Set([...selectedWrongRecordIds.value, ...ids]))
}

async function submitRedo() {
  if (!currentRedoRecord.value || !redoAnswer.value || redoSession.value?.completed) return
  const resp = await fetch('/api/exercise/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_id: studentId.value, question_id: currentRedoRecord.value.question_id, answer: redoAnswer.value }),
  })
  const payload = await resp.json()
  if (payload.success) {
    redoResult.value = payload.data
    onExerciseAnswered(payload.data)
    if (redoSession.value) {
      if (payload.data.correct) redoSession.value.correct += 1
      else redoSession.value.wrong += 1
    }
    if (payload.data.correct) {
      recordMasteredGalaxyStar(currentRedoRecord.value)
      await deleteWrongRecord(currentRedoRecord.value, false)
    } else {
      await loadWrongBook()
    }
  } else {
    wrongBookError.value = payload.error?.message || '重做判题失败'
  }
}

async function nextRedoQuestion() {
  if (!redoSession.value) return
  if (redoSession.value.index >= redoSession.value.queue.length - 1) {
    redoSession.value.completed = true
    await loadWrongBook()
    return
  }
  redoSession.value.index += 1
  redoAnswer.value = ''
  redoResult.value = null
}

function selectRedoQuestion(index: number) {
  if (!redoSession.value || index < 0 || index >= redoSession.value.queue.length) return
  redoSession.value.index = index
  redoAnswer.value = ''
  redoResult.value = null
}

async function finishRedoSession() {
  redoSession.value = null
  redoAnswer.value = ''
  redoResult.value = null
  await loadWrongBook()
}

async function deleteWrongRecord(record: any, reload = true) {
  const resp = await fetch(`/api/exercise/wrong-book/${encodeURIComponent(record.id)}?student_id=${encodeURIComponent(studentId.value)}`, {
    method: 'DELETE',
  })
  const payload = await resp.json()
  if (payload.success) {
    wrongBook.value = payload.data
    selectedWrongRecordIds.value = selectedWrongRecordIds.value.filter((id) => id !== String(record.id))
    if (reload) await loadWrongBook()
  } else {
    wrongBookError.value = payload.error?.message || '删除错题失败'
  }
}

async function deleteAllWrongRecords() {
  if (!wrongBookStats.value.totalWrong) return
  const resp = await fetch(`/api/exercise/wrong-book?student_id=${encodeURIComponent(studentId.value)}`, {
    method: 'DELETE',
  })
  const payload = await resp.json()
  if (payload.success) {
    wrongBook.value = payload.data || emptyWrongBookData()
    selectedWrongRecordIds.value = []
    await finishRedoSession()
  } else {
    wrongBookError.value = payload.error?.message || '一键删除错题失败'
  }
}

async function deleteSelectedWrongRecords() {
  const records = [...selectedWrongRecords.value]
  if (!records.length) return
  for (const record of records) {
    await deleteWrongRecord(record, false)
  }
  selectedWrongRecordIds.value = []
  await loadWrongBook()
}

function onExerciseAnswered(payload?: any) {
  applyExerciseRadarImpact(payload)
  void loadWrongBook()
  const progress = payload?.path_progress
  if (!progress || !currentPathStage.value) return
  currentPathStage.value = {
    ...currentPathStage.value,
    status: progress.status,
    mastery: progress.mastery,
    answered_count: progress.answered_count,
    correct_count: progress.correct_count,
    target_count: progress.target_count,
    accuracy: progress.accuracy,
  }
  closedLoopStatus.value = progress.message || `当前阶段掌握度已更新为 ${progress.mastery}% 。`
  if (progress.advanced) {
    window.setTimeout(async () => {
      await loadPathContext()
      setActiveQuestionBankIds([])
      resources.value = []
      activePage.value = 'builder'
      closedLoopStatus.value = progress.next_stage_id
        ? '上一阶段已达标，下一阶段已自动解锁。请定制新阶段题库后继续。'
        : '全部路径阶段已完成。'
    }, 1200)
  }
}

function normalizeOptions(options: string[]) {
  const seen = new Set<string>()
  return options
    .flatMap((option) => {
      const text = String(option || '').trim()
      const matches = [...text.matchAll(/(?<![A-Za-z])([A-Ha-h])(?:[.、．]?\s*)/g)]
      if (matches.length <= 1) return [text]
      return matches.map((match, index) => text.slice(match.index || 0, matches[index + 1]?.index ?? text.length).trim())
    })
    .filter(Boolean)
    .map((option) => {
      const match = option.match(/^([A-Ha-h])(?:[.、．]?\s*)?(.*)$/)
      return { text: (match?.[2] || option).trim(), raw: option }
    })
    .filter((option) => {
      const fingerprint = option.text.replace(/\s+/g, '').toLowerCase()
      if (!fingerprint || seen.has(fingerprint)) return false
      seen.add(fingerprint)
      return true
    })
    .map((option, index) => ({ ...option, key: String.fromCharCode(65 + index) }))
}

function radarPoint(index: number, score: number, radius = 84) {
  const count = Math.max(1, abilityRadar.value.length)
  const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count
  const distance = radius * Math.max(0, Math.min(100, score)) / 100
  return `${120 + Math.cos(angle) * distance},${120 + Math.sin(angle) * distance}`
}

function radarAxisPoint(index: number, radius = 92) {
  const count = Math.max(1, abilityRadar.value.length)
  const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count
  return { x: 120 + Math.cos(angle) * radius, y: 120 + Math.sin(angle) * radius }
}

function radarLabelPoint(index: number, radius = 112) {
  const count = Math.max(1, abilityRadar.value.length)
  const angle = -Math.PI / 2 + (Math.PI * 2 * index) / count
  return { x: 120 + Math.cos(angle) * radius, y: 120 + Math.sin(angle) * radius }
}

watch(activePage, async (page) => {
  if (page === 'wrongBook') await loadWrongBook()
  if (page === 'tagGalaxy') {
    await loadWrongBook()
    if (activePage.value !== 'tagGalaxy') return
    await nextTick()
    await startTagGalaxy()
  } else {
    stopTagGalaxy()
  }
})

watch(studentId, async () => {
  await loadPathContext()
  await restoreActiveQuestionBanks()
})

watch(() => [
  tagGalaxy.value.nodes.map((node: any) => `${node.tag}:${node.count}`).join('|'),
  tagGalaxy.value.links.map((link: any) => `${link.source}-${link.target}:${link.weight}`).join('|'),
].join('::'), () => {
  if (!activeGalaxyTag.value && tagGalaxy.value.nodes.length) activeGalaxyTag.value = tagGalaxy.value.nodes[0].tag
  if (activePage.value === 'tagGalaxy') void nextTick(startTagGalaxy)
})

watch(activeGalaxyTag, () => {
  if (activePage.value === 'tagGalaxy') {
    if (!refreshGalaxyFocusState()) {
  markNeedsRebuild()
      void nextTick(startTagGalaxy)
    }
  }
})

onMounted(async () => {
  prefersReducedMotion.value = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  loadMasteredGalaxyStars()
  void loadWrongBook()
  try {
    await loadPathContext()
    await restoreActiveQuestionBanks()
  } finally {
    exerciseContextReady.value = true
  }
  if (shouldAutoStartStageBank.value && currentPathStage.value && !activeQuestionBankIds.value.length) {
    await generateFromCustomize()
  }
})

onBeforeUnmount(() => {
  stopTagGalaxy()
  if (galaxyRefreshFeedbackTimer !== null) window.clearTimeout(galaxyRefreshFeedbackTimer)
  disposeTagGalaxyScene()
})
</script>

<template>
  <div class="studio-page workshop-shell workshop-shell-practice">
    <aside class="workshop-sidebar studio-panel">
      <div class="workshop-sidebar-head practice-workshop-head">
        <span class="practice-workshop-eyebrow">Practice Center</span>
        <strong class="practice-workshop-title">练习诊断中心</strong>
        <p>智能练习 · 精准诊断 · 个性提升</p>
      </div>
      <nav class="workshop-nav practice-workshop-nav" aria-label="练习诊断导航">
        <button type="button" :class="{ active: activePage === 'builder' }" :aria-current="activePage === 'builder' ? 'page' : undefined" @click="trySwitchPage('builder')">
          <span class="practice-workshop-icon">▤</span>
          <span class="practice-workshop-copy">
            <strong>题库定制</strong>
            <small>按路径阶段设置难度、数量与题型</small>
          </span>
        </button>
        <button type="button" :class="{ active: activePage === 'diagnosis' }" :aria-current="activePage === 'diagnosis' ? 'page' : undefined" @click="trySwitchPage('diagnosis')">
          <span class="practice-workshop-icon">✓</span>
          <span class="practice-workshop-copy">
            <strong>智能做题</strong>
            <small>训练、考试与即时诊断</small>
          </span>
        </button>
        <button type="button" :class="{ active: activePage === 'wrongBook' }" :aria-current="activePage === 'wrongBook' ? 'page' : undefined" @click="trySwitchPage('wrongBook')">
          <span class="practice-workshop-icon">▧</span>
          <span class="practice-workshop-copy">
            <strong>错题本</strong>
            <small>复盘、重做与错因沉淀</small>
          </span>
        </button>
        <button type="button" :class="{ active: activePage === 'tagGalaxy' }" :aria-current="activePage === 'tagGalaxy' ? 'page' : undefined" @click="trySwitchPage('tagGalaxy')">
          <span class="practice-workshop-icon">◎</span>
          <span class="practice-workshop-copy">
            <strong>知识点诊断</strong>
            <small>薄弱标签与能力分布</small>
          </span>
        </button>
      </nav>
      <div class="workshop-summary practice-learning-card">
        <span class="practice-learning-label">正在学习</span>
        <strong>{{ pathStageTitle }}</strong>
        <p>{{ pathCourseTitle }}</p>
        <div class="practice-learning-progress" aria-hidden="true">
          <i :style="{ width: activeQuestionBankIds.length ? `${Math.min(100, Math.max(14, activeExerciseQuestionLimit * 5))}%` : '0%' }"></i>
        </div>
        <div class="practice-learning-meta">
          <span>掌握度 {{ pathStageMastery }}%</span>
          <em>{{ activeQuestionBankIds.length ? pathStageProgressText : '暂无阶段题库' }}</em>
        </div>
        <button type="button" @click="trySwitchPage('builder')">调整阶段题库</button>
      </div>
    </aside>

    <main class="workshop-content">
      <section v-if="false" class="studio-panel" aria-hidden="true">
        <div class="studio-panel-header">
          <div>
            <div class="studio-title"><span class="studio-title-dot"></span>专业课程选择</div>
            <p>先选择专业大类、小类和课程目录；如果选择其它，课程类别和课程内容会同步进入自定义模式。</p>
          </div>
          <div class="studio-actions">
            <button class="studio-btn ghost" @click="resetCourseWorkflow">重新选择</button>
            <button class="studio-btn secondary" @click="goCustomize">进入出题定制</button>
          </div>
        </div>
        <div class="studio-panel-body">
          <div v-if="courseLocked" class="studio-empty mb-3">专业课程已确定，后续题库、训练和错题归档都会沿用该选择。</div>
          <div class="studio-grid studio-grid-balanced">
            <label class="grid gap-2">
              <span class="text-sm font-black text-slate-700">专业大类</span>
              <select v-model="selectedMajorCategory" class="studio-select" :disabled="courseLocked" @change="syncMajorCategory">
                <option v-for="item in majorCatalog" :key="item.category" :value="item.category">{{ item.category }}</option>
              </select>
            </label>
            <label class="grid gap-2">
              <span class="text-sm font-black text-slate-700">专业小类</span>
              <select v-model="selectedMajor" class="studio-select" :disabled="courseLocked" @change="syncMajor">
                <option v-for="major in majorOptions" :key="major" :value="major">{{ major }}</option>
              </select>
            </label>
          </div>
          <input v-if="selectedMajor === '其它'" v-model="customMajor" class="studio-input mt-3" :disabled="courseLocked" placeholder="请输入专业名称" @input="syncCustomizationDefaults" />

          <div class="studio-grid studio-grid-balanced mt-4">
            <label class="grid gap-2">
              <span class="text-sm font-black text-slate-700">课程大类</span>
              <select v-model="selectedCourseCategory" class="studio-select" :disabled="courseLocked" @change="syncCourse">
                <option v-for="item in courseCatalog" :key="item.category" :value="item.category">{{ item.category }}</option>
              </select>
            </label>
            <label class="grid gap-2">
              <span class="text-sm font-black text-slate-700">课程内容</span>
              <select v-model="selectedCourse" class="studio-select" :disabled="courseLocked" @change="syncCustomizationDefaults">
                <option v-for="course in courseOptions" :key="course" :value="course">{{ course }}</option>
              </select>
            </label>
          </div>
          <div v-if="selectedCourseCategory === '其它' || selectedCourse === '其它'" class="studio-grid studio-grid-balanced mt-3">
            <input v-if="selectedCourseCategory === '其它'" v-model="customCourseCategory" class="studio-input" :disabled="courseLocked" placeholder="请输入课程类别" @input="syncCustomizationDefaults" />
            <input v-if="selectedCourse === '其它'" v-model="customCourse" class="studio-input" :disabled="courseLocked" placeholder="请输入课程内容" @input="syncCustomizationDefaults" />
          </div>

          <section class="practice-config-summary" aria-label="当前训练配置">
            <div class="practice-config-summary__head">
              <div>
                <span>当前训练配置</span>
                <strong>课程选择将直接约束定制题库</strong>
              </div>
              <button class="studio-btn secondary" type="button" @click="goCustomize">继续定制</button>
            </div>
            <div class="practice-config-summary__grid">
              <article>
                <span>专业方向</span>
                <strong>{{ effectiveMajor }}</strong>
                <small>{{ selectedMajorCategory }}</small>
              </article>
              <article>
                <span>当前课程</span>
                <strong>{{ effectiveCourse }}</strong>
                <small>{{ effectiveCourseCategory }}</small>
              </article>
              <article>
                <span>诊断焦点</span>
                <strong>{{ specificKnowledgePoint || '待设置知识点' }}</strong>
                <small>进入出题定制后可修改</small>
              </article>
              <article>
                <span>题库规格</span>
                <strong>{{ totalQuestionCount }} 题 · {{ questionDifficultyLabel }}</strong>
                <small>{{ selectedQuestionTypes.length }} 种题型已启用</small>
              </article>
            </div>
          </section>

          <div class="stage-steps mt-4">
            <div class="stage-step">
              <div class="stage-step-num">1</div>
              <div>
                <strong>专业课程定位</strong>
                <p>当前选择会作为题库生成的学科上下文，影响知识点范围、案例背景和难度表达。</p>
              </div>
              <button class="studio-btn secondary" @click="goCustomize">下一步</button>
            </div>
            <div class="stage-step">
              <div class="stage-step-num">2</div>
              <div>
                <strong>错题与诊断联动</strong>
                <p>也可以直接进入错题本，从历史错误反推薄弱点，再回到出题定制生成针对性题库。</p>
              </div>
              <button class="studio-btn ghost" @click="trySwitchPage('wrongBook')">查看错题本</button>
            </div>
          </div>
        </div>
      </section>

      <section v-show="activePage === 'builder'" class="studio-panel">
        <div class="studio-panel-header">
          <div>
            <div class="studio-title"><span class="studio-title-dot green"></span>路径题库定制</div>
            <p>题目只来自当前学习节点；你可以定制难度、数量和题型，完成后系统自动更新掌握度并判定是否晋级。</p>
          </div>
          <div class="studio-actions">
            <button class="studio-btn" :disabled="generating || totalQuestionCount <= 0 || !currentPathStage" @click="generateFromCustomize">
              {{ generating ? '题库生成中' : '生成阶段题库并开始' }}
            </button>
          </div>
        </div>
        <div class="studio-panel-body">
          <div class="grid gap-3">
            <section v-if="currentPathStage" class="practice-config-summary" aria-label="当前路径阶段">
              <div class="practice-config-summary__head">
                <div>
                  <span>当前路径阶段</span>
                  <strong>{{ pathStageTitle }}</strong>
                </div>
                <span class="cp-status">{{ currentPathStage.status === 'warning' ? '需补强' : '正在学习' }}</span>
              </div>
              <div class="practice-config-summary__grid">
                <article><span>所属路径</span><strong>{{ pathCourseTitle }}</strong><small>题目不会跨出该节点</small></article>
                <article><span>阶段目标</span><strong>{{ pathStageGoal }}</strong><small>{{ currentPathStage.checkpoint || '完成测试形成学习证据' }}</small></article>
                <article><span>当前掌握度</span><strong>{{ pathStageMastery }}%</strong><small>每次提交后实时更新</small></article>
                <article><span>自动晋级</span><strong>掌握度 ≥ 80%</strong><small>完成本轮全部题目后判定</small></article>
              </div>
            </section>
            <div v-else class="studio-empty">{{ pathContextLoading ? '正在读取当前路径阶段…' : '没有可用路径阶段，请先前往路径推送生成学习路径。' }}</div>
            <div class="studio-grid studio-grid-balanced">
              <label class="grid gap-2">
                <span class="text-sm font-black text-slate-700">题目总数</span>
                <input class="studio-input" type="number" :value="totalQuestionCount" readonly />
              </label>
              <label class="grid gap-2">
                <span class="text-sm font-black text-slate-700">题目难度</span>
                <select v-model="questionDifficulty" class="studio-select" @change="applyQuizConfig">
                  <option value="mixed">由易到难混合</option>
                  <option value="easy">基础巩固</option>
                  <option value="medium">中等应用</option>
                  <option value="hard">综合提升</option>
                </select>
              </label>
            </div>
            <div class="grid gap-2">
              <span class="text-sm font-black text-slate-700">题型数量</span>
              <div class="question-type-grid">
                <label v-for="type in questionTypeOptions" :key="type.value" class="question-type-card">
                  <span>
                    <strong>{{ type.label }}</strong>
                    <em>{{ type.hint }}</em>
                  </span>
                  <input
                    v-model.number="questionTypeCounts[type.value]"
                    type="number"
                    min="0"
                    max="20"
                    @change="applyQuizConfig"
                  />
                </label>
              </div>
            </div>
            <p class="studio-muted">当前身份：{{ studentId }}。题库只使用“{{ pathStageTitle }}”的目标与验收标准作为出题上下文。</p>
            <div class="studio-actions">
              <button class="studio-btn" :disabled="generating || totalQuestionCount <= 0 || !currentPathStage" @click="generateFromCustomize">
                {{ generating ? '题库生成中' : '生成阶段题库并开始学习' }}
              </button>
              <button class="studio-btn ghost" @click="trySwitchPage('wrongBook')">从错题本调整</button>
            </div>
            <div v-if="error" class="text-sm font-bold text-orange-600">{{ error }}</div>
          </div>
        </div>
      </section>

      <section
        v-show="activePage === 'wrongBook'"
        class="studio-panel"
        :class="{ 'wrongbook-panel-empty': !wrongBookStats.totalWrong && !redoSession }"
      >
        <div class="studio-panel-header">
          <div>
            <div class="studio-title"><span class="studio-title-dot green"></span>错题本</div>
            <p>按专业和课程整理错题文件夹，错题标签会进入能力雷达；每次训练和重做都会动态更新。</p>
          </div>
          <div v-if="!redoSession" class="studio-actions">
            <span v-if="selectedWrongRecordIds.length" class="wrongbook-selection-pill">已选 {{ selectedWrongRecordIds.length }} 题</span>
            <button v-if="wrongBookStats.totalWrong" class="studio-btn secondary" @click="openRedoAll">{{ redoAllButtonText }}</button>
            <button v-if="wrongBookStats.totalWrong" class="studio-btn danger" :disabled="!selectedWrongRecordIds.length" @click="deleteSelectedWrongRecords">批量删除</button>
            <button v-if="wrongBookStats.totalWrong" class="studio-btn danger" @click="deleteAllWrongRecords">一键删除错题</button>
            <button class="studio-btn ghost" :disabled="wrongBookLoading" @click="loadWrongBook">{{ wrongBookLoading ? '刷新中' : '刷新错题本' }}</button>
          </div>
        </div>
        <div class="studio-panel-body">
          <section v-if="redoSession" class="wrongbook-redo-workbench">
            <aside v-if="redoSession.queue.length" class="wrongbook-hover-directory" aria-label="重做错题目录">
              <span class="wrongbook-hover-tab">目录</span>
              <div class="wrongbook-hover-panel">
                <strong>重做目录</strong>
                <button
                  v-for="(item, idx) in redoSession.queue"
                  :key="`redo-nav-${item.id || item.question_id || idx}`"
                  type="button"
                  :class="{ active: idx === redoSession.index }"
                  @click="selectRedoQuestion(idx)"
                >
                  <span>{{ idx + 1 }}. {{ item.stem }}</span>
                  <em>{{ item.type || '题目' }}</em>
                </button>
              </div>
            </aside>
            <div class="wrongbook-redo-head">
              <div>
                <div class="studio-title"><span class="studio-title-dot"></span>错题重做训练</div>
                <p>{{ redoSession.title }} · {{ redoSession.index + 1 }} / {{ redoSession.queue.length }}</p>
              </div>
              <div class="studio-actions">
                <button class="studio-btn ghost" @click="finishRedoSession">结束重做</button>
              </div>
            </div>

            <div v-if="redoSession.completed" class="wrongbook-redo-summary">
              <strong>本轮错题重做完成</strong>
              <span>答对 {{ redoSession.correct }} 题，仍需复盘 {{ redoSession.wrong }} 题。</span>
              <button class="studio-btn" @click="finishRedoSession">回到错题本</button>
            </div>

            <template v-else>
              <article class="exercise-question mt-3">
                <strong>{{ currentRedoRecord?.stem }}</strong>
                <div class="exercise-tags">
                  <span v-for="tag in currentRedoRecord?.tags || []" :key="tag">{{ tag }}</span>
                </div>
                <p class="studio-muted mt-3">原答案：{{ currentRedoRecord?.answer || '未记录' }}；正确答案：{{ currentRedoRecord?.correct_answer || '待核验' }}</p>
              </article>
              <div v-if="redoOptions.length" class="exercise-options mt-3">
                <label v-for="option in redoOptions" :key="option.key" :class="{ selected: isRedoOptionSelected(option.key) }">
                  <input
                    :type="currentRedoIsMultiple ? 'checkbox' : 'radio'"
                    :name="currentRedoRecord?.id || currentRedoRecord?.question_id"
                    :value="option.key"
                    :checked="isRedoOptionSelected(option.key)"
                    @change="onRedoOptionChange(option.key, $event)"
                  />
                  <span class="exercise-option-key">{{ option.key }}</span>
                  <span class="exercise-option-text">{{ option.text }}</span>
                </label>
              </div>
              <input v-else v-model="redoAnswer" class="exercise-answer-input mt-3" placeholder="输入重做答案" />
              <div class="studio-actions mt-3">
                <button class="studio-btn" :disabled="!redoAnswer || !!redoResult" @click="submitRedo">提交重做</button>
                <button v-if="redoResult" class="studio-btn secondary" @click="nextRedoQuestion">
                  {{ redoSession.index >= redoSession.queue.length - 1 ? '完成本轮' : '下一题' }}
                </button>
              </div>
              <div v-if="redoResult" class="exercise-result mt-3" :class="redoResult.correct ? 'is-correct' : 'is-wrong'">
                <strong>{{ redoResult.correct ? '重做正确，已从错题本移除' : '重做仍需复盘' }}</strong>
                <span>正确答案：{{ redoResult.correct_answer || '待核验' }}</span>
                <p v-if="redoResult.analysis">{{ redoResult.analysis }}</p>
              </div>
            </template>
          </section>

          <template v-else-if="wrongBookStats.totalWrong">
          <div class="wrongbook-stats">
            <div>
              <strong>{{ wrongBookStats.totalWrong }}</strong>
              <span>仍需复盘错题</span>
            </div>
            <div>
              <strong>{{ wrongBookStats.courseCount }}</strong>
              <span>涉及课程文件夹</span>
            </div>
            <div>
              <strong>{{ masteredGalaxyStars.length }}</strong>
              <span>历史星</span>
            </div>
          </div>
          <section class="wrongbook-history-entry">
            <div>
              <strong>历史星系</strong>
              <span>重做正确的错题会沉淀为高亮历史星，训练诊断会同步影响能力雷达。</span>
            </div>
            <button class="studio-btn secondary" type="button" @click="openTagGalaxy()">进入历史星系</button>
          </section>
          <section class="wrongbook-folder-directory">
            <div class="wrongbook-directory-head">
              <strong>课程文件夹</strong>
              <div class="studio-actions">
                <button class="studio-btn ghost" @click="toggleAllCourseFolders">{{ allCourseFoldersOpen ? '收起全部' : '展开全部' }}</button>
              </div>
            </div>
            <div v-if="!courseFolders.length" class="studio-empty">暂无课程文件夹。</div>
            <button
              v-for="folder in courseFolders"
              :key="folder.key"
              type="button"
              :class="{ active: openCourseFolders[folder.key] }"
              @click="toggleCourseFolder(folder.major, folder.course)"
            >
              <span>{{ folder.major }} / {{ folder.course }}</span>
              <strong>{{ folder.count }} 题</strong>
            </button>
          </section>
          <div class="wrongbook-layout">
            <section class="wrongbook-radar">
              <div class="studio-title"><span class="studio-title-dot green"></span>能力雷达图</div>
              <svg :key="radarSignature" class="ability-radar-svg" viewBox="0 0 240 240" role="img" aria-label="能力雷达图">
                <polygon points="120,36 192.7,78 192.7,162 120,204 47.3,162 47.3,78" class="radar-grid" />
                <polygon points="120,64 168.5,92 168.5,148 120,176 71.5,148 71.5,92" class="radar-grid inner" />
                <line v-for="(_, idx) in abilityRadar" :key="idx" x1="120" y1="120" :x2="radarAxisPoint(idx).x" :y2="radarAxisPoint(idx).y" class="radar-axis" />
                <polygon :points="radarOldPoints" class="radar-area-old" />
                <polygon :points="radarPoints" class="radar-area" />
                <circle v-for="(item, idx) in abilityRadar" :key="item.name" :cx="radarPoint(idx, item.score).split(',')[0]" :cy="radarPoint(idx, item.score).split(',')[1]" r="3.5" class="radar-dot" />
                <text
                  v-for="(item, idx) in abilityRadar"
                  :key="`percent-${item.name}`"
                  :x="radarPoint(idx, item.score, 96).split(',')[0]"
                  :y="radarPoint(idx, item.score, 96).split(',')[1]"
                  class="radar-percent-label"
                  text-anchor="middle"
                >
                  {{ Math.round(item.score) }}%
                </text>
                <text
                  v-for="(item, idx) in abilityRadar"
                  :key="`label-${item.name}`"
                  :x="radarLabelPoint(idx).x"
                  :y="radarLabelPoint(idx).y"
                  class="radar-label"
                  text-anchor="middle"
                >
                  {{ item.name.replace('能力', '') }}
                </text>
              </svg>
              <div class="radar-legend">
                <span><i class="old"></i>旧</span>
                <span><i></i>新</span>
              </div>
              <div class="ability-list">
                <p v-for="item in abilityRadar" :key="item.name">
                  <span>{{ item.name }}</span>
                  <strong>{{ Math.round(item.old_score ?? 50) }}% → {{ Math.round(item.score) }}%</strong>
                </p>
              </div>
            </section>

            <section class="wrongbook-folders">
              <div v-if="wrongBookError" class="text-sm font-bold text-orange-600">{{ wrongBookError }}</div>
              <div v-if="!wrongBook?.groups?.length" class="studio-empty">暂无错题。完成练习训练后，错题会按专业和课程自动归档。</div>
              <div v-for="major in wrongBook?.groups || []" :key="major.major" class="wrongbook-major">
                <div class="wrongbook-folder-head">
                  <strong>{{ major.major }}</strong>
                  <span>{{ major.count }} 道错题</span>
                </div>
                <div
                  v-for="course in major.courses"
                  v-show="openCourseFolders[folderKey(major.major, course.course)]"
                  :key="course.course"
                  class="wrongbook-course"
                >
                  <div class="wrongbook-course-head">
                    <strong>{{ course.course }}</strong>
                    <span>{{ course.count }} 题</span>
                    <button class="studio-btn ghost" @click="toggleSelectCourseWrongRecords(course)">选择本课程</button>
                    <button class="studio-btn ghost" @click="openRedoCourse(major, course)">重做本课程</button>
                  </div>
                  <article v-for="item in course.items" :key="item.id" class="wrongbook-item">
                    <label class="wrongbook-check">
                      <input
                        type="checkbox"
                        :checked="selectedWrongRecordIds.includes(String(item.id))"
                        @change="onWrongRecordSelection(item, $event)"
                      />
                    </label>
                    <div class="wrongbook-item-main">
                      <div class="tag-row">
                        <span>{{ item.type }}</span>
                        <span v-for="tag in item.tags || []" :key="tag">{{ tag }}</span>
                      </div>
                      <strong>{{ item.stem }}</strong>
                      <p>你的答案：{{ item.answer || '未记录' }}；正确答案：{{ item.correct_answer || '待核验' }}</p>
                      <p v-if="item.analysis">{{ item.analysis }}</p>
                    </div>
                    <div class="wrongbook-item-actions">
                      <button class="studio-btn secondary" @click="openRedo(item)">重做</button>
                      <button class="studio-btn danger" @click="deleteWrongRecord(item)">删除</button>
                    </div>
                  </article>
                </div>
              </div>
            </section>
          </div>
          </template>
          <section v-else class="wrongbook-empty-state" aria-label="错题本为空">
            <div class="wrongbook-empty-state__intro">
              <span class="wrongbook-empty-state__mark">✓</span>
              <div>
                <span>当前无待复盘错题</span>
                <strong>完成一轮定制练习后，错题和能力变化会自动沉淀到这里</strong>
                <p>能力雷达只基于真实作答结果更新，空错题本不会填充模拟分数。</p>
              </div>
            </div>
            <div class="wrongbook-empty-flow">
              <section class="wrongbook-empty-zone">
                <header><span>当前诊断配置</span><strong>本轮练习将使用的真实输入</strong></header>
                <dl>
                  <div><dt>专业方向</dt><dd>{{ effectiveMajor }}</dd></div>
                  <div><dt>当前课程</dt><dd>{{ effectiveCourse }}</dd></div>
                  <div><dt>诊断焦点</dt><dd>{{ specificKnowledgePoint || '待设置知识点' }}</dd></div>
                  <div><dt>题库规格</dt><dd>{{ totalQuestionCount }} 题 · {{ questionDifficultyLabel }}</dd></div>
                  <div><dt>已绑定题库</dt><dd>{{ activeQuestionBankIds.length }} 份</dd></div>
                </dl>
              </section>
              <section class="wrongbook-empty-zone">
                <header><span>真实复盘机制</span><strong>错题从作答到能力变化的处理路径</strong></header>
                <ol>
                  <li><b>1</b><span><strong>提交真实答案</strong><small>训练模式即时判题，考试模式交卷后统一判题</small></span></li>
                  <li><b>2</b><span><strong>保留错因证据</strong><small>记录用户答案、正确答案、解析和知识点标签</small></span></li>
                  <li><b>3</b><span><strong>归档到课程文件夹</strong><small>按专业和课程归类，支持单题、课程和全部重做</small></span></li>
                  <li><b>4</b><span><strong>重做结果继续沉淀</strong><small>答对后移出待复盘区，同步到历史星系</small></span></li>
                </ol>
              </section>
              <section class="wrongbook-empty-evidence">
                <header><span>完成练习后这里会出现的真实证据</span><strong>页面不会在作答前生成虚假分数</strong></header>
                <div>
                  <article><b>错题文件夹</b><span>按专业、课程和知识点组织待复盘题目。</span></article>
                  <article><b>能力雷达</b><span>根据实际正误与重做结果更新六维能力。</span></article>
                  <article><b>历史星系</b><span>重做正确的题目转为已掌握历史证据。</span></article>
                </div>
              </section>
              <section class="wrongbook-empty-rules">
                <header><span>开始前准备</span><strong>当前最短可执行路径</strong></header>
                <ol>
                  <li><b>01</b><span><strong>确认知识点</strong><small>{{ specificKnowledgePoint || '在出题定制页设置具体诊断范围' }}</small></span></li>
                  <li><b>02</b><span><strong>生成独立题库</strong><small>练习诊断不会读取资源工坊的资源组合</small></span></li>
                  <li><b>03</b><span><strong>完成智能做题</strong><small>作答后回到本页查看错题、雷达和历史变化</small></span></li>
                </ol>
              </section>
            </div>
            <div class="studio-actions wrongbook-empty-state__actions">
              <button class="studio-btn secondary" type="button" @click="trySwitchPage('builder')">设置定制题库</button>
              <button class="studio-btn" type="button" @click="trySwitchPage('diagnosis')">进入智能做题</button>
              <button v-if="masteredGalaxyStars.length" class="studio-btn ghost" type="button" @click="openTagGalaxy()">查看 {{ masteredGalaxyStars.length }} 颗历史星</button>
            </div>
          </section>
        </div>
      </section>

      <section v-show="activePage === 'tagGalaxy'" class="studio-panel tag-galaxy-panel">
        <div class="studio-panel-header">
          <div>
            <div class="studio-title"><span class="studio-title-dot green"></span>错题标签星系</div>
            <p>标签按专业、课程和知识点聚合成星系节点，连线表示错题标签之间的关联强度。</p>
          </div>
          <div class="studio-actions">
            <button class="studio-btn ghost" @click="trySwitchPage('wrongBook')">返回错题本</button>
            <button class="studio-btn secondary" :disabled="galaxyRefreshing || wrongBookLoading" @click="refreshTagGalaxy">{{ galaxyRefreshing ? '刷新中' : (galaxyRefreshFeedback || '刷新星系') }}</button>
          </div>
        </div>
        <div class="tag-galaxy-body">
          <div class="tag-galaxy-stage">
            <p id="tag-galaxy-keyboard-help" class="sr-only">错题星系。聚焦后使用加号和减号缩放，0 恢复 100%，方向键选择标签，Enter 或空格确认，Escape 清除焦点。</p>
            <canvas
              ref="galaxyCanvas"
              tabindex="0"
              role="application"
              aria-label="错题标签星系"
              aria-describedby="tag-galaxy-keyboard-help"
              @click="onGalaxyClick"
              @keydown="onGalaxyKeydown"
              @mousemove="onGalaxyPointerMove"
              @mouseleave="onGalaxyPointerLeave"
              @wheel.prevent="onGalaxyWheel"
            ></canvas>
          </div>
          <aside class="tag-galaxy-inspector">
            <div>
              <span>当前标签</span>
              <strong>{{ activeGalaxyNode?.tag || '暂无标签' }}</strong>
            </div>
            <p v-if="activeGalaxyNode">{{ activeGalaxyNode.major }} / {{ activeGalaxyNode.course }}</p>
            <p v-if="activeGalaxyNode">涉及 {{ activeGalaxyNode.count }} 道错题，知识点：{{ activeGalaxyNode.points?.slice(0, 3).join('、') || '综合知识点' }}</p>
            <p>移动鼠标会改变星系大小、倾斜和视差；滚轮缩放：{{ Math.round(galaxyZoom * 100) }}%。点击任意标签后，相关标签会围绕它形成动态星系。</p>
            <div class="tag-galaxy-clusters">
              <button
                v-for="node in tagGalaxy.nodes"
                :key="node.tag"
                type="button"
                :class="{ active: activeGalaxyTag === node.tag }"
                @click="activeGalaxyTag = node.tag"
              >
                <span>{{ node.tag }}</span>
              </button>
            </div>
          </aside>
        </div>
      </section>

      <section v-show="activePage === 'diagnosis'">
        <div class="studio-panel mb-4 diagnosis-hero-panel">
        <div class="studio-panel-header">
          <div>
            <div class="studio-title"><span class="studio-title-dot green"></span>{{ pathStageTitle }} · 智能做题</div>
            <p>本轮题目全部来自当前路径节点；每次提交都会回写阶段掌握度，完成全部题目后自动判定是否解锁下一阶段。</p>
          </div>
        </div>
        <div class="studio-panel-body">
          <div class="diagnosis-overview-strip">
            <article>
              <span>题库来源</span>
              <strong>{{ questionBankResources.length ? `${questionBankResources.length} 份个性化题库` : '尚未生成题库' }}</strong>
            </article>
            <article>
              <span>{{ activeQuestionBankIds.length ? '计划题量' : '题库状态' }}</span>
              <strong>{{ activeQuestionBankIds.length ? `${activeExerciseQuestionLimit} 题` : '题库就绪后确定' }}</strong>
            </article>
            <article>
              <span>诊断去向</span>
              <strong>掌握度 · 自动晋级 · 错题本</strong>
            </article>
          </div>
          <div class="tag-row">
            <span>需求定制</span>
            <span>资源生成</span>
            <span>题库出题</span>
            <span>训练诊断</span>
            <span>画像迭代</span>
          </div>
          <p class="studio-muted mt-3">{{ closedLoopStatus }}</p>
        </div>
      </div>
      <div v-if="!practiceStarted" class="practice-start-panel studio-panel" data-testid="practice-start-panel">
        <div class="practice-start-copy">
          <span class="practice-start-eyebrow">本轮练习 · 开始前确认</span>
          <h2>准备好开始做题了吗？</h2>
          <p>点击“开始做题”后才会载入题目。进入后可选择即时训练或考试模式，作答会记录到学习诊断中。</p>
        </div>
        <div class="practice-start-details" aria-label="本轮练习信息">
          <article><span>学习阶段</span><strong>{{ pathStageTitle }}</strong></article>
          <article>
            <span>{{ activeQuestionBankIds.length ? '计划题量' : '题库状态' }}</span>
            <strong>{{ activeQuestionBankIds.length ? `${activeExerciseQuestionLimit} 题` : '尚未生成题库' }}</strong>
          </article>
          <article><span>题目来源</span><strong>{{ activeQuestionBankIds.length ? `${activeQuestionBankIds.length} 份已选题库` : '开始后检查当前可用题目' }}</strong></article>
        </div>
        <div class="practice-start-actions">
          <button class="studio-btn" type="button" :disabled="!exerciseContextReady" @click="startPractice">{{ exerciseContextReady ? '开始做题' : '正在准备练习…' }}</button>
          <button class="studio-btn ghost" type="button" @click="trySwitchPage('builder')">调整题库</button>
        </div>
        <p v-if="!exerciseContextReady" class="practice-start-note" role="status">正在读取当前学习阶段和题库状态。</p>
        <p v-if="!activeQuestionBankIds.length" class="practice-start-note" role="note">
          当前没有已选的个性化题库。开始后会检查本地可用题目；如果没有题目，页面会提示先去题库定制。
        </p>
      </div>
      <ExercisePage
        v-else
        ref="exercisePageRef"
        :active="activePage === 'diagnosis'"
        :question-bank-ids="activeQuestionBankIds"
        :question-limit="activeExerciseQuestionLimit"
        :difficulty="activeExerciseDifficulty"
        :course-name="pathCourseTitle"
        :knowledge-point="pathStageTitle"
        :question-type-count="selectedQuestionTypes.length"
        :reset-seed="exerciseResetSeed"
        @answered="onExerciseAnswered"
        @navigate="trySwitchPage($event)"
      />
      </section>
    </main>

    <div v-if="showExamLeaveDialog" class="workshop-modal-backdrop">
      <section class="workshop-modal studio-panel">
        <div class="studio-title"><span class="studio-title-dot green"></span>考试正在进行</div>
        <p>切换到其它页面前需要先交卷。交卷后会保留本次作答记录，并生成训练诊断和错题沉淀。</p>
        <div class="studio-actions">
          <button class="studio-btn ghost" @click="cancelSubmitExamAndLeave">继续考试</button>
          <button class="studio-btn" @click="confirmSubmitExamAndLeave">交卷并离开</button>
        </div>
      </section>
    </div>
  </div>
</template>
