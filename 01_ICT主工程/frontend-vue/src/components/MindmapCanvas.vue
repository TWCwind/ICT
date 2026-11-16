<script setup lang="ts">
import { computed, ref, watch } from 'vue'

/**
 * 把 Mermaid mindmap 缩进文本渲染成真正的思维导图（纯 SVG，不依赖第三方图表库）。
 * - 根节点居中，一级分支按叶子数量自动均分到左右两侧
 * - 节点可点击折叠/展开，支持滚轮缩放、拖拽平移
 */

interface MindNode {
  id: string
  text: string
  children: MindNode[]
  parent: MindNode | null
}

interface PlacedNode {
  id: string
  text: string
  depth: number
  dir: 1 | -1
  x: number
  y: number
  w: number
  h: number
  hasChildren: boolean
  collapsed: boolean
}

const props = defineProps<{ source: string }>()

const ROW = 42
const GAP_ROOT = 60
const GAP_LEVEL = 42
const MIN_W = 64
const MAX_W = 210
const FONT = 13
const HEIGHT = 32

const collapsed = ref(new Set<string>())
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })
const dragging = ref<null | { x: number; y: number; ox: number; oy: number }>(null)
const hovered = ref('')

watch(
  () => props.source,
  () => {
    scale.value = 1
    offset.value = { x: 0, y: 0 }
    // 默认把第三层折叠起来，先呈现主干结构，避免一上来就是几十个叶子挤成一列
    const defaults = new Set<string>()
    const walk = (node: MindNode, depth: number) => {
      if (depth >= 2 && node.children.length) defaults.add(node.id)
      node.children.forEach((child) => walk(child, depth + 1))
    }
    const root = parseMindmap(props.source)
    if (root) walk(root, 0)
    collapsed.value = defaults
  },
  { immediate: true },
)

