// 练习中心「错题标签星系」的 3D 渲染引擎（从 ExerciseCenterPage.vue 拆出）。
//
// 页面只保留数据加载、选择态与模板；THREE 场景、纹理生成、动画循环、命中测试与
// 鼠标/键盘交互都在这里。拆开后页面文件 3247 → 1884 行，星系代码只在打开页签时执行。
import { nextTick, ref } from 'vue'
import { hashText } from '@/utils/hashText'

export type GalaxyNode = {
  tag: string
  major?: string
  course?: string
  count?: number
  points?: string[]
  score?: number
  isRelated?: boolean
  hue?: number
  angle?: number
  radius?: number
  [key: string]: any
}

export type GalaxyContext = {
  /** 是否停在星系页签（引擎据此决定渲染与否） */
  isActive: () => boolean
  nodes: () => GalaxyNode[]
  links: () => { source: string; target: string; weight?: number }[]
  reducedMotion: () => boolean
  /** 页面持有的当前选中标签 ref */
  activeTag: { value: string }
  /** 页面持有的 canvas（模板 ref） */
  canvasRef: { value: HTMLCanvasElement | null }
  /** 页面持有的缩放百分比 ref（模板要显示） */
  zoomRef: { value: number }
  /** 已掌握星点数据，页面负责填充 */
  masteredStarsRef: { value: any[] }
}

let THREE: any = null
async function ensureThree(): Promise<any> {
  if (!THREE) THREE = await import('../../node_modules/three/build/three.module.js')
  return THREE
}

export function createTagGalaxyScene(galaxyCtx: GalaxyContext) {
  const activeTag = galaxyCtx.activeTag
  const galaxyCanvas = galaxyCtx.canvasRef
  const galaxyZoom = galaxyCtx.zoomRef
  const masteredStars = galaxyCtx.masteredStarsRef

const galaxyAngle = ref(0)
const galaxyTargets = ref<{ tag: string; x: number; y: number; radius: number }[]>([])
const galaxyMouse = { x: 0, y: 0, targetX: 0, targetY: 0, active: false }
let galaxyFrame: number | null = null
let galaxyRenderer: any = null
let galaxyScene: any = null
let galaxyCamera: any = null
let galaxyRaycaster: any = null
let galaxyPointer: any = null
let galaxyCore: any = null
let galaxyDisk: any = null
let galaxyBackdrop: any = null
let galaxySkyDome: any = null
let galaxyAtmosphereLayers: any[] = []
let galaxyBackgroundSystems: any[] = []
let galaxyDeepField: any = null
let galaxyStarField: any = null
let galaxyDustField: any = null
let galaxyTrackGroup: any = null
let galaxyNebulae: any[] = []
let galaxyMasteredGroup: any = null
let galaxyNodeGroup: any = null
let galaxyLinkGroup: any = null
let galaxyNodeMeshes: any[] = []
let galaxyLinkMeshes: any[] = []
let galaxyNeedsRebuild = true
let galaxySceneSignature = ''
let galaxyRefreshVersion = 0
let galaxyReferenceTexture: any = null
let galaxyReferenceLoading = false
const galaxyTextureCache = new Map<string, any>()

async function startTagGalaxy() {
  await ensureThree()
  stopTagGalaxy()
  const nextSignature = [
    galaxyCtx.nodes().map((node: any) => `${node.tag}:${node.count}`).join('|'),
    galaxyCtx.links().map((link: any) => `${link.source}-${link.target}:${link.weight}`).join('|'),
    masteredStars.value.map((item: any) => item.id).join('|'),
    `refresh:${galaxyRefreshVersion}`,
  ].join('::')
  if (nextSignature !== galaxySceneSignature || !galaxyScene || !galaxyCamera) {
    galaxySceneSignature = nextSignature
    galaxyNeedsRebuild = true
  } else {
    refreshGalaxyFocusState()
  }
  animateTagGalaxy()
}

function stopTagGalaxy() {
  if (galaxyFrame !== null) {
    window.cancelAnimationFrame(galaxyFrame)
    galaxyFrame = null
  }
}

function disposeGalaxyObject(item: any, disposeMap = true) {
  if (!item) return
  item.traverse?.((child: any) => {
    child.geometry?.dispose?.()
    if (Array.isArray(child.material)) {
      child.material.forEach((material: any) => {
        if (disposeMap) material.map?.dispose?.()
        material.dispose?.()
      })
    } else if (child.material) {
      if (disposeMap) child.material.map?.dispose?.()
      child.material.dispose?.()
    }
  })
  if (!item.traverse) {
    item.geometry?.dispose?.()
    if (disposeMap) item.material?.map?.dispose?.()
    item.material?.dispose?.()
  }
}

function disposeTagGalaxyScene() {
  for (const item of [...galaxyNodeMeshes, ...galaxyLinkMeshes, ...galaxyNebulae, ...galaxyAtmosphereLayers, ...galaxyBackgroundSystems, galaxyCore, galaxyDisk, galaxySkyDome, galaxyDeepField, galaxyStarField, galaxyDustField, galaxyTrackGroup, galaxyMasteredGroup]) disposeGalaxyObject(item, false)
  disposeGalaxyObject(galaxyBackdrop, false)
  galaxyNodeMeshes = []
  galaxyLinkMeshes = []
  galaxyNebulae = []
  galaxyScene?.clear?.()
  galaxyScene = null
  galaxyCamera = null
  galaxyRaycaster = null
  galaxyPointer = null
  galaxyCore = null
  galaxyDisk = null
  galaxyBackdrop = null
  galaxySkyDome = null
  galaxyAtmosphereLayers = []
  galaxyBackgroundSystems = []
  galaxyDeepField = null
  galaxyStarField = null
  galaxyDustField = null
  galaxyTrackGroup = null
  galaxyNodeGroup = null
  galaxyMasteredGroup = null
  galaxyLinkGroup = null
}

function makeGlowTexture(inner: string, mid: string, outer: string, size = 128) {
  const cacheKey = `glow:${inner}:${mid}:${outer}:${size}`
  const cached = galaxyTextureCache.get(cacheKey)
  if (cached) return cached
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  gradient.addColorStop(0, inner)
  gradient.addColorStop(0.3, mid)
  gradient.addColorStop(1, outer)
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  const texture = new THREE.CanvasTexture(canvas)
  galaxyTextureCache.set(cacheKey, texture)
  return texture
}

function makeNebulaTexture(seedKey: string, width = 1024, height = 1024, density = 28) {
  const cacheKey = `nebula:${seedKey}:${width}:${height}:${density}`
  const cached = galaxyTextureCache.get(cacheKey)
  if (cached) return cached
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')!
  const base = ctx.createLinearGradient(0, 0, width, height)
  base.addColorStop(0, 'rgba(46, 64, 86,1)')
  base.addColorStop(0.42, 'rgba(46, 64, 86,1)')
  base.addColorStop(1, 'rgba(46, 64, 86,1)')
  ctx.fillStyle = base
  ctx.fillRect(0, 0, width, height)

  for (let i = 0; i < density; i += 1) {
    const seed = hashText(`${seedKey}-cloud-${i}`)
    const x = ((seed % 1000) / 1000) * width
    const y = ((hashText(`${seedKey}-cloud-y-${i}`) % 1000) / 1000) * height
    const radius = width * (0.16 + (seed % 340) / 1000)
    const hue = seed % 6
    const colorA = hue === 0
      ? 'rgba(162, 199, 225,0.3)'
      : hue === 1
        ? 'rgba(162, 199, 225,0.28)'
        : hue === 2
          ? 'rgba(119, 194, 174,0.25)'
          : hue === 3
            ? 'rgba(238, 154, 171,0.21)'
            : hue === 4
              ? 'rgba(119, 194, 174,0.23)'
              : 'rgba(238, 154, 171,0.23)'
    const colorB = hue === 0
      ? 'rgba(46, 64, 86,0.08)'
      : hue === 1
        ? 'rgba(46, 64, 86,0.08)'
        : hue === 2
          ? 'rgba(35, 64, 58,0.07)'
          : hue === 3
            ? 'rgba(74, 38, 48,0.055)'
            : hue === 4
              ? 'rgba(35, 64, 58,0.06)'
              : 'rgba(46, 64, 86,0.06)'
    const cloud = ctx.createRadialGradient(x, y, 0, x, y, radius)
    cloud.addColorStop(0, colorA)
    cloud.addColorStop(0.5, colorB)
    cloud.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = cloud
    ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2)
  }

  for (let i = 0; i < 14; i += 1) {
    const seed = hashText(`${seedKey}-dust-lane-${i}`)
    ctx.save()
    ctx.translate(((seed % 1000) / 1000) * width, ((hashText(`${seedKey}-lane-y-${i}`) % 1000) / 1000) * height)
    ctx.rotate(((seed % 360) / 180) * Math.PI)
    const lane = ctx.createLinearGradient(-width * 0.42, 0, width * 0.42, 0)
    lane.addColorStop(0, 'rgba(0,0,0,0)')
    lane.addColorStop(0.46, 'rgba(0,0,0,0.12)')
    lane.addColorStop(0.52, 'rgba(0,0,0,0.22)')
    lane.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = lane
    ctx.fillRect(-width * 0.5, -height * 0.045, width, height * 0.09)
    ctx.restore()
  }

  ctx.globalCompositeOperation = 'screen'
  for (let i = 0; i < 7; i += 1) {
    const seed = hashText(`${seedKey}-soft-veil-${i}`)
    ctx.save()
    ctx.translate(((seed % 1000) / 1000) * width, ((hashText(`${seedKey}-soft-y-${i}`) % 1000) / 1000) * height)
    ctx.rotate(((seed % 160) - 80) * Math.PI / 180)
    const veil = ctx.createLinearGradient(-width * 0.58, 0, width * 0.58, 0)
    veil.addColorStop(0, 'rgba(0,0,0,0)')
    veil.addColorStop(0.36, 'rgba(119, 194, 174,0.095)')
    veil.addColorStop(0.5, 'rgba(207, 226, 241,0.125)')
    veil.addColorStop(0.64, 'rgba(162, 199, 225,0.105)')
    veil.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = veil
    ctx.fillRect(-width * 0.58, -height * 0.085, width * 1.16, height * 0.17)
    ctx.restore()
  }
  ctx.globalCompositeOperation = 'source-over'

  const vignette = ctx.createRadialGradient(width * 0.5, height * 0.5, width * 0.1, width * 0.5, height * 0.5, width * 0.74)
  vignette.addColorStop(0, 'rgba(0,0,0,0)')
  vignette.addColorStop(0.68, 'rgba(0,0,0,0.04)')
  vignette.addColorStop(1, 'rgba(0,0,0,0.5)')
  ctx.fillStyle = vignette
  ctx.fillRect(0, 0, width, height)

  const texture = new THREE.CanvasTexture(canvas)
  if ('SRGBColorSpace' in THREE) texture.colorSpace = THREE.SRGBColorSpace
  texture.needsUpdate = true
  galaxyTextureCache.set(cacheKey, texture)
  return texture
}

