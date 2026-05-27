<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BboxCanvas from '@/components/BboxCanvas.vue'
import GameTimer from '@/components/GameTimer.vue'
import ImageStrip from '@/components/ImageStrip.vue'
import { imageUrl, setBbox } from '@/api/client'
import type { Bbox } from '@/api/client'
import { useGameStore } from '@/stores/gameStore'

const store = useGameStore()
const router = useRouter()
const timerRunning = ref(true)
const finishing = ref(false)
let intervalId: ReturnType<typeof setInterval> | null = null

const currentUrl = computed(() =>
  store.sessionId ? imageUrl(store.sessionId, store.currentIndex) : '',
)

const currentStem = computed(() => store.stems[store.currentIndex] ?? '')

const bboxCount = computed(() => store.bboxes.filter((b) => b !== null).length)

function startTimer() {
  stopTimer()
  timerRunning.value = true
  intervalId = setInterval(async () => {
    if (!timerRunning.value) return
    store.tickTimer()
    if (store.timeRemaining <= 0) {
      timerRunning.value = false
      stopTimer()
      await handleFinish()
    }
  }, 1000)
}

function stopTimer() {
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
}

async function saveBbox(bbox: Bbox | null) {
  store.setLocalBbox(store.currentIndex, bbox)
  if (bbox && store.sessionId) {
    try {
      await setBbox(store.sessionId, store.currentIndex, bbox)
    } catch {
      /* keep local copy */
    }
  }
}

function goPrev() {
  if (store.currentIndex > 0) store.currentIndex -= 1
}

function goNext() {
  if (store.currentIndex < store.imageCount - 1) store.currentIndex += 1
}

function selectIndex(i: number) {
  store.currentIndex = i
}

async function handleFinish() {
  if (finishing.value) return
  finishing.value = true
  timerRunning.value = false
  stopTimer()
  router.push('/processing')
  await store.runFinish()
  if (store.phase === 'results') router.push('/results')
  else router.push('/game')
  finishing.value = false
}

onMounted(() => {
  if (!store.sessionId || store.phase !== 'game') {
    router.replace('/')
    return
  }
  startTimer()
})

onUnmounted(stopTimer)

watch(
  () => store.phase,
  (p) => {
    if (p === 'processing') router.push('/processing')
  },
)
</script>

<template>
  <main class="page game-page">
    <div class="game-header">
      <div>
        <h1 class="page-title game-title">{{ currentStem }}</h1>
        <p class="game-progress">
          Image {{ store.currentIndex + 1 }} / {{ store.imageCount }} ·
          {{ bboxCount }} boxed
        </p>
      </div>
      <GameTimer
        :remaining="store.timeRemaining"
        :total="store.timeLimitSec"
        :running="timerRunning"
      />
    </div>

    <ImageStrip
      :stems="store.stems"
      :current-index="store.currentIndex"
      :bboxes="store.bboxes"
      @select="selectIndex"
    />

    <BboxCanvas
      :key="currentUrl"
      :image-url="currentUrl"
      :bbox="store.bboxes[store.currentIndex]"
      @bbox-change="saveBbox"
    />

    <div class="game-actions">
      <button type="button" class="btn-secondary" :disabled="store.currentIndex === 0" @click="goPrev">
        ← Prev
      </button>
      <button type="button" class="btn-secondary" @click="saveBbox(null)">Clear box</button>
      <button
        type="button"
        class="btn-secondary"
        :disabled="store.currentIndex >= store.imageCount - 1"
        @click="goNext"
      >
        Next →
      </button>
      <button type="button" class="btn-primary" :disabled="finishing" @click="handleFinish">
        Finish early
      </button>
    </div>
  </main>
</template>

<style scoped>
.game-page {
  max-width: 900px;
}

.game-header {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 1.5rem;
  align-items: start;
  margin-bottom: 1.25rem;
}

.game-title {
  font-size: 1.75rem;
  text-transform: lowercase;
  font-family: var(--font-mono);
}

.game-progress {
  margin: 0.35rem 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.game-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
  margin-top: 1.5rem;
}

@media (max-width: 640px) {
  .game-header {
    grid-template-columns: 1fr;
  }
}
</style>