function cleanText(raw: string): string {
  let text = raw.trim()
  text = text.replace(/\s*::icon\([^)]*\)\s*$/i, '')
  text = text.replace(/^[A-Za-z0-9_-]+\s*(?=[(\[{])/, '')
  const wrappers: [RegExp, string][] = [
    [/^\(\((.*)\)\)$/s, '$1'],
    [/^\(\[(.*)\]\)$/s, '$1'],
    [/^\[\((.*)\)\]$/s, '$1'],
    [/^\[(.*)\]$/s, '$1'],
    [/^\{\{(.*)\}\}$/s, '$1'],
    [/^\((.*)\)$/s, '$1'],
    [/^\>(.*)\]$/s, '$1'],
  ]
  for (const [pattern, replacement] of wrappers) {
    if (pattern.test(text)) {
      text = text.replace(pattern, replacement)
      break
    }
  }
  return text.replace(/["'`]/g, '').trim()
}

function parseMindmap(source: string): MindNode | null {
  const lines = (source || '').replace(/\r/g, '').replace(/\t/g, '  ').split('\n')
  const raw: { indent: number; text: string }[] = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    if (/^mindmap$/i.test(trimmed)) continue
    if (trimmed.startsWith('%%')) continue
    if (/^(classDef|class|style|linkStyle)\b/.test(trimmed)) continue
    const indent = line.length - line.replace(/^ +/, '').length
    const text = cleanText(trimmed)
    if (!text) continue
    raw.push({ indent, text })
  }
  if (!raw.length) return null

  const indents = [...new Set(raw.map((item) => item.indent))].sort((a, b) => a - b)
  const rank = new Map<number, number>()
  indents.forEach((value, index) => rank.set(value, index))

  let root: MindNode | null = null
  const stack: { level: number; node: MindNode }[] = []
  let seq = 0
  for (const item of raw) {
    const level = rank.get(item.indent) ?? 0
    const node: MindNode = { id: `n${seq++}`, text: item.text, children: [], parent: null }
    while (stack.length && stack[stack.length - 1].level >= level) stack.pop()
    if (stack.length) {
      const parent = stack[stack.length - 1].node
      node.parent = parent
      parent.children.push(node)
    } else if (!root) {
      root = node
    } else {
      node.parent = root
      root.children.push(node)
    }
    stack.push({ level, node })
  }
  return root
}

function visibleChildren(node: MindNode): MindNode[] {
  return collapsed.value.has(node.id) ? [] : node.children
}

function leafCount(node: MindNode): number {
  const kids = visibleChildren(node)
  if (!kids.length) return 1
  return kids.reduce((total, child) => total + leafCount(child), 0)
}

function textWidth(text: string): number {
  let width = 0
  for (const char of text) width += /[\u4e00-\u9fff\uff00-\uffef]/.test(char) ? FONT : FONT * 0.56
  return width
}

function nodeWidth(text: string, depth: number): number {
  const padding = depth === 0 ? 30 : 22
  return Math.max(MIN_W, Math.min(MAX_W, Math.round(textWidth(text) + padding)))
}

function ellipsis(text: string, limit: number): string {
  const chars = Array.from(text)
  if (chars.length <= limit) return text
  return chars.slice(0, Math.max(2, limit - 1)).join('') + '…'
}

const tree = computed(() => parseMindmap(props.source))

const layout = computed(() => {
  const root = tree.value
  if (!root) return { nodes: [] as PlacedNode[], edges: [] as { id: string; path: string }[], bounds: { minX: -100, maxX: 100, minY: -100, maxY: 100 } }

  const placed: PlacedNode[] = []
  const edges: { id: string; path: string }[] = []

  const rootW = nodeWidth(root.text, 0)
  const rootPlaced: PlacedNode = {
    id: root.id,
    text: root.text,
    depth: 0,
    dir: 1,
    x: 0,
    y: 0,
    w: rootW,
    h: HEIGHT + 6,
    hasChildren: root.children.length > 0,
    collapsed: collapsed.value.has(root.id),
  }
  placed.push(rootPlaced)

  const branches = visibleChildren(root)
  const totalLeaves = branches.reduce((total, child) => total + leafCount(child), 0) || 1
  // 按叶子权重把分支均分到左右两侧
  const right: MindNode[] = []
  const left: MindNode[] = []
  let rightLeaves = 0
  for (const branch of branches) {
    const leaves = leafCount(branch)
    if (rightLeaves + leaves / 2 <= totalLeaves / 2) {
      right.push(branch)
      rightLeaves += leaves
    } else {
      left.push(branch)
    }
  }

  const placeSide = (side: MindNode[], dir: 1 | -1) => {
    const total = side.reduce((sum, node) => sum + leafCount(node), 0) || 1
    let cursor = (-total * ROW) / 2

    const walk = (node: MindNode, level: number, start: number, parent: PlacedNode): PlacedNode => {
      const span = leafCount(node) * ROW
      const width = nodeWidth(node.text, level)
      const gap = level === 1 ? GAP_ROOT : GAP_LEVEL
      // 关键：按父子盒子边缘留白，而不是按中心等距，否则宽节点一定互相压住
      const x = parent.x + dir * (parent.w / 2 + gap + width / 2)
      const y = start + span / 2
      const current: PlacedNode = {
        id: node.id,
        text: ellipsis(node.text, Math.max(4, Math.floor((width - 20) / FONT))),
        depth: level,
        dir,
        x,
        y,
        w: width,
        h: HEIGHT,
        hasChildren: node.children.length > 0,
        collapsed: collapsed.value.has(node.id),
      }
      placed.push(current)
      return current
    }

    for (const branch of side) {
      const current = walk(branch, 1, cursor, rootPlaced)
      edges.push({ id: `${root.id}-${current.id}`, path: curve(rootPlaced, current) })
      cursor += leafCount(branch) * ROW

      const placeChildren = (node: MindNode, parentPlaced: PlacedNode) => {
        const children = visibleChildren(node)
        if (!children.length) return
        let childCursor = parentPlaced.y - (leafCount(node) * ROW) / 2
        for (const child of children) {
          const childPlaced = walk(child, parentPlaced.depth + 1, childCursor, parentPlaced)
          edges.push({ id: `${parentPlaced.id}-${childPlaced.id}`, path: curve(parentPlaced, childPlaced) })
          childCursor += leafCount(child) * ROW
          placeChildren(child, childPlaced)
        }
      }
      placeChildren(branch, current)
    }
  }

  placeSide(right, 1)
  placeSide(left, -1)

  const minX = Math.min(...placed.map((node) => node.x - node.w / 2)) - 40
  const maxX = Math.max(...placed.map((node) => node.x + node.w / 2)) + 40
  const minY = Math.min(...placed.map((node) => node.y - node.h / 2)) - 40
  const maxY = Math.max(...placed.map((node) => node.y + node.h / 2)) + 40

  return { nodes: placed, edges, bounds: { minX, maxX, minY, maxY } }
})

function curve(parent: PlacedNode, child: PlacedNode): string {
  const dir = child.dir
  const startX = parent.x + (parent.depth === 0 ? dir * parent.w / 2 : dir * parent.w / 2)
  const endX = child.x - dir * child.w / 2
  const mid = (startX + endX) / 2
  return `M ${startX} ${parent.y} C ${mid} ${parent.y}, ${mid} ${child.y}, ${endX} ${child.y}`
}

const viewBox = computed(() => {
  const { minX, maxX, minY, maxY } = layout.value.bounds
  const width = Math.max(1, maxX - minX)
  const height = Math.max(1, maxY - minY)
  const factor = 1 / Math.max(0.2, scale.value)
  const cx = (minX + maxX) / 2 + offset.value.x
  const cy = (minY + maxY) / 2 + offset.value.y
  const halfW = (width * factor) / 2
  const halfH = (height * factor) / 2
  return `${cx - halfW} ${cy - halfH} ${halfW * 2} ${halfH * 2}`
})

const FILLS = ['#2f6bff', '#e8f0ff', '#f2f7ff', '#f7faff']
const TEXTS = ['#ffffff', '#1b3a6b', '#274564', '#35506e']

function fillFor(depth: number): string {
  return FILLS[Math.min(depth, FILLS.length - 1)]
}
function strokeFor(depth: number): string {
  return depth === 0 ? '#1f57d6' : depth === 1 ? '#b9d0ff' : '#d7e4f7'
}
function textFor(depth: number): string {
  return TEXTS[Math.min(depth, TEXTS.length - 1)]
}

function toggle(node: PlacedNode) {
  if (!node.hasChildren) return
  const next = new Set(collapsed.value)
  if (next.has(node.id)) next.delete(node.id)
  else next.add(node.id)
  collapsed.value = next
}

function zoom(factor: number) {
  scale.value = Math.min(6, Math.max(0.4, scale.value * factor))
}

function reset() {
  scale.value = 1
  offset.value = { x: 0, y: 0 }
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  zoom(event.deltaY < 0 ? 1.12 : 1 / 1.12)
}

function onPointerDown(event: PointerEvent) {
  dragging.value = { x: event.clientX, y: event.clientY, ox: offset.value.x, oy: offset.value.y }
  ;(event.target as Element).setPointerCapture?.(event.pointerId)
}

function onPointerMove(event: PointerEvent) {
  if (!dragging.value) return
  const scalePx = 1 / Math.max(0.2, scale.value)
  offset.value = {
    x: dragging.value.ox - (event.clientX - dragging.value.x) * scalePx,
    y: dragging.value.oy - (event.clientY - dragging.value.y) * scalePx,
  }
}

function onPointerUp() {
  dragging.value = null
}
</script>

<template>
  <div class="mindmap-canvas">
    <div class="mindmap-canvas__toolbar">
      <button type="button" title="放大" @click="zoom(1.2)">＋</button>
      <button type="button" title="缩小" @click="zoom(1 / 1.2)">－</button>
      <button type="button" title="复位" @click="reset">复位</button>
      <span>点击节点可折叠，滚轮缩放，拖拽平移</span>
    </div>
    <svg
      v-if="layout.nodes.length"
      class="mindmap-canvas__svg"
      :viewBox="viewBox"
      preserveAspectRatio="xMidYMid meet"
      @wheel.prevent="onWheel"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
    >
      <path v-for="edge in layout.edges" :key="edge.id" :d="edge.path" class="mindmap-edge" />
      <g
        v-for="node in layout.nodes"
        :key="node.id"
        class="mindmap-node"
        :class="{ 'is-collapsed': node.collapsed, 'is-hovered': hovered === node.id }"
        @click.stop="toggle(node)"
        @mouseenter="hovered = node.id"
        @mouseleave="hovered = ''"
      >
        <rect
          :x="node.x - node.w / 2"
          :y="node.y - node.h / 2"
          :width="node.w"
          :height="node.h"
          rx="9"
          :fill="fillFor(node.depth)"
          :stroke="strokeFor(node.depth)"
        />
        <text
          :x="node.x"
          :y="node.y + 4.5"
          text-anchor="middle"
          :fill="textFor(node.depth)"
          :style="{ fontWeight: node.depth <= 1 ? 600 : 400 }"
        >{{ node.text }}</text>
        <circle
          v-if="node.hasChildren"
          :cx="node.x + (node.dir * node.w) / 2"
          :cy="node.y"
          r="4.5"
          class="mindmap-dot"
        />
      </g>
    </svg>
    <p v-else class="mindmap-canvas__empty">这份资源里没有可解析的思维导图结构。</p>
  </div>
</template>

<style scoped>
.mindmap-canvas {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 420px;
  height: 100%;
}

.mindmap-canvas__toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.mindmap-canvas__toolbar button {
  min-width: 30px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid #dbe4f0;
  border-radius: 7px;
  background: #fff;
  color: #334155;
  font-size: 12px;
  cursor: pointer;
}

.mindmap-canvas__toolbar button:hover {
  border-color: #93b4ef;
  color: #1f57d6;
}

.mindmap-canvas__svg {
  flex: 1;
  width: 100%;
  min-height: 380px;
  border: 1px solid #e6eefb;
  border-radius: 14px;
  background: linear-gradient(180deg, #fbfdff, #f4f8ff);
  cursor: grab;
  touch-action: none;
}

.mindmap-edge {
  fill: none;
  stroke: #b9cdea;
  stroke-width: 1.6;
}

.mindmap-node rect {
  stroke-width: 1.2;
  transition: filter 0.15s ease;
}

.mindmap-node text {
  font-size: 13px;
  font-family: inherit;
  user-select: none;
}

.mindmap-node {
  cursor: pointer;
}

.mindmap-node.is-hovered rect {
  filter: drop-shadow(0 3px 8px rgba(47, 107, 255, 0.22));
}

.mindmap-dot {
  fill: #8fb4ee;
  stroke: #fff;
  stroke-width: 1.5;
}

.mindmap-node.is-collapsed .mindmap-dot {
  fill: #2f6bff;
}

.mindmap-canvas__empty {
  margin: 0;
  padding: 28px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  border: 1px dashed #dbe4f0;
  border-radius: 14px;
}
</style>