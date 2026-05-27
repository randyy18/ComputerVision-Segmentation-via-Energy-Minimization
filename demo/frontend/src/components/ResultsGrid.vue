<script setup lang="ts">
import { ref } from 'vue'
import type { ImageMetrics } from '@/api/client'

defineProps<{
  images: ImageMetrics[]
}>()

const previewMode = ref<Record<number, 'mask' | 'overlay'>>({})

function toggleMode(index: number) {
  previewMode.value[index] = previewMode.value[index] === 'overlay' ? 'mask' : 'overlay'
}

function modeFor(index: number): 'mask' | 'overlay' {
  return previewMode.value[index] ?? 'overlay'
}

function fmt(n: number): string {
  return (n * 100).toFixed(1) + '%'
}
</script>

<template>
  <div class="results-grid">
    <div
      v-for="img in images"
      :key="img.stem"
      class="result-card card animate-fade-up"
      :class="{ 'result-card--skipped': img.skipped }"
    >
      <div class="result-card__head">
        <h3>{{ img.stem }}</h3>
        <span v-if="img.skipped" class="badge">skipped</span>
      </div>

      <template v-if="!img.skipped">
        <div class="result-preview">
          <img
            :src="modeFor(img.index) === 'overlay' ? img.overlay_url : img.mask_url"
            :alt="img.stem"
          />
          <button type="button" class="btn-ghost preview-toggle" @click="toggleMode(img.index)">
            {{ modeFor(img.index) === 'overlay' ? 'Show mask' : 'Show overlay' }}
          </button>
        </div>
        <div class="result-metrics">
          <div>
            <div class="metric-label">IoU</div>
            <div class="metric-value">{{ fmt(img.iou) }}</div>
          </div>
          <div>
            <div class="metric-label">Dice</div>
            <div class="metric-value">{{ fmt(img.dice) }}</div>
          </div>
          <div>
            <div class="metric-label">Pixel err</div>
            <div class="metric-value">{{ fmt(img.pixel_error) }}</div>
          </div>
        </div>
      </template>
      <p v-else class="skipped-msg">No bounding box drawn in time.</p>
    </div>
  </div>
</template>

<style scoped>
.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.25rem;
}

.result-card--skipped {
  opacity: 0.55;
}

.result-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.result-card__head h3 {
  font-family: var(--font-mono);
  font-size: 0.95rem;
  text-transform: lowercase;
}

.badge {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--text-muted);
}

.result-preview {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
  margin-bottom: 1rem;
}

.result-preview img {
  width: 100%;
  display: block;
  aspect-ratio: 4/3;
  object-fit: contain;
  background: var(--bg-elevated);
}

.preview-toggle {
  position: absolute;
  bottom: 0.5rem;
  right: 0.5rem;
  font-size: 0.75rem;
  padding: 0.35rem 0.65rem;
  opacity: 0.9;
}

.result-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  text-align: center;
}

.skipped-msg {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}
</style>