function makeDistantGalaxyTexture(seedKey: string, size = 512) {
  const cacheKey = `distant:${seedKey}:${size}`
  const cached = galaxyTextureCache.get(cacheKey)
  if (cached) return cached
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')!
  const center = size / 2
  ctx.clearRect(0, 0, size, size)

  const seed = hashText(seedKey)
  ctx.save()
  ctx.translate(center, center)
  ctx.rotate(((seed % 90) - 45) * Math.PI / 180)
  ctx.scale(1, 0.42 + (seed % 18) / 100)

  const palette = seed % 5
  const coreColor = palette === 0 ? 'rgba(252, 239, 213,0.9)' : palette === 1 ? 'rgba(236, 244, 250,0.88)' : palette === 2 ? 'rgba(236, 244, 250,0.86)' : palette === 3 ? 'rgba(223, 242, 235,0.82)' : 'rgba(246, 195, 208,0.86)'
  const armA = palette === 0 ? 'rgba(248, 223, 174,0.4)' : palette === 1 ? 'rgba(207, 226, 241,0.4)' : palette === 2 ? 'rgba(207, 226, 241,0.38)' : palette === 3 ? 'rgba(183, 225, 212,0.34)' : 'rgba(246, 195, 208,0.32)'
  const armB = palette === 0 ? 'rgba(207, 226, 241,0.3)' : palette === 1 ? 'rgba(183, 225, 212,0.28)' : palette === 2 ? 'rgba(246, 195, 208,0.28)' : palette === 3 ? 'rgba(207, 226, 241,0.26)' : 'rgba(248, 223, 174,0.28)'
  const armC = palette === 0 ? 'rgba(207, 226, 241,0.2)' : palette === 1 ? 'rgba(246, 195, 208,0.2)' : palette === 2 ? 'rgba(183, 225, 212,0.2)' : palette === 3 ? 'rgba(246, 195, 208,0.18)' : 'rgba(207, 226, 241,0.2)'

  const halo = ctx.createRadialGradient(0, 0, 0, 0, 0, size * 0.48)
  halo.addColorStop(0, coreColor)
  halo.addColorStop(0.08, armA)
  halo.addColorStop(0.28, armB)
  halo.addColorStop(0.62, armC)
  halo.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.fillStyle = halo
  ctx.fillRect(-center, -center, size, size)

  ctx.globalCompositeOperation = 'lighter'
  for (let arm = 0; arm < 3; arm += 1) {
    ctx.beginPath()
    for (let i = 0; i < 190; i += 1) {
      const t = i / 189
      const spin = arm * Math.PI * 0.66 + t * Math.PI * (3.2 + (seed % 12) / 10)
      const radius = 8 + Math.pow(t, 0.74) * size * 0.42
      const wobble = Math.sin(t * Math.PI * 7 + arm) * 5
      const x = Math.cos(spin) * (radius + wobble)
      const y = Math.sin(spin) * (radius * 0.62 + wobble * 0.4)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.strokeStyle = arm === 0 ? armA : arm === 1 ? armB : armC
    ctx.lineWidth = size * (0.028 + arm * 0.007)
    ctx.shadowColor = palette === 2 ? 'rgba(207, 226, 241,0.5)' : palette === 3 ? 'rgba(183, 225, 212,0.42)' : 'rgba(207, 226, 241,0.46)'
    ctx.shadowBlur = 34
    ctx.stroke()
  }

  for (let i = 0; i < 430; i += 1) {
    const dotSeed = hashText(`${seedKey}-dot-${i}`)
    const t = (dotSeed % 1000) / 1000
    const arm = i % 3
    const spin = arm * Math.PI * 0.66 + t * Math.PI * 4.2 + ((dotSeed % 80) / 80)
    const radius = Math.sqrt(t) * size * 0.43
    const x = Math.cos(spin) * radius + ((dotSeed % 30) - 15)
    const y = Math.sin(spin) * radius * 0.55 + ((hashText(`${seedKey}-dot-y-${i}`) % 24) - 12)
    const dot = 0.45 + (dotSeed % 14) / 10
    ctx.fillStyle = i % 7 === 0 ? 'rgba(252, 239, 213,0.9)' : palette === 2 ? 'rgba(236, 244, 250,0.82)' : palette === 3 ? 'rgba(223, 242, 235,0.78)' : palette === 4 ? 'rgba(251, 227, 233,0.76)' : 'rgba(236, 244, 250,0.78)'
    ctx.beginPath()
    ctx.arc(x, y, dot, 0, Math.PI * 2)
    ctx.fill()
  }

  const dust = ctx.createLinearGradient(-size * 0.36, 0, size * 0.36, 0)
  dust.addColorStop(0, 'rgba(0,0,0,0)')
  dust.addColorStop(0.48, 'rgba(0,0,0,0.28)')
  dust.addColorStop(0.55, 'rgba(0,0,0,0.18)')
  dust.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.globalCompositeOperation = 'source-over'
  ctx.fillStyle = dust
  ctx.fillRect(-size * 0.38, -size * 0.025, size * 0.76, size * 0.05)
  ctx.restore()

  const fade = ctx.createRadialGradient(center, center, size * 0.08, center, center, size * 0.5)
  fade.addColorStop(0, 'rgba(255,255,255,0)')
  fade.addColorStop(0.78, 'rgba(255,255,255,0)')
  fade.addColorStop(1, 'rgba(0,0,0,0.35)')
  ctx.fillStyle = fade
  ctx.fillRect(0, 0, size, size)

  const texture = new THREE.CanvasTexture(canvas)
  if ('SRGBColorSpace' in THREE) texture.colorSpace = THREE.SRGBColorSpace
  texture.needsUpdate = true
  galaxyTextureCache.set(cacheKey, texture)
  return texture
}

function makeLabelTexture(text: string, subtext = '') {
  const cacheKey = `label:${text}:${subtext}`
  const cached = galaxyTextureCache.get(cacheKey)
  if (cached) return cached
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 96
  const ctx = canvas.getContext('2d')!
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.textAlign = 'center'
  ctx.shadowColor = 'rgba(0,0,0,0.9)'
  ctx.shadowBlur = 8
  ctx.fillStyle = 'rgba(248, 251, 253,0.92)'
  ctx.font = '700 28px Microsoft YaHei, system-ui, sans-serif'
  ctx.fillText(text.slice(0, 9), 128, 40)
  ctx.fillStyle = 'rgba(207, 226, 241,0.8)'
  ctx.font = '600 18px Microsoft YaHei, system-ui, sans-serif'
  ctx.fillText(subtext, 128, 68)
  const texture = new THREE.CanvasTexture(canvas)
  galaxyTextureCache.set(cacheKey, texture)
  return texture
}

function requestReferenceGalaxyTexture() {
  if (galaxyReferenceTexture) return galaxyReferenceTexture
  if (galaxyReferenceLoading) return null
  galaxyReferenceLoading = true
  const image = new Image()
  image.onload = () => {
    const canvas = document.createElement('canvas')
    canvas.width = 1920
    canvas.height = 1040
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const sourceY = Math.floor(image.height * 0.31)
    const sourceHeight = Math.floor(image.height * 0.37)
    ctx.drawImage(image, 0, sourceY, image.width, sourceHeight, 0, 0, canvas.width, canvas.height)

    const coolTint = ctx.createLinearGradient(0, 0, canvas.width, canvas.height)
    coolTint.addColorStop(0, 'rgba(46, 64, 86, 0.16)')
    coolTint.addColorStop(0.45, 'rgba(252, 239, 213, 0.04)')
    coolTint.addColorStop(1, 'rgba(106, 147, 184, 0.16)')
    ctx.fillStyle = coolTint
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    const coreBloom = ctx.createRadialGradient(canvas.width * 0.5, canvas.height * 0.49, 0, canvas.width * 0.5, canvas.height * 0.49, canvas.width * 0.22)
    coreBloom.addColorStop(0, 'rgba(254, 249, 238,0.34)')
    coreBloom.addColorStop(0.2, 'rgba(252, 239, 213,0.16)')
    coreBloom.addColorStop(0.58, 'rgba(207, 226, 241,0.07)')
    coreBloom.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = coreBloom
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    const edgeFade = ctx.createRadialGradient(canvas.width * 0.5, canvas.height * 0.5, canvas.width * 0.12, canvas.width * 0.5, canvas.height * 0.5, canvas.width * 0.62)
    edgeFade.addColorStop(0, 'rgba(0,0,0,0)')
    edgeFade.addColorStop(0.56, 'rgba(0,0,0,0.12)')
    edgeFade.addColorStop(1, 'rgba(0,0,0,0.9)')
    ctx.fillStyle = edgeFade
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    const texture = new THREE.CanvasTexture(canvas)
    if ('SRGBColorSpace' in THREE) texture.colorSpace = THREE.SRGBColorSpace
    texture.needsUpdate = true
    galaxyReferenceTexture = texture
    galaxyReferenceLoading = false
    galaxyNeedsRebuild = true
    if (galaxyCtx.isActive()) void nextTick(startTagGalaxy)
  }
  image.onerror = () => {
    galaxyReferenceLoading = false
  }
  image.src = '/assets/tag-galaxy-reference.jpg'
  return null
}

function ensureTagGalaxyRenderer() {
  const canvas = galaxyCanvas.value
  if (!canvas || !galaxyCtx.isActive()) return false
  const rect = canvas.getBoundingClientRect()
  const width = Math.max(320, rect.width)
  const height = Math.max(280, rect.height)
  if (!galaxyRenderer) {
    galaxyRenderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false })
    galaxyRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    galaxyRenderer.setClearColor(0x050817, 1)
  }
  galaxyRenderer.setSize(width, height, false)
  if (!galaxyScene || !galaxyCamera || galaxyNeedsRebuild) rebuildTagGalaxyScene(width, height)
  galaxyCamera.aspect = width / height
  galaxyCamera.position.z = 560 / galaxyZoom.value
  galaxyCamera.updateProjectionMatrix()
  return true
}

