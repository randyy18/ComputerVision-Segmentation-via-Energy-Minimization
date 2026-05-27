<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import type { Bbox } from '@/api/client'

const props = defineProps<{
  imageUrl: string
  bbox: Bbox | null
}>()

const emit = defineEmits<{
  bboxChange: [bbox: Bbox | null]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const image = ref<HTMLImageElement | null>(null)
const drawing = ref(false)
const start = ref<{ x: number; y: number } | null>(null)
const current = ref<{ x: number; y: number } | null>(null)

let scale = 1
let imgW = 0
let imgH = 0

function loadImage(url: string) {
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    image.value = img
    imgW = img.naturalWidth
    imgH = img.naturalHeight
    resizeCanvas()
    redraw()
  }
  img.src = url
}

function resizeCanvas() {
  const canvas = canvasRef.value
  const container = containerRef.value
  if (!canvas || !container || !image.value) return

  const maxW = container.clientWidth
  const maxH = Math.min(520, window.innerHeight * 0.55)
  scale = Math.min(maxW / imgW, maxH / imgH, 1)
  const cw = Math.round(imgW * scale)
  const ch = Math.round(imgH * scale)
  canvas.width = cw
  canvas.height = ch
  redraw()
}

function canvasToImage(x: number, y: number): { x: number; y: number } {
  return {
    x: Math.round(x / scale),
    y: Math.round(y / scale),
  }
}

function normalizeBbox(a: { x: number; y: number }, b: { x: number; y: number }): Bbox {
  const x1 = Math.max(0, Math.min(a.x, b.x))
  const y1 = Math.max(0, Math.min(a.y, b.y))
  const x2 = Math.min(imgW, Math.max(a.x, b.x))
  const y2 = Math.min(imgH, Math.max(a.y, b.y))
  return { x1, y1, x2, y2 }
}

function redraw() {
  const canvas = canvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!canvas || !ctx || !image.value) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(image.value, 0, 0, canvas.width, canvas.height)

  const drawRect = (b: Bbox, color: string, lineW: number) => {
    ctx.strokeStyle = color
    ctx.lineWidth = lineW
    ctx.strokeRect(b.x1 * scale, b.y1 * scale, (b.x2 - b.x1) * scale, (b.y2 - b.y1) * scale)
  }

  if (props.bbox) {
    drawRect(props.bbox, '#4ade80', 2)
  }

  if (drawing.value && start.value && current.value) {
    const live = normalizeBbox(start.value, current.value)
    drawRect(live, '#4ade80', 2)
  }
}

function onPointerDown(e: PointerEvent) {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  drawing.value = true
  start.value = canvasToImage(x, y)
  current.value = start.value
  canvas.setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (!drawing.value) return
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  current.value = canvasToImage(e.clientX - rect.left, e.clientY - rect.top)
  redraw()
}

function onPointerUp(e: PointerEvent) {
  if (!drawing.value || !start.value || !current.value) return
  drawing.value = false
  const bbox = normalizeBbox(start.value, current.value)
  if (bbox.x2 - bbox.x1 >= 2 && bbox.y2 - bbox.y1 >= 2) {
    emit('bboxChange', bbox)
  }
  start.value = null
  current.value = null
  canvasRef.value?.releasePointerCapture(e.pointerId)
  redraw()
}

watch(
  () => props.imageUrl,
  (url) => loadImage(url),
  { immediate: true },
)

watch(
  () => props.bbox,
  () => redraw(),
)

watch(image, () => redraw())

onMounted(() => {
  window.addEventListener('resize', resizeCanvas)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCanvas)
})
</script>

<template>
  <div ref="containerRef" class="bbox-canvas-wrap">
    <canvas
      ref="canvasRef"
      class="bbox-canvas"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
    />
    <p class="bbox-hint">Click and drag to draw a box around the object</p>
  </div>
</template>

<style scoped>
.bbox-canvas-wrap {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.bbox-canvas {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: crosshair;
  touch-action: none;
  max-width: 100%;
}

.bbox-hint {
  margin: 0.75rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}
</style>
