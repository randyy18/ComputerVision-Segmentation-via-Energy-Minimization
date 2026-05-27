<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  remaining: number
  total: number
  running: boolean
}>()

const urgent = computed(() => props.running && props.remaining <= 10 && props.remaining > 0)
const expired = computed(() => props.running && props.remaining <= 0)

const pct = computed(() =>
  props.total > 0 ? ((props.total - props.remaining) / props.total) * 100 : 0,
)
</script>

<template>
  <div class="timer-wrap" :class="{ 'timer-expired-shake': expired }">
    <div class="timer-display" :class="{ 'timer-urgent': urgent }">
      <span class="timer-value">{{ remaining }}</span>
      <span class="timer-unit">sec</span>
    </div>
    <p class="timer-caption">{{ total }} images — {{ total }} seconds</p>
    <div class="progress-bar">
      <div class="progress-bar-fill" :style="{ width: `${pct}%` }" />
    </div>
  </div>
</template>

<style scoped>
.timer-wrap {
  text-align: center;
  padding: 1rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.timer-display {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 0.35rem;
  font-family: var(--font-mono);
}

.timer-value {
  font-size: 3.5rem;
  font-weight: 700;
  line-height: 1;
}

.timer-unit {
  font-size: 1rem;
  color: var(--text-muted);
  text-transform: uppercase;
}

.timer-caption {
  margin: 0.5rem 0 1rem;
  font-size: 0.85rem;
  color: var(--text-muted);
}
</style>