function rebuildTagGalaxyScene(width: number, height: number) {
  disposeTagGalaxyScene()
  galaxyScene = new THREE.Scene()
  galaxyCamera = new THREE.PerspectiveCamera(48, width / height, 1, 3000)
  galaxyCamera.position.set(0, 0, 560 / galaxyZoom.value)
  galaxyRaycaster = new THREE.Raycaster()
  galaxyPointer = new THREE.Vector2()

  galaxySkyDome = new THREE.Mesh(
    new THREE.SphereGeometry(1850, 64, 32),
    new THREE.MeshBasicMaterial({
      map: makeNebulaTexture('sky-dome', 1600, 900, 42),
      side: THREE.BackSide,
      transparent: true,
      opacity: 0.96,
      depthWrite: false,
    })
  )
  galaxySkyDome.rotation.set(0.18, -0.22, 0.12)
  galaxyScene.add(galaxySkyDome)

  const atmosphereConfigs = [
    { key: 'near-left', x: -760, y: 120, z: -430, w: 1500, h: 1040, opacity: 0.3, rotate: -0.42 },
    { key: 'near-right', x: 820, y: -80, z: -520, w: 1650, h: 1120, opacity: 0.27, rotate: 0.36 },
    { key: 'upper-veil', x: 80, y: 520, z: -670, w: 2150, h: 880, opacity: 0.26, rotate: 0.08 },
    { key: 'lower-veil', x: -70, y: -560, z: -720, w: 2150, h: 880, opacity: 0.24, rotate: -0.1 },
    { key: 'far-wrap', x: 0, y: 0, z: -980, w: 3000, h: 1900, opacity: 0.34, rotate: 0.02 },
    { key: 'diagonal-mist-a', x: -220, y: 180, z: -820, w: 2500, h: 620, opacity: 0.2, rotate: -0.36 },
    { key: 'diagonal-mist-b', x: 260, y: -160, z: -900, w: 2500, h: 620, opacity: 0.18, rotate: 0.32 },
  ]
  for (const config of atmosphereConfigs) {
    const layer = new THREE.Sprite(new THREE.SpriteMaterial({
      map: makeNebulaTexture(`atmosphere-${config.key}`, 1024, 1024, 30),
      transparent: true,
      opacity: config.opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }))
    layer.position.set(config.x, config.y, config.z)
    layer.scale.set(config.w, config.h, 1)
    layer.rotation.z = config.rotate
    layer.userData = { ...config, baseX: config.x, baseY: config.y, baseZ: config.z, baseScaleX: config.w, baseScaleY: config.h, type: 'atmosphere' }
    galaxyAtmosphereLayers.push(layer)
    galaxyScene.add(layer)
  }

  const backgroundGalaxyConfigs = [
    { key: 'spiral-left', x: -980, y: 350, z: -1180, w: 470, h: 290, opacity: 0.42, rotate: -0.28, speed: 0.018 },
    { key: 'spiral-right', x: 1080, y: 260, z: -1260, w: 550, h: 330, opacity: 0.4, rotate: 0.32, speed: -0.014 },
    { key: 'tiny-upper', x: 520, y: 620, z: -1420, w: 320, h: 200, opacity: 0.34, rotate: -0.7, speed: 0.022 },
    { key: 'edge-lower', x: -720, y: -610, z: -1320, w: 660, h: 370, opacity: 0.36, rotate: 0.18, speed: -0.012 },
    { key: 'far-center', x: 40, y: -470, z: -1540, w: 370, h: 230, opacity: 0.3, rotate: -0.08, speed: 0.016 },
    { key: 'ghost-far-left', x: -1380, y: -280, z: -1580, w: 410, h: 250, opacity: 0.28, rotate: 0.48, speed: 0.01 },
    { key: 'ghost-far-right', x: 1380, y: -420, z: -1620, w: 350, h: 220, opacity: 0.26, rotate: -0.44, speed: -0.012 },
    { key: 'rim-upper-left-a', x: -1580, y: 760, z: -1660, w: 290, h: 180, opacity: 0.34, rotate: -0.18, speed: 0.013 },
    { key: 'rim-upper-left-b', x: -1280, y: 900, z: -1780, w: 230, h: 142, opacity: 0.28, rotate: 0.62, speed: -0.017 },
    { key: 'rim-upper-right-a', x: 1540, y: 760, z: -1700, w: 310, h: 190, opacity: 0.33, rotate: -0.56, speed: 0.014 },
    { key: 'rim-upper-right-b', x: 1260, y: 930, z: -1840, w: 225, h: 140, opacity: 0.27, rotate: 0.28, speed: 0.018 },
    { key: 'rim-lower-left-a', x: -1600, y: -820, z: -1720, w: 330, h: 200, opacity: 0.32, rotate: 0.34, speed: -0.015 },
    { key: 'rim-lower-right-a', x: 1580, y: -850, z: -1740, w: 300, h: 190, opacity: 0.31, rotate: -0.32, speed: 0.016 },
    { key: 'distant-cluster-top', x: 40, y: 1010, z: -1900, w: 250, h: 155, opacity: 0.25, rotate: -0.12, speed: 0.02 },
    { key: 'distant-cluster-bottom', x: -120, y: -1040, z: -1880, w: 270, h: 165, opacity: 0.26, rotate: 0.42, speed: -0.018 },
  ]
  for (const config of backgroundGalaxyConfigs) {
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: makeDistantGalaxyTexture(`background-galaxy-${config.key}`, 640),
      transparent: true,
      opacity: config.opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      rotation: config.rotate,
    }))
    sprite.position.set(config.x, config.y, config.z)
    sprite.scale.set(config.w, config.h, 1)
    sprite.userData = { ...config, baseX: config.x, baseY: config.y, baseZ: config.z, baseScaleX: config.w, baseScaleY: config.h, type: 'background-galaxy' }
    galaxyBackgroundSystems.push(sprite)
    galaxyScene.add(sprite)
  }

  const backgroundNebulaConfigs = [
    { key: 'blue-cloud-left', x: -1180, y: -120, z: -1100, w: 1220, h: 980, opacity: 0.22, rotate: -0.22, speed: 0.006 },
    { key: 'violet-cloud-right', x: 1160, y: -260, z: -1160, w: 1320, h: 1020, opacity: 0.2, rotate: 0.26, speed: -0.007 },
    { key: 'top-aurora', x: 0, y: 820, z: -1250, w: 2200, h: 640, opacity: 0.18, rotate: 0.04, speed: 0.004 },
    { key: 'bottom-aurora', x: -180, y: -820, z: -1220, w: 2200, h: 680, opacity: 0.17, rotate: -0.08, speed: -0.005 },
    { key: 'center-haze', x: 0, y: 80, z: -1360, w: 2400, h: 1200, opacity: 0.16, rotate: 0.16, speed: 0.003 },
    { key: 'left-shadow-haze', x: -900, y: 520, z: -1500, w: 1500, h: 950, opacity: 0.14, rotate: -0.48, speed: -0.004 },
    { key: 'teal-fog-field', x: 760, y: 540, z: -1460, w: 1450, h: 940, opacity: 0.15, rotate: 0.58, speed: 0.005 },
    { key: 'rose-violet-field', x: -1020, y: -500, z: -1480, w: 1520, h: 980, opacity: 0.14, rotate: -0.62, speed: -0.004 },
    { key: 'amber-dust-field', x: 160, y: -80, z: -1680, w: 2600, h: 900, opacity: 0.12, rotate: 0.24, speed: 0.003 },
    { key: 'bright-cyan-nebula', x: -1460, y: 220, z: -1320, w: 1120, h: 820, opacity: 0.4, rotate: 0.18, speed: 0.006 },
    { key: 'bright-rose-nebula', x: 1450, y: 420, z: -1380, w: 1180, h: 860, opacity: 0.38, rotate: -0.26, speed: -0.006 },
    { key: 'bright-amber-nebula', x: 980, y: -760, z: -1500, w: 1220, h: 780, opacity: 0.34, rotate: 0.4, speed: 0.005 },
    { key: 'bright-violet-nebula', x: -1120, y: -860, z: -1540, w: 1260, h: 820, opacity: 0.34, rotate: -0.36, speed: -0.005 },
  ]
  for (const config of backgroundNebulaConfigs) {
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: makeNebulaTexture(`background-nebula-${config.key}`, 1024, 1024, 36),
      transparent: true,
      opacity: config.opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      rotation: config.rotate,
    }))
    sprite.position.set(config.x, config.y, config.z)
    sprite.scale.set(config.w, config.h, 1)
    sprite.userData = { ...config, baseX: config.x, baseY: config.y, baseZ: config.z, baseScaleX: config.w, baseScaleY: config.h, type: 'background-nebula' }
    galaxyBackgroundSystems.push(sprite)
    galaxyScene.add(sprite)
  }

  const deepPositions: number[] = []
  const deepColors: number[] = []
  for (let i = 0; i < 6200; i += 1) {
    const seed = hashText(`deep-space-${i}`)
    const ySeed = hashText(`deep-space-y-${i}`)
    const zSeed = hashText(`deep-space-z-${i}`)
    deepPositions.push(((seed % 1000) / 1000 - 0.5) * 3000)
    deepPositions.push(((ySeed % 1000) / 1000 - 0.5) * 1800)
    deepPositions.push(-900 + ((zSeed % 1000) / 1000 - 0.5) * 700)
    const warmth = (hashText(`deep-space-c-${i}`) % 100) / 100
    deepColors.push(0.56 + warmth * 0.34, 0.66 + warmth * 0.28, 0.86 + warmth * 0.14)
  }
  const deepGeometry = new THREE.BufferGeometry()
  deepGeometry.setAttribute('position', new THREE.Float32BufferAttribute(deepPositions, 3))
  deepGeometry.setAttribute('color', new THREE.Float32BufferAttribute(deepColors, 3))
  galaxyDeepField = new THREE.Points(deepGeometry, new THREE.PointsMaterial({ size: 2.25, vertexColors: true, transparent: true, opacity: 0.58, blending: THREE.AdditiveBlending, depthWrite: false }))
  galaxyScene.add(galaxyDeepField)

  const spaceWashTexture = makeGlowTexture('rgba(207, 226, 241,0.46)', 'rgba(106, 147, 184,0.3)', 'rgba(0,0,0,0)', 256)
  const spaceWash = new THREE.Sprite(new THREE.SpriteMaterial({ map: spaceWashTexture, transparent: true, opacity: 0.62, blending: THREE.AdditiveBlending, depthWrite: false }))
  spaceWash.position.set(0, 0, -1080)
  spaceWash.scale.set(3000, 1900, 1)
  spaceWash.userData = { baseX: 0, baseY: 0, baseScaleX: 3000, baseScaleY: 1900, type: 'wide-nebula' }
  galaxyNebulae.push(spaceWash)
  galaxyScene.add(spaceWash)

  galaxyBackdrop = new THREE.Group()
  const referenceTexture = requestReferenceGalaxyTexture()
  if (referenceTexture) {
    const aspect = width / Math.max(height, 1)
    const backdropWidth = aspect > 1.25 ? 1900 : 1500
    const backdropHeight = aspect > 1.25 ? 1060 : 1160
    const photoPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(backdropWidth, backdropHeight, 1, 1),
      new THREE.MeshBasicMaterial({ map: referenceTexture, transparent: true, opacity: 0.68, blending: THREE.AdditiveBlending, depthWrite: false })
    )
    photoPlane.position.set(0, 0, -280)
    photoPlane.rotation.z = -0.015
    photoPlane.userData = { baseScaleX: 1, baseScaleY: 1, type: 'photo' }
    galaxyBackdrop.add(photoPlane)
  }
  const wideNebulaTexture = makeGlowTexture('rgba(207, 226, 241,0.24)', 'rgba(162, 199, 225,0.16)', 'rgba(0,0,0,0)', 256)
  for (let i = 0; i < 5; i += 1) {
    const wide = new THREE.Sprite(new THREE.SpriteMaterial({ map: wideNebulaTexture, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false }))
    const seed = hashText(`wide-nebula-${i}`)
    wide.position.set(((seed % 1000) / 1000 - 0.5) * 1500, ((hashText(`wide-nebula-y-${i}`) % 1000) / 1000 - 0.5) * 820, -760 + i * 36)
    const wideW = 680 + (seed % 420)
    const wideH = 360 + (seed % 260)
    wide.scale.set(wideW, wideH, 1)
    wide.userData = { baseX: wide.position.x, baseY: wide.position.y, baseScaleX: wideW, baseScaleY: wideH, type: 'wide-nebula' }
    galaxyNebulae.push(wide)
    galaxyScene.add(wide)
  }

  const softHaloTexture = makeGlowTexture('rgba(252, 239, 213,0.42)', 'rgba(162, 199, 225,0.17)', 'rgba(0,0,0,0)', 256)
  const innerHalo = new THREE.Sprite(new THREE.SpriteMaterial({ map: softHaloTexture, transparent: true, opacity: referenceTexture ? 0.34 : 0.64, blending: THREE.AdditiveBlending, depthWrite: false }))
  innerHalo.position.set(0, -6, -205)
  innerHalo.scale.set(680, 460, 1)
  innerHalo.userData = { baseScaleX: 680, baseScaleY: 460 }
  galaxyBackdrop.add(innerHalo)
  const edgeMistTexture = makeGlowTexture('rgba(207, 226, 241,0.13)', 'rgba(106, 147, 184,0.09)', 'rgba(0,0,0,0)', 256)
  for (let i = 0; i < 4; i += 1) {
    const mist = new THREE.Sprite(new THREE.SpriteMaterial({ map: edgeMistTexture, transparent: true, opacity: 0.13, blending: THREE.AdditiveBlending, depthWrite: false }))
    const seed = hashText(`reference-mist-${i}`)
    mist.position.set(((seed % 1000) / 1000 - 0.5) * 1100, ((hashText(`reference-mist-y-${i}`) % 1000) / 1000 - 0.5) * 520, -245 + i * 8)
    const mistWidth = 520 + (seed % 320)
    const mistHeight = 240 + (seed % 210)
    mist.scale.set(mistWidth, mistHeight, 1)
    mist.userData = { baseScaleX: mistWidth, baseScaleY: mistHeight }
    galaxyBackdrop.add(mist)
  }
  galaxyScene.add(galaxyBackdrop)

  const starPositions: number[] = []
  const starColors: number[] = []
  for (let i = 0; i < 4600; i += 1) {
    const seed = hashText(`three-star-${i}`)
    starPositions.push(((seed % 1000) / 1000 - 0.5) * 2300)
    starPositions.push(((hashText(`three-star-y-${i}`) % 1000) / 1000 - 0.5) * 1350)
    starPositions.push(((hashText(`three-star-z-${i}`) % 1000) / 1000 - 0.5) * 1300)
    const cool = (seed % 100) / 100
    starColors.push(0.72 + cool * 0.28, 0.82 + cool * 0.16, 1)
  }
  const starGeometry = new THREE.BufferGeometry()
  starGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starPositions, 3))
  starGeometry.setAttribute('color', new THREE.Float32BufferAttribute(starColors, 3))
  galaxyStarField = new THREE.Points(starGeometry, new THREE.PointsMaterial({ size: 2.05, vertexColors: true, transparent: true, opacity: referenceTexture ? 0.58 : 0.82, blending: THREE.AdditiveBlending, depthWrite: false }))
  galaxyScene.add(galaxyStarField)

  const dustPositions: number[] = []
  const dustColors: number[] = []
  for (let i = 0; i < 4200; i += 1) {
    const t = i / 4200
    const seed = hashText(`three-dust-${i}`)
    const arm = i % 2
    const spin = arm * Math.PI + t * Math.PI * 9.8 + (seed % 80) / 90
    const radius = 28 + Math.sqrt(t) * 780
    dustPositions.push(Math.cos(spin) * radius + ((seed % 100) - 50) * 0.8)
    dustPositions.push(Math.sin(spin * 1.3) * 16 + ((seed % 40) - 20) * 0.22)
    dustPositions.push(Math.sin(spin) * radius * 0.23 + ((hashText(`three-dust-z-${i}`) % 60) - 30))
    dustColors.push(i % 7 === 0 ? 1 : 0.58, i % 7 === 0 ? 0.9 : 0.72, i % 5 === 0 ? 0.84 : 1)
  }
  const dustGeometry = new THREE.BufferGeometry()
  dustGeometry.setAttribute('position', new THREE.Float32BufferAttribute(dustPositions, 3))
  dustGeometry.setAttribute('color', new THREE.Float32BufferAttribute(dustColors, 3))
  galaxyDustField = new THREE.Points(dustGeometry, new THREE.PointsMaterial({ size: 2.65, vertexColors: true, transparent: true, opacity: referenceTexture ? 0.28 : 0.42, blending: THREE.AdditiveBlending, depthWrite: false }))
  galaxyDustField.rotation.z = -0.25
  galaxyScene.add(galaxyDustField)

  galaxyTrackGroup = new THREE.Group()
  const trackColors = [0x91b9ff, 0xffd8a6, 0xc59cff, 0x72dcc8]
  for (let arm = 0; arm < 8; arm += 1) {
    const points: any[] = []
    const armOffset = arm * Math.PI * 0.5
    const inner = arm % 2 === 0 ? 36 : 58
    const outer = arm % 2 === 0 ? 760 : 680
    for (let i = 0; i < 210; i += 1) {
      const t = i / 209
      const spin = armOffset + t * Math.PI * (2.65 + (arm % 3) * 0.38)
      const radius = inner + Math.pow(t, 0.78) * outer
      const wave = Math.sin(t * Math.PI * 5 + arm) * (8 + arm * 0.8)
      points.push(new THREE.Vector3(
        Math.cos(spin) * (radius + wave),
        Math.sin(spin * 1.2) * (11 + arm * 0.8),
        Math.sin(spin) * (radius * 0.24 + wave * 0.35)
      ))
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(points)
    const material = new THREE.LineBasicMaterial({
      color: trackColors[arm % trackColors.length],
      transparent: true,
      opacity: arm % 2 === 0 ? 0.36 : 0.22,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const line = new THREE.Line(geometry, material)
    galaxyTrackGroup.add(line)
  }
  galaxyTrackGroup.rotation.z = -0.25
  galaxyScene.add(galaxyTrackGroup)

  const nebulaTexture = makeGlowTexture('rgba(207, 226, 241,0.12)', 'rgba(162, 199, 225,0.08)', 'rgba(0,0,0,0)', 256)
  for (let i = 0; i < 5; i += 1) {
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: nebulaTexture, transparent: true, opacity: referenceTexture ? 0.11 : 0.25, blending: THREE.AdditiveBlending, depthWrite: false }))
    const seed = hashText(`three-nebula-${i}`)
    sprite.position.set(((seed % 1000) / 1000 - 0.5) * 820, ((hashText(`n-y-${i}`) % 1000) / 1000 - 0.5) * 330, -150 + i * 48)
    const nebulaW = 320 + (seed % 220)
    const nebulaH = 145 + (seed % 120)
    sprite.scale.set(nebulaW, nebulaH, 1)
    sprite.userData = { baseX: sprite.position.x, baseY: sprite.position.y, baseScaleX: nebulaW, baseScaleY: nebulaH, type: 'inner-nebula' }
    galaxyNebulae.push(sprite)
    galaxyScene.add(sprite)
  }

  galaxyCore = new THREE.Group()
  const coreTexture = makeGlowTexture('rgba(255,255,255,0.96)', 'rgba(252, 239, 213,0.34)', 'rgba(207, 226, 241,0)', 256)
  const coreBloomTexture = makeGlowTexture('rgba(252, 239, 213,0.42)', 'rgba(207, 226, 241,0.14)', 'rgba(0,0,0,0)', 256)
  const coreMistTexture = makeGlowTexture('rgba(236, 244, 250,0.2)', 'rgba(162, 199, 225,0.1)', 'rgba(0,0,0,0)', 256)
  const coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: coreTexture, transparent: true, opacity: referenceTexture ? 0.62 : 0.8, blending: THREE.AdditiveBlending, depthWrite: false }))
  coreGlow.scale.set(260, 220, 1)
  const coreBloom = new THREE.Sprite(new THREE.SpriteMaterial({ map: coreBloomTexture, transparent: true, opacity: referenceTexture ? 0.5 : 0.66, blending: THREE.AdditiveBlending, depthWrite: false }))
  coreBloom.scale.set(470, 360, 1)
  const coreMist = new THREE.Sprite(new THREE.SpriteMaterial({ map: coreMistTexture, transparent: true, opacity: 0.34, blending: THREE.AdditiveBlending, depthWrite: false }))
  coreMist.scale.set(640, 430, 1)
  galaxyCore.add(coreMist, coreBloom, coreGlow)
  galaxyScene.add(galaxyCore)

  galaxyLinkGroup = new THREE.Group()
  galaxyNodeGroup = new THREE.Group()
  galaxyScene.add(galaxyLinkGroup, galaxyNodeGroup)
  const nodeMap = new Map<string, any>()
  for (const node of galaxyCtx.nodes()) {
    const active = activeTag.value === node.tag
    const related = activeTag.value && node.isRelated
    const texture = makeGlowTexture(
      active ? 'rgba(183, 225, 212,1)' : related ? 'rgba(183, 225, 212,0.98)' : `hsla(${node.hue},100%,68%,0.96)`,
      active ? 'rgba(183, 225, 212,0.68)' : related ? 'rgba(183, 225, 212,0.58)' : `hsla(${node.hue},100%,58%,0.5)`,
      active ? 'rgba(119, 194, 174,0)' : related ? 'rgba(119, 194, 174,0)' : `hsla(${node.hue},100%,54%,0)`,
      128
    )
    const star = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: active ? 1 : related ? 0.78 : 0.5 }))
    star.scale.set(active ? 48 : related ? 36 : 24, active ? 48 : related ? 36 : 24, 1)
    star.userData = { tag: node.tag, node }
    const label = new THREE.Sprite(new THREE.SpriteMaterial({ map: makeLabelTexture(node.tag, `${node.count}题`), transparent: true, depthWrite: false, opacity: active ? 0.82 : related ? 0.56 : 0.16 }))
    label.position.y = active ? -36 : -30
    label.scale.set(active ? 84 : 68, active ? 30 : 24, 1)
    const group = new THREE.Group()
    group.add(star, label)
    group.userData = { tag: node.tag, node, star, label }
    galaxyNodeGroup.add(group)
    galaxyNodeMeshes.push(group)
    nodeMap.set(node.tag, group)
  }

  galaxyMasteredGroup = new THREE.Group()
  masteredStars.value.forEach((item: any, index: number) => {
    const seed = hashText(`${item.id || item.tag}-${index}`)
    const hue = Number(item.hue ?? (38 + seed % 270))
    const masteredTexture = makeGlowTexture(`hsla(${hue},100%,72%,1)`, `hsla(${hue + 22},100%,58%,0.76)`, `hsla(${hue + 46},100%,48%,0)`, 128)
    const angle = (seed % 628) / 100
    const radius = 120 + (seed % 520)
    const y = ((hashText(`mastered-y-${item.id || index}`) % 1000) / 1000 - 0.5) * 250
    const star = new THREE.Sprite(new THREE.SpriteMaterial({
      map: masteredTexture,
      transparent: true,
      opacity: 0.96,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }))
    const size = 18 + (seed % 16)
    star.position.set(Math.cos(angle) * radius, y, Math.sin(angle) * radius * 0.34)
    star.scale.set(size, size, 1)
    star.userData = { baseSize: size, phase: angle, type: 'mastered-star' }
    galaxyMasteredGroup.add(star)
  })
  galaxyMasteredGroup.rotation.z = -0.25
  galaxyScene.add(galaxyMasteredGroup)

  for (const link of galaxyCtx.links()) {
    const a = nodeMap.get(link.source)
    const b = nodeMap.get(link.target)
    if (!a || !b) continue
    const selectedLink = activeTag.value && (link.source === activeTag.value || link.target === activeTag.value)
    const geometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()])
    const material = new THREE.LineBasicMaterial({ color: selectedLink ? 0xd8f2ff : 0x6ca8ff, transparent: true, opacity: selectedLink ? 0.56 : activeTag.value ? 0.12 : 0.28, blending: THREE.AdditiveBlending })
    const line = new THREE.Line(geometry, material)
    line.userData = { source: a, target: b, link }
    galaxyLinkGroup.add(line)
    galaxyLinkMeshes.push(line)
  }
  galaxyNeedsRebuild = false
}

