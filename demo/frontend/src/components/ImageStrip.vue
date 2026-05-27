<script setup lang="ts">
import { computed } from 'vue'
import type { Bbox } from '@/api/client'

const props = defineProps<{
  stems: string[]
  currentIndex: number
  bboxes: (Bbox | null)[]
}>()

const emit = defineEmits<{
  select: [index: number]
}>()

const items = computed(() =>
  props.stems.map((stem, i) => ({
    stem,
    index: i,
    done: props.bboxes[i] !== null,
    active: i === props.currentIndex,
  })),
)
</script>

<template>
  <div class="strip">
    <button
      v-for="item in items"
      :key="item.stem"
      type="button"
      class="strip-item"
      :class="{
        'strip-item--active': item.active,
        'strip-item--done': item.done,
      }"
      :title="item.stem"
      @click="emit('select', item.index)"
    >
      {{ item.index + 1 }}
    </button>
  </div>
</template>

<style scoped>
.strip {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  justify-content: center;
}

.strip-item {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0;
}

.strip-item--active {
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: 0 0 12px rgba(255, 255, 255, 0.15);
}

.strip-item--done {
  background: var(--text);
  color: var(--bg);
  border-color: var(--text);
}
</style>
