<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/gameStore'

const store = useGameStore()
const router = useRouter()
const loading = ref(true)
const switching = ref(false)
const error = ref<string | null>(null)

function fmtPct(n: number): string {
  return (n * 100).toFixed(1) + '%'
}

function fmtScore(n: number): string {
  return n.toFixed(2)
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

async function refreshAll(selectId?: string) {
  error.value = null
  await store.loadDatasetList()
  const fallback = store.datasetList[0]?.dataset_id
  const target = selectId ?? store.datasetId ?? fallback
  if (target) {
    await store.selectDataset(target)
  }
}

onMounted(async () => {
  try {
    await refreshAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load leaderboard'
  } finally {
    loading.value = false
  }
})

async function onSelectDataset(id: string) {
  if (id === store.datasetId || switching.value) return
  switching.value = true
  error.value = null
  try {
    await store.selectDataset(id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load dataset'
  } finally {
    switching.value = false
  }
}

function playAgain() {
  store.reset()
  router.push('/')
}
</script>

<template>
  <main class="page">
    <h1 class="page-title">Leaderboard</h1>
    <p class="page-subtitle">
      Each upload set has its own board. Pick a dataset tag to view its rankings.
    </p>

    <section v-if="store.datasetList.length > 0" class="dataset-picker">
      <p class="picker-label">Datasets</p>
      <div class="dataset-tags" role="tablist" aria-label="Dataset leaderboards">
        <button
          v-for="ds in store.datasetList"
          :key="ds.dataset_id"
          type="button"
          role="tab"
          class="dataset-chip"
          :class="{ 'dataset-chip--active': ds.dataset_id === store.datasetId }"
          :aria-selected="ds.dataset_id === store.datasetId"
          @click="onSelectDataset(ds.dataset_id)"
        >
          <span class="chip-label">{{ ds.dataset_label }}</span>
          <span class="chip-meta">{{ ds.image_count }} img · {{ ds.entry_count }} runs</span>
        </button>
      </div>
    </section>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-if="loading || switching" class="card loading-card">
      {{ switching ? 'Loading dataset…' : 'Loading…' }}
    </div>

    <template v-else>
      <div v-if="store.datasetList.length === 0" class="card empty-card">
        <p>No datasets yet. Upload images and play to create a leaderboard.</p>
        <button type="button" class="btn-primary" @click="playAgain">Start playing</button>
      </div>

      <div v-else-if="store.leaderboard.length === 0" class="card empty-card">
        <p>
          No scores for <strong>{{ store.datasetLabel }}</strong> yet. Be the first to submit
          a run on this dataset.
        </p>
        <button type="button" class="btn-primary" @click="playAgain">Play this dataset</button>
      </div>

      <table v-else class="board-table card">
        <thead>
          <tr>
            <th colspan="6" class="table-dataset-head">
              {{ store.datasetLabel }}
            </th>
          </tr>
          <tr>
            <th>Rank</th>
            <th>Player</th>
            <th>Score</th>
            <th>Mean IoU</th>
            <th>Scored</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in store.leaderboard"
            :key="`${entry.display_name}-${entry.submitted_at}`"
            :class="{
              'row-you': entry.display_name === store.displayName && store.submittedToBoard,
            }"
          >
            <td class="rank">#{{ entry.rank }}</td>
            <td>{{ entry.display_name }}</td>
            <td class="metric-value score-cell">{{ fmtScore(entry.leaderboard_score) }}</td>
            <td class="iou-cell">{{ fmtPct(entry.mean_iou) }}</td>
            <td>{{ entry.scored_count }}/{{ entry.image_count }}</td>
            <td class="time-cell">{{ formatTime(entry.submitted_at) }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <div v-if="store.lastRank !== null && store.datasetId" class="your-rank card">
      You placed <strong>#{{ store.lastRank }}</strong> on this dataset last round.
    </div>

    <div class="board-actions">
      <button type="button" class="btn-primary" @click="playAgain">Play again</button>
    </div>
  </main>
</template>

<style scoped>
.loading-card,
.empty-card {
  text-align: center;
  padding: 2rem;
}

.empty-card p {
  margin: 0 0 1rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.empty-card strong {
  color: var(--text);
  font-family: var(--font-mono);
}

.dataset-picker {
  margin-bottom: 1.75rem;
}

.picker-label {
  margin: 0 0 0.65rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
}

.dataset-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.dataset-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.2rem;
  padding: 0.65rem 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-muted);
  text-align: left;
  max-width: 100%;
  transition:
    border-color 0.15s,
    background 0.15s,
    transform 0.15s,
    box-shadow 0.15s;
}

.dataset-chip:hover {
  border-color: var(--accent-dim);
  transform: translateY(-2px);
}

.dataset-chip--active {
  background: var(--accent);
  color: var(--bg);
  border-color: var(--accent);
  box-shadow: 0 0 20px rgba(255, 255, 255, 0.12);
}

.chip-label {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
}

.chip-meta {
  font-size: 0.65rem;
  opacity: 0.85;
}

.dataset-chip--active .chip-meta {
  opacity: 0.75;
}

.board-table {
  width: 100%;
  border-collapse: collapse;
  overflow: hidden;
  padding: 0;
}

.table-dataset-head {
  font-family: var(--font-mono);
  font-size: 0.85rem !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  color: var(--text) !important;
  background: var(--bg-elevated) !important;
  border-bottom: 1px solid var(--border);
}

.board-table th,
.board-table td {
  padding: 0.85rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.board-table th {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  background: var(--bg-elevated);
}

.board-table tbody tr:last-child td {
  border-bottom: none;
}

.board-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.03);
}

.row-you {
  background: rgba(255, 255, 255, 0.06) !important;
}

.row-you td {
  font-weight: 600;
}

.rank {
  font-family: var(--font-mono);
  font-weight: 700;
}

.score-cell {
  font-size: 1.2rem;
  font-weight: 700;
}

.iou-cell {
  font-size: 0.95rem;
  color: var(--text-muted);
}

.time-cell {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.your-rank {
  margin-top: 1.5rem;
  text-align: center;
  font-size: 1.1rem;
}

.board-actions {
  margin-top: 2rem;
  text-align: center;
}
</style>