function updateThreeNodePosition(group: any, time: number) {
  const node = group.userData.node
  let x = node.x
  let y = node.y
  let z = node.z
  if (node.focusMode) {
    if (node.isCenter) {
      x = Math.sin(time * 1.5) * 5
      y = Math.cos(time * 1.1) * 4
      z = Math.cos(time * 1.3) * 5
    } else {
      const phase = node.orbitPhase + time * (node.orbitSpeed || 0.25)
      x = Math.cos(phase) * node.orbitRadius
      z = Math.sin(phase) * node.orbitRadius
      y = node.y * 0.58 + Math.sin(phase * 1.7 + time) * (node.isRelated ? 18 : 34)
    }
  }
  group.position.set(x, y, z)
}

function refreshGalaxyFocusState() {
  if (!galaxyNodeGroup || !galaxyLinkGroup) return false
  const nodeLookup = new Map(galaxyCtx.nodes().map((node: any) => [node.tag, node]))
  galaxyNodeGroup.children.forEach((group: any) => {
    const node = nodeLookup.get(group.userData.tag) || group.userData.node
    const active = activeTag.value === group.userData.tag
    const related = Boolean(activeTag.value && node?.isRelated)
    group.userData.node = node
    group.visible = true
    const star = group.userData.star
    const label = group.userData.label
    if (star) {
      star.visible = true
      star.material.opacity = active ? 1 : related ? 0.78 : activeTag.value ? 0.42 : 0.5
      star.scale.set(active ? 52 : related ? 40 : 28, active ? 52 : related ? 40 : 28, 1)
    }
    if (label) {
      label.visible = true
      label.material.opacity = active ? 0.88 : related ? 0.62 : activeTag.value ? 0.22 : 0.32
      label.position.y = active ? -38 : -31
      label.scale.set(active ? 88 : related ? 74 : 64, active ? 32 : related ? 26 : 22, 1)
    }
  })
  for (const line of galaxyLinkMeshes) {
    const link = line.userData.link
    const selectedLink = activeTag.value && (link.source === activeTag.value || link.target === activeTag.value)
    line.visible = true
    line.material.color.set(selectedLink ? 0xd8f2ff : 0x7fb4ff)
    line.material.opacity = selectedLink ? 0.62 : activeTag.value ? 0.18 : 0.32
  }
  return true
}

