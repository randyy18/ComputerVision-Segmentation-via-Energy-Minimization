<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ResultsGrid from '@/components/ResultsGrid.vue'
import { downloadMasksUrl } from '@/api/client'
import { useGameStore } from '@/stores/gameStore'

const store = useGameStore()
const router = useRouter()
const submitting = ref(false)
const actionError = ref<string | null>(null)

const agg = computed(() => store.aggregate)

function fmtPct(n: number | undefined): string {
  if (n === undefined) return '—'
  return (n * 100).toFixed(1) + '%'
}

function fmtScore(n: number | undefined): string {
  if (n === undefined) return '—'
  return n.toFixed(2)
}

onMounted(() => {
  if (store.phase !== 'results') {
    router.replace('/')
  }
})

async function submitScore() {
  submitting.value = true
  actionError.value = null
  try {
    await store.postToLeaderboard()
    router.push('/leaderboard')
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : 'Submit failed'
  } finally {
    submitting.value = false
  }
}

async function tryAgain() {
  await store.tryAgain()
  router.push('/game')
}

function downloadZip() {
  if (!store.sessionId) return
  window.location.href = downloadMasksUrl(store.sessionId)
}
</script>

<template>
  <main class="page">
    <h1 class="page-title">Results</h1>
    <p class="page-subtitle">
      Leaderboard rank uses your composite score: mean IoU × images scored (bonus for
      completing more of the set).
    </p>

    <div v-if="actionError" class="error-banner">{{ actionError }}</div>

    <section v-if="agg" class="summary card">
      <div class="summary-grid">
        <div class="summary-primary">
          <div class="metric-label">Leaderboard score</div>
          <div class="metric-value summary-highlight">{{ fmtScore(agg.leaderboard_score) }}</div>
        </div>
        <div>
          <div class="metric-label">Mean IoU</div>
          <div class="metric-value">{{ fmtPct(agg.mean_iou) }}</div>
        </div>
        <div>
          <div class="metric-label">Mean Dice</div>
          <div class="metric-value">{{ fmtPct(agg.mean_dice) }}</div>
        </div>
        <div>
          <div class="metric-label">Images scored</div>
          <div class="metric-value">{{ agg.scored_count }} / {{ agg.image_count }}</div>
        </div>
        <div>
          <div class="metric-label">Mean pixel error</div>
          <div class="metric-value">{{ fmtPct(agg.mean_pixel_error) }}</div>
        </div>
      </div>
    </section>

    <ResultsGrid :images="store.results" />

    <div class="results-actions">
      <button type="button" class="btn-primary" :disabled="submitting || store.submittedToBoard" @click="submitScore">
        {{ store.submittedToBoard ? 'Submitted ✓' : 'Submit to leaderboard' }}
      </button>
      <button type="button" class="btn-secondary" @click="downloadZip">Download masks (ZIP)</button>
      <button type="button" class="btn-secondary" @click="tryAgain">Try again</button>
    </div>
  </main>
</template>

<style scoped>
.summary {
  margin-bottom: 2rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1.5rem;
  text-align: center;
}

.summary-primary {
  grid-column: 1 / -1;
}

.summary-primary .summary-highlight {
  font-size: 2.75rem;
}

.results-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 2rem;
  justify-content: center;
}
</style>