function animateTagGalaxy() {
  if (!ensureTagGalaxyRenderer() || !galaxyRenderer || !galaxyScene || !galaxyCamera || !galaxyCtx.isActive()) return
  const time = galaxyAngle.value
  galaxyAngle.value += 0.006
  galaxyMouse.x += (galaxyMouse.targetX - galaxyMouse.x) * 0.08
  galaxyMouse.y += (galaxyMouse.targetY - galaxyMouse.y) * 0.08
  const mouseDistance = Math.min(1, Math.hypot(galaxyMouse.x, galaxyMouse.y))
  const interactiveScale = 1 + mouseDistance * 0.14
  galaxyScene.rotation.y = Math.sin(time * 0.22) * 0.04 + galaxyMouse.x * 0.08
  galaxyScene.rotation.x = galaxyMouse.y * 0.035
  galaxyCamera.position.x = -galaxyMouse.x * 26
  galaxyCamera.position.y = galaxyMouse.y * 18
  galaxyCamera.position.z = 560 / Math.max(0.5, galaxyZoom.value * (1 + mouseDistance * 0.08))
  galaxyCamera.lookAt(galaxyMouse.x * 16, -galaxyMouse.y * 10, 0)
  if (galaxySkyDome) {
    galaxySkyDome.rotation.y = -0.22 + time * 0.012 + galaxyMouse.x * 0.018
    galaxySkyDome.rotation.x = 0.18 + Math.sin(time * 0.16) * 0.025 + galaxyMouse.y * 0.012
    galaxySkyDome.rotation.z = 0.12 + time * 0.006
  }
  galaxyAtmosphereLayers.forEach((layer, index) => {
    const depth = 1 + index * 0.22
    const driftX = Math.sin(time * (0.16 + index * 0.025) + index) * (22 + index * 8)
    const driftY = Math.cos(time * (0.13 + index * 0.02) + index) * (14 + index * 6)
    const pulse = 1 + Math.sin(time * (0.22 + index * 0.035) + index) * 0.035
    layer.position.x = layer.userData.baseX + driftX - galaxyMouse.x * 42 / depth
    layer.position.y = layer.userData.baseY + driftY + galaxyMouse.y * 30 / depth
    layer.position.z = layer.userData.baseZ + Math.sin(time * 0.12 + index) * 18
    layer.scale.set(layer.userData.baseScaleX * pulse, layer.userData.baseScaleY * pulse, 1)
    layer.rotation.z = layer.userData.rotate + time * (0.006 + index * 0.002) * (index % 2 ? -1 : 1)
    if (layer.material) layer.material.opacity = layer.userData.opacity + Math.sin(time * 0.28 + index) * 0.022
  })
  galaxyBackgroundSystems.forEach((system, index) => {
    const isGalaxy = system.userData.type === 'background-galaxy'
    const isBrightNebula = !isGalaxy && String(system.userData.key || '').includes('bright')
    const depth = Math.max(1, Math.abs(system.userData.baseZ || -1000) / 760)
    const driftX = Math.sin(time * (0.11 + index * 0.014) + index) * (isGalaxy ? 10 : isBrightNebula ? 36 : 28)
    const driftY = Math.cos(time * (0.09 + index * 0.012) + index) * (isGalaxy ? 7 : isBrightNebula ? 28 : 20)
    const pulse = 1 + Math.sin(time * (isGalaxy ? 0.18 : 0.24) + index) * (isGalaxy ? 0.018 : isBrightNebula ? 0.055 : 0.04)
    system.position.x = system.userData.baseX + driftX - galaxyMouse.x * (isGalaxy ? 20 : 34) / depth
    system.position.y = system.userData.baseY + driftY + galaxyMouse.y * (isGalaxy ? 14 : 26) / depth
    system.position.z = system.userData.baseZ + Math.sin(time * 0.08 + index) * (isGalaxy ? 10 : 22)
    system.scale.set(system.userData.baseScaleX * pulse, system.userData.baseScaleY * pulse, 1)
    if (system.material) {
      system.material.rotation = system.userData.rotate + time * system.userData.speed
      system.material.opacity = system.userData.opacity + Math.sin(time * 0.22 + index) * (isGalaxy ? 0.04 : isBrightNebula ? 0.06 : 0.036)
    }
  })
  if (galaxyDeepField) {
    galaxyDeepField.rotation.z = time * 0.01
    galaxyDeepField.rotation.y += 0.00045 + mouseDistance * 0.00025
    galaxyDeepField.rotation.x = Math.sin(time * 0.18) * 0.035 + galaxyMouse.y * 0.02
  }
  if (galaxyBackdrop) {
    galaxyBackdrop.rotation.z = -0.018 + time * 0.055 + galaxyMouse.x * 0.035
    galaxyBackdrop.rotation.x = galaxyMouse.y * 0.028
    galaxyBackdrop.rotation.y = -galaxyMouse.x * 0.036
    galaxyBackdrop.scale.setScalar(interactiveScale + Math.sin(time * 0.42) * 0.012)
    galaxyBackdrop.children.forEach((child: any, index: number) => {
      const photoLayer = child.userData.type === 'photo'
      const pulse = photoLayer ? 1 + Math.sin(time * 0.5) * 0.012 : 1 + Math.sin(time * 0.72 + index) * 0.025
      child.scale.set((child.userData.baseScaleX || child.scale.x) * pulse, (child.userData.baseScaleY || child.scale.y) * pulse, 1)
      if (child.material) {
        child.material.opacity = photoLayer
          ? 0.68 + Math.sin(time * 0.7) * 0.018
          : index === 1 ? 0.3 + Math.sin(time * 0.8) * 0.035 : 0.1 + Math.sin(time * 0.55 + index) * 0.024
      }
    })
  }
  if (galaxyStarField) {
    galaxyStarField.rotation.z = -time * 0.008
    galaxyStarField.rotation.y += 0.0011 + mouseDistance * 0.0004
    galaxyStarField.rotation.x = galaxyMouse.y * 0.025
  }
  if (galaxyDustField) {
    galaxyDustField.rotation.y += 0.0032 + mouseDistance * 0.001
    galaxyDustField.rotation.x = galaxyMouse.y * 0.035
    galaxyDustField.rotation.z = -0.25 + time * 0.085 + Math.sin(time * 0.4) * 0.018 + galaxyMouse.x * 0.05
  }
  if (galaxyTrackGroup) {
    galaxyTrackGroup.rotation.y = galaxyDustField?.rotation.y || 0
    galaxyTrackGroup.rotation.x = galaxyMouse.y * 0.034
    galaxyTrackGroup.rotation.z = -0.25 + time * 0.09 + Math.sin(time * 0.4) * 0.016 + galaxyMouse.x * 0.05
    galaxyTrackGroup.children.forEach((line: any, index: number) => {
      if (line.material) line.material.opacity = (index % 2 === 0 ? 0.34 : 0.2) + Math.sin(time * 0.7 + index) * 0.055
    })
  }
  if (galaxyMasteredGroup) {
    galaxyMasteredGroup.rotation.y = galaxyDustField?.rotation.y || 0
    galaxyMasteredGroup.rotation.x = galaxyMouse.y * 0.032
    galaxyMasteredGroup.rotation.z = -0.25 + time * 0.07 + galaxyMouse.x * 0.04
    galaxyMasteredGroup.children.forEach((star: any, index: number) => {
      const pulse = 1 + Math.sin(time * 1.8 + star.userData.phase + index) * 0.22
      const baseSize = star.userData.baseSize || 20
      star.scale.set(baseSize * pulse, baseSize * pulse, 1)
      if (star.material) star.material.opacity = 0.74 + Math.sin(time * 1.4 + index) * 0.22
    })
  }
  if (galaxyCore) {
    const pulse = 1 + mouseDistance * 0.08 + Math.sin(time * 2.4) * 0.045
    galaxyCore.scale.setScalar(pulse)
    galaxyCore.rotation.y += 0.01
    galaxyCore.rotation.z = time * 0.09
  }
  galaxyNebulae.forEach((sprite, index) => {
    const wide = sprite.userData.type === 'wide-nebula'
    const pulse = 1 + Math.sin(time * (wide ? 0.34 : 0.8) + index) * (wide ? 0.035 : 0.045)
    sprite.material.opacity = wide ? 0.1 + Math.sin(time * 0.38 + index) * 0.024 : 0.09 + Math.sin(time * 0.8 + index) * 0.026
    sprite.position.x = (sprite.userData.baseX || sprite.position.x) + Math.sin(time * 0.22 + index) * (wide ? 26 : 8)
    sprite.position.y = (sprite.userData.baseY || sprite.position.y) + Math.cos(time * 0.18 + index) * (wide ? 18 : 6)
    sprite.scale.set((sprite.userData.baseScaleX || sprite.scale.x) * pulse, (sprite.userData.baseScaleY || sprite.scale.y) * pulse, 1)
    sprite.rotation.z += (wide ? 0.00025 : 0.0009) * (index % 2 ? -1 : 1)
  })
  const projected: { tag: string; x: number; y: number; radius: number }[] = []
  galaxyNodeGroup?.children.forEach((group: any) => {
    updateThreeNodePosition(group, time)
    group.lookAt(galaxyCamera.position)
    const screen = group.position.clone().project(galaxyCamera)
    const rect = galaxyCanvas.value?.getBoundingClientRect()
    if (rect) projected.push({ tag: group.userData.tag, x: (screen.x * 0.5 + 0.5) * rect.width, y: (-screen.y * 0.5 + 0.5) * rect.height, radius: 24 })
  })
  galaxyTargets.value = projected
  for (const line of galaxyLinkMeshes) {
    line.geometry.setFromPoints([line.userData.source.position, line.userData.target.position])
    line.geometry.attributes.position.needsUpdate = true
  }
  galaxyRenderer.render(galaxyScene, galaxyCamera)
  if (!galaxyCtx.reducedMotion()) galaxyFrame = window.requestAnimationFrame(animateTagGalaxy)
}

function drawTagGalaxy() {
  const canvas = galaxyCanvas.value
  if (!canvas || !galaxyCtx.isActive()) return
  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  const width = Math.max(320, rect.width)
  const height = Math.max(280, rect.height)
  if (canvas.width !== Math.floor(width * dpr) || canvas.height !== Math.floor(height * dpr)) {
    canvas.width = Math.floor(width * dpr)
    canvas.height = Math.floor(height * dpr)
  }
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, width, height)

  ctx.fillStyle = '#2e4056'
  ctx.fillRect(0, 0, width, height)

  const nodes = galaxyCtx.nodes()
  const links = galaxyCtx.links()
  const angle = galaxyAngle.value
  galaxyAngle.value += 0.006
  const time = angle * 160
  const projected = new Map<string, any>()
  const centerX = width / 2
  const centerY = height / 2
  const camera = 430
  const zoom = galaxyZoom.value
  const scaleBase = Math.min(width, height) / 390 * zoom

  const skyGlow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, Math.max(width, height) * 0.65)
  skyGlow.addColorStop(0, 'rgba(106, 147, 184, 0.22)')
  skyGlow.addColorStop(0.45, 'rgba(46, 64, 86, 0.2)')
  skyGlow.addColorStop(1, 'rgba(0, 0, 0, 0)')
  ctx.fillStyle = skyGlow
  ctx.fillRect(0, 0, width, height)

  ctx.save()
  ctx.globalCompositeOperation = 'screen'
  const nebulaPalette = [
    ['rgba(162, 199, 225, 0.24)', 'rgba(162, 199, 225, 0)'],
    ['rgba(207, 226, 241, 0.18)', 'rgba(207, 226, 241, 0)'],
    ['rgba(162, 199, 225, 0.14)', 'rgba(162, 199, 225, 0)'],
    ['rgba(119, 194, 174, 0.12)', 'rgba(119, 194, 174, 0)'],
  ]
  for (let i = 0; i < 7; i += 1) {
    const seed = hashText(`nebula-${i}`)
    const drift = angle * (0.18 + (seed % 7) * 0.01)
    const x = centerX + Math.cos(seed * 0.017 + drift) * width * (0.16 + (seed % 23) / 190)
    const y = centerY + Math.sin(seed * 0.013 - drift * 0.7) * height * (0.12 + (seed % 19) / 210)
    const rx = width * (0.16 + (seed % 31) / 170)
    const ry = height * (0.06 + (seed % 29) / 260)
    const [inner, outer] = nebulaPalette[i % nebulaPalette.length]
    ctx.save()
    ctx.translate(x, y)
    ctx.rotate(-0.36 + (seed % 60) / 110)
    ctx.scale(1, ry / rx)
    const cloud = ctx.createRadialGradient(0, 0, 0, 0, 0, rx)
    cloud.addColorStop(0, inner)
    cloud.addColorStop(0.42, inner.replace('0.24', '0.11').replace('0.18', '0.09').replace('0.14', '0.07').replace('0.12', '0.06'))
    cloud.addColorStop(1, outer)
    ctx.fillStyle = cloud
    ctx.beginPath()
    ctx.arc(0, 0, rx, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }
  ctx.restore()

  for (let i = 0; i < 360; i += 1) {
    const seed = i * 7919
    const parallax = 0.35 + (hashText(`p${seed}`) % 100) / 150
    const x = ((hashText(`x${seed}`) % Math.floor(width)) + Math.sin(time * 0.01 + seed) * parallax * 16 + time * 0.018 * parallax + width) % width
    const y = ((hashText(`y${seed}`) % Math.floor(height)) + Math.cos(time * 0.007 + seed) * parallax * 10 + height) % height
    const bright = hashText(`b${seed}`) % 100
    const r = bright > 94 ? 1.6 : bright > 82 ? 1.05 : 0.45 + (bright % 7) / 12
    const twinkle = 0.55 + Math.sin(time * 0.035 + seed) * 0.32
    ctx.fillStyle = bright > 88
      ? `rgba(255, 255, 255, ${0.62 + twinkle * 0.34})`
      : `rgba(187, 218, 255, ${0.12 + twinkle * 0.2 + (bright % 20) / 160})`
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fill()
    if (bright > 96) {
      ctx.strokeStyle = 'rgba(236, 244, 250, 0.32)'
      ctx.lineWidth = 0.7
      ctx.beginPath()
      ctx.moveTo(x - r * 3, y)
      ctx.lineTo(x + r * 3, y)
      ctx.moveTo(x, y - r * 3)
      ctx.lineTo(x, y + r * 3)
      ctx.stroke()
    }
  }

  ctx.save()
  ctx.globalCompositeOperation = 'screen'
  for (let layer = 0; layer < 3; layer += 1) {
    const count = layer === 0 ? 70 : layer === 1 ? 48 : 28
    const speed = 0.18 + layer * 0.22
    for (let i = 0; i < count; i += 1) {
      const seed = hashText(`field-${layer}-${i}`)
      const baseX = seed % Math.floor(width)
      const baseY = hashText(`field-y-${layer}-${i}`) % Math.floor(height)
      const driftX = (time * speed + seed * 0.017) % (width + 80)
      const driftY = Math.sin(time * 0.01 + seed) * (4 + layer * 5)
      const x = (baseX + driftX) % (width + 80) - 40
      const y = baseY + driftY
      const alpha = 0.08 + layer * 0.045 + ((seed % 30) / 300)
      const size = 0.7 + layer * 0.5 + (seed % 8) / 12
      const trail = 10 + layer * 9 + (seed % 12)
      const particle = ctx.createLinearGradient(x - trail, y + trail * 0.22, x, y)
      particle.addColorStop(0, 'rgba(207, 226, 241, 0)')
      particle.addColorStop(1, `rgba(210, 235, 255, ${alpha})`)
      ctx.strokeStyle = particle
      ctx.lineWidth = size
      ctx.beginPath()
      ctx.moveTo(x - trail, y + trail * 0.22)
      ctx.lineTo(x, y)
      ctx.stroke()
    }
  }
  for (let i = 0; i < 4; i += 1) {
    const seed = hashText(`meteor-${i}`)
    const cycle = ((time * (0.18 + i * 0.04) + seed) % 520) / 520
    if (cycle > 0.72) {
      const p = (cycle - 0.72) / 0.28
      const x = width * (0.08 + (seed % 70) / 100) + p * width * 0.32
      const y = height * (0.12 + (seed % 48) / 120) + p * height * 0.18
      const length = 80 + (seed % 70)
      const alpha = Math.sin(p * Math.PI) * 0.42
      const meteor = ctx.createLinearGradient(x - length, y + length * 0.28, x, y)
      meteor.addColorStop(0, 'rgba(255,255,255,0)')
      meteor.addColorStop(0.72, `rgba(140, 200, 255, ${alpha * 0.55})`)
      meteor.addColorStop(1, `rgba(255, 255, 255, ${alpha})`)
      ctx.strokeStyle = meteor
      ctx.lineWidth = 1.4
      ctx.beginPath()
      ctx.moveTo(x - length, y + length * 0.28)
      ctx.lineTo(x, y)
      ctx.stroke()
    }
  }
  ctx.restore()

  const galaxyTilt = -0.34
  const galaxyMajor = Math.min(width, height) * 0.68 * zoom
  const galaxyMinor = galaxyMajor * 0.3
  ctx.save()
  ctx.translate(centerX, centerY + height * 0.02)
  ctx.rotate(galaxyTilt)
  const disk = ctx.createRadialGradient(0, 0, 0, 0, 0, galaxyMajor)
  disk.addColorStop(0, 'rgba(252, 239, 213, 0.92)')
  disk.addColorStop(0.12, 'rgba(251, 227, 233, 0.62)')
  disk.addColorStop(0.28, 'rgba(207, 226, 241, 0.35)')
  disk.addColorStop(0.58, 'rgba(106, 147, 184, 0.22)')
  disk.addColorStop(1, 'rgba(46, 64, 86, 0)')
  ctx.scale(1, galaxyMinor / galaxyMajor)
  ctx.fillStyle = disk
  ctx.beginPath()
  ctx.arc(0, 0, galaxyMajor, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()

  ctx.save()
  ctx.translate(centerX, centerY + height * 0.02)
  ctx.rotate(galaxyTilt)
  for (let arm = 0; arm < 2; arm += 1) {
    for (let i = 0; i < 620; i += 1) {
      const t = i / 620
      const spin = arm * Math.PI + t * Math.PI * 5.9 + angle * 0.42
      const spread = ((hashText(`arm-${arm}-${i}`) % 100) - 50) / 100
      const radius = 18 + t * galaxyMajor * 1.08
      const x = Math.cos(spin) * radius + spread * 40
      const y = (Math.sin(spin) * radius * 0.24) + spread * 14
      const alpha = Math.max(0, 0.34 * (1 - t))
      const size = 0.45 + (hashText(`arm-size-${arm}-${i}`) % 16) / 10
      ctx.fillStyle = i % 5 === 0 ? `rgba(255, 244, 225, ${alpha})` : `rgba(166, 207, 255, ${alpha})`
      ctx.beginPath()
      ctx.arc(x, y, size, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  ctx.filter = 'blur(9px)'
  const core = ctx.createRadialGradient(-8, -6, 0, 0, 0, 170)
  core.addColorStop(0, 'rgba(255, 255, 255, 1)')
  core.addColorStop(0.18, 'rgba(254, 249, 238, 0.98)')
  core.addColorStop(0.4, 'rgba(252, 239, 213, 0.68)')
  core.addColorStop(0.66, 'rgba(207, 226, 241, 0.34)')
  core.addColorStop(1, 'rgba(255, 255, 255, 0)')
  ctx.fillStyle = core
  ctx.beginPath()
  ctx.ellipse(0, 0, 176, 86, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.globalCompositeOperation = 'screen'
  const coreDepth = ctx.createRadialGradient(-26, -20, 0, 0, 0, 128)
  coreDepth.addColorStop(0, 'rgba(255, 255, 255, 0.95)')
  coreDepth.addColorStop(0.28, 'rgba(252, 239, 213, 0.58)')
  coreDepth.addColorStop(0.62, 'rgba(207, 226, 241, 0.22)')
  coreDepth.addColorStop(1, 'rgba(255, 255, 255, 0)')
  ctx.fillStyle = coreDepth
  ctx.beginPath()
  ctx.arc(0, 0, 112, 0, Math.PI * 2)
  ctx.fill()
  const dreamHaze = ctx.createRadialGradient(0, 0, 0, 0, 0, 220)
  dreamHaze.addColorStop(0, 'rgba(255, 255, 255, 0.6)')
  dreamHaze.addColorStop(0.28, 'rgba(207, 226, 241, 0.26)')
  dreamHaze.addColorStop(0.62, 'rgba(162, 199, 225, 0.18)')
  dreamHaze.addColorStop(1, 'rgba(255, 255, 255, 0)')
  ctx.fillStyle = dreamHaze
  ctx.beginPath()
  ctx.ellipse(0, 0, 260, 110, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.filter = 'blur(16px)'
  const hotCore = ctx.createRadialGradient(-10, -8, 0, 0, 0, 82)
  hotCore.addColorStop(0, 'rgba(255, 255, 255, 1)')
  hotCore.addColorStop(0.52, 'rgba(254, 249, 238, 0.92)')
  hotCore.addColorStop(1, 'rgba(252, 239, 213, 0)')
  ctx.fillStyle = hotCore
  ctx.beginPath()
  ctx.arc(0, 0, 76, 0, Math.PI * 2)
  ctx.fill()
  ctx.filter = 'none'
  ctx.globalCompositeOperation = 'source-over'
  ctx.restore()

  ctx.save()
  ctx.globalCompositeOperation = 'lighter'
  ctx.translate(centerX, centerY + height * 0.02)
  ctx.rotate(galaxyTilt)
  for (let i = 0; i < 220; i += 1) {
    const seed = hashText(`dust-${i}`)
    const t = (seed % 1000) / 1000
    const orbit = Math.sqrt(t) * galaxyMajor * 1.1
    const spin = (seed % 628) / 100 + angle * (0.38 + (seed % 17) / 90)
    const wobble = Math.sin(angle * 2.1 + seed) * 7
    const x = Math.cos(spin) * orbit
    const y = Math.sin(spin) * orbit * 0.2 + wobble
    const size = 0.55 + (seed % 12) / 9
    const alpha = 0.12 + (1 - t) * 0.28
    ctx.fillStyle = i % 6 === 0 ? `rgba(255, 241, 210, ${alpha})` : `rgba(166, 213, 255, ${alpha})`
    ctx.beginPath()
    ctx.arc(x, y, size, 0, Math.PI * 2)
    ctx.fill()
    if (i % 11 === 0) {
      ctx.strokeStyle = `rgba(160, 208, 255, ${alpha * 0.24})`
      ctx.lineWidth = 0.7
      ctx.beginPath()
      ctx.moveTo(x - Math.sin(spin) * 9, y + Math.cos(spin) * 2)
      ctx.lineTo(x + Math.sin(spin) * 9, y - Math.cos(spin) * 2)
      ctx.stroke()
    }
  }
  ctx.restore()

  const edgeBlend = ctx.createRadialGradient(centerX, centerY, Math.min(width, height) * 0.22, centerX, centerY, Math.max(width, height) * 0.72)
  edgeBlend.addColorStop(0, 'rgba(0, 0, 0, 0)')
  edgeBlend.addColorStop(0.7, 'rgba(46, 64, 86, 0.18)')
  edgeBlend.addColorStop(1, 'rgba(46, 64, 86, 0.78)')
  ctx.fillStyle = edgeBlend
  ctx.fillRect(0, 0, width, height)
  const topMist = ctx.createLinearGradient(0, 0, 0, height)
  topMist.addColorStop(0, 'rgba(106, 147, 184, 0.16)')
  topMist.addColorStop(0.18, 'rgba(46, 64, 86, 0.08)')
  topMist.addColorStop(0.78, 'rgba(0, 0, 0, 0)')
  topMist.addColorStop(1, 'rgba(46, 64, 86, 0.32)')
  ctx.fillStyle = topMist
  ctx.fillRect(0, 0, width, height)

  const rotate = (node: any) => {
    const cos = Math.cos(angle)
    const sin = Math.sin(angle)
    let sourceX = node.x
    let sourceY = node.y
    let sourceZ = node.z
    if (node.focusMode) {
      if (node.isCenter) {
        sourceX = Math.sin(angle * 1.5) * 4
        sourceY = Math.cos(angle * 1.1) * 3
        sourceZ = Math.cos(angle * 1.3) * 4
      } else {
        const phase = node.orbitPhase + angle * (node.orbitSpeed || 0.25)
        const wave = Math.sin(phase * 1.7 + angle) * (node.isRelated ? 18 : 34)
        sourceX = Math.cos(phase) * node.orbitRadius
        sourceZ = Math.sin(phase) * node.orbitRadius
        sourceY = node.y * 0.58 + wave
      }
    }
    const x = sourceX * cos - sourceZ * sin
    const z = sourceX * sin + sourceZ * cos
    const perspective = camera / (camera + z * zoom + 150)
    return {
      ...node,
      px: centerX + x * perspective * scaleBase,
      py: centerY + node.y * perspective * scaleBase,
      pz: z,
      perspective,
    }
  }

  for (const node of nodes) projected.set(node.tag, rotate(node))

  for (const link of links) {
    const a = projected.get(link.source)
    const b = projected.get(link.target)
    if (!a || !b) continue
    const selectedLink = activeTag.value && (link.source === activeTag.value || link.target === activeTag.value)
    const dimUnrelated = activeTag.value && !selectedLink
    const alpha = dimUnrelated
      ? Math.min(0.12, 0.035 + Number(link.weight || 1) * 0.018)
      : Math.min(0.58, 0.14 + Number(link.weight || 1) * 0.065)
    const beam = ctx.createLinearGradient(a.px, a.py, b.px, b.py)
    beam.addColorStop(0, `rgba(180, 220, 255, ${alpha})`)
    beam.addColorStop(0.5, `rgba(255, 255, 255, ${alpha * 0.72})`)
    beam.addColorStop(1, `rgba(115, 179, 255, ${alpha})`)
    ctx.strokeStyle = beam
    ctx.lineWidth = Math.max(0.8, Math.min(4.2, link.weight)) * ((a.perspective + b.perspective) / 2) * (selectedLink ? 1.28 : 1)
    ctx.shadowColor = selectedLink ? 'rgba(223, 242, 235, 0.42)' : 'rgba(207, 226, 241, 0.2)'
    ctx.shadowBlur = selectedLink ? 14 : 7
    ctx.beginPath()
    ctx.moveTo(a.px, a.py)
    ctx.lineTo(b.px, b.py)
    ctx.stroke()
    ctx.shadowBlur = 0
  }

  const targets: { tag: string; x: number; y: number; radius: number }[] = []
  Array.from(projected.values()).sort((a, b) => a.pz - b.pz).forEach((node: any) => {
    const active = activeTag.value === node.tag
    const related = Boolean(activeTag.value && node.isRelated)
    const unrelated = Boolean(activeTag.value && !active && !related)
    const pulse = 0.86 + Math.sin(time * 0.026 + hashText(node.tag)) * 0.14
    const radius = (7 + Math.min(12, node.count * 2.4)) * node.perspective * (active ? 1.42 : related ? 1.16 : 0.9) * pulse
    const haloRadius = radius * (active ? 2.8 : 2.25)
    const star = ctx.createRadialGradient(node.px, node.py, 0, node.px, node.py, haloRadius)
    star.addColorStop(0, '#ffffff')
    star.addColorStop(0.12, active ? 'rgba(254, 249, 238,0.98)' : related ? 'rgba(248, 251, 253,0.92)' : 'rgba(248, 251, 253,0.62)')
    star.addColorStop(0.42, active ? 'rgba(183, 225, 212, 0.42)' : related ? `hsla(${node.hue}, 90%, 66%, 0.34)` : `hsla(${node.hue}, 70%, 62%, 0.16)`)
    star.addColorStop(1, 'rgba(255, 255, 255, 0)')
    ctx.shadowColor = active ? 'rgba(183, 225, 212, 0.52)' : 'rgba(207, 226, 241, 0.28)'
    ctx.shadowBlur = active ? 18 : 10
    ctx.fillStyle = star
    ctx.beginPath()
    ctx.arc(node.px, node.py, haloRadius, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = active ? 'rgba(243, 250, 247, 0.92)' : 'rgba(236, 244, 250, 0.78)'
    ctx.beginPath()
    ctx.arc(node.px, node.py, Math.max(1.2, radius * 0.24), 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = active ? 'rgba(223, 242, 235, 0.34)' : 'rgba(236, 244, 250, 0.2)'
    ctx.lineWidth = 0.7
    ctx.beginPath()
    ctx.moveTo(node.px - radius * 1.15, node.py)
    ctx.lineTo(node.px + radius * 1.15, node.py)
    ctx.moveTo(node.px, node.py - radius * 1.15)
    ctx.lineTo(node.px, node.py + radius * 1.15)
    ctx.stroke()
    ctx.shadowBlur = 0
    ctx.globalAlpha = unrelated ? 0.46 : 1
    ctx.fillStyle = active ? 'rgba(255,255,255,0.94)' : related ? 'rgba(248, 251, 253, 0.82)' : 'rgba(236, 244, 250, 0.56)'
    ctx.font = `${Math.max(11, 12 * node.perspective)}px system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.shadowColor = 'rgba(0, 0, 0, 0.82)'
    ctx.shadowBlur = 5
    ctx.fillText(node.tag, node.px, node.py + radius + 15)
    ctx.fillStyle = active ? '#dff2eb' : 'rgba(236, 244, 250, 0.88)'
    ctx.font = `${Math.max(9, 10 * node.perspective)}px system-ui, sans-serif`
    ctx.fillText(`${node.count}题`, node.px, node.py + radius + 28)
    ctx.globalAlpha = 1
    ctx.shadowBlur = 0
    targets.push({ tag: node.tag, x: node.px, y: node.py, radius: radius + 18 })
  })
  galaxyTargets.value = targets
  galaxyFrame = window.requestAnimationFrame(drawTagGalaxy)
}

function onGalaxyClick(event: MouseEvent) {
  const rect = galaxyCanvas.value?.getBoundingClientRect()
  if (!rect) return
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const target = galaxyTargets.value.find((item) => Math.hypot(item.x - x, item.y - y) <= item.radius)
  if (target) activeTag.value = target.tag
}

function onGalaxyPointerMove(event: MouseEvent) {
  const rect = galaxyCanvas.value?.getBoundingClientRect()
  if (!rect) return
  galaxyMouse.active = true
  galaxyMouse.targetX = Math.max(-1, Math.min(1, ((event.clientX - rect.left) / rect.width - 0.5) * 2))
  galaxyMouse.targetY = Math.max(-1, Math.min(1, ((event.clientY - rect.top) / rect.height - 0.5) * 2))
}

function onGalaxyPointerLeave() {
  galaxyMouse.active = false
  galaxyMouse.targetX = 0
  galaxyMouse.targetY = 0
}

function onGalaxyWheel(event: WheelEvent) {
  const nextZoom = galaxyZoom.value + (event.deltaY > 0 ? -0.08 : 0.08)
  galaxyZoom.value = Math.max(0.62, Math.min(1.9, Number(nextZoom.toFixed(2))))
}

function onGalaxyKeydown(event: KeyboardEvent) {
  if (event.key === '+' || event.key === '=') {
    event.preventDefault()
    galaxyZoom.value = Math.min(1.9, Number((galaxyZoom.value + 0.08).toFixed(2)))
    return
  }
  if (event.key === '-' || event.key === '_') {
    event.preventDefault()
    galaxyZoom.value = Math.max(0.62, Number((galaxyZoom.value - 0.08).toFixed(2)))
    return
  }
  if (event.key === '0') {
    event.preventDefault()
    galaxyZoom.value = 1
    return
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    activeTag.value = ''
    galaxyMouse.active = false
    galaxyCanvas.value?.blur()
    return
  }
  const tags = galaxyCtx.nodes().map((node: any) => String(node.tag))
  if (!tags.length) return
  const currentIndex = Math.max(0, tags.indexOf(activeTag.value))
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    event.preventDefault()
    activeTag.value = tags[(currentIndex + 1) % tags.length]
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    event.preventDefault()
    activeTag.value = tags[(currentIndex - 1 + tags.length) % tags.length]
  } else if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    activeTag.value = tags[currentIndex]
  }
}

  /** 刷新数据后重置引擎（version=true 时强制重建场景） */
  function resetGalaxyScene({ version = false } = {}) {
    if (version) galaxyRefreshVersion += 1
    galaxySceneSignature = ''
    galaxyNeedsRebuild = true
    galaxyAngle.value = 0
    galaxyZoom.value = 1
    Object.assign(galaxyMouse, { x: 0, y: 0, targetX: 0, targetY: 0, active: false })
  }

  function markNeedsRebuild() {
    galaxyNeedsRebuild = true
  }

  function clearSignature() {
    galaxySceneSignature = ''
  }

  /** 页面卸载时用：停帧、清场景、连渲染器一起释放（WebGL 上下文不释放会泄漏） */
  function disposeEngine() {
    stopTagGalaxy()
    disposeTagGalaxyScene()
    galaxyRenderer?.dispose?.()
    galaxyRenderer = null
  }

  return {
    targets: galaxyTargets,
    start: startTagGalaxy,
    stop: stopTagGalaxy,
    dispose: disposeEngine,
    refreshFocus: refreshGalaxyFocusState,
    requestReferenceTexture: requestReferenceGalaxyTexture,
    resetGalaxyScene,
    markNeedsRebuild,
    clearSignature,
    onGalaxyClick,
    onGalaxyPointerMove,
    onGalaxyPointerLeave,
    onGalaxyWheel,
    onGalaxyKeydown,
  }
}

export type TagGalaxyEngine = ReturnType<typeof createTagGalaxyScene>
