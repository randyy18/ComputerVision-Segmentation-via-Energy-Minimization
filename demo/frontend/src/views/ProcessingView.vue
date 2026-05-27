<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '@/stores/gameStore'

const store = useGameStore()
const router = useRouter()

onMounted(() => {
  if (store.phase !== 'processing') {
    if (store.phase === 'results') router.replace('/results')
    else router.replace('/')
  }
})
</script>

<template>
  <main class="page processing-page">
    <div class="processing-card card">
      <div class="spinner" />
      <h1 class="page-title">Running graph cuts</h1>
      <p class="page-subtitle processing-sub">
        Iterative histogram refinement on {{ store.bboxes.filter((b) => b !== null).length }}
        images… hang tight.
      </p>
      <div class="progress-bar processing-bar">
        <div class="progress-bar-fill" style="width: 100%" />
      </div>
    </div>
  </main>
</template>

<style scoped>
.processing-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 80px);
}

.processing-card {
  text-align: center;
  max-width: 420px;
  width: 100%;
  padding: 2.5rem;
}

.processing-sub {
  margin: 0 auto 1.5rem;
}

.processing-bar {
  margin-top: 0.5rem;
}

.spinner {
  width: 48px;
  height: 48px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  margin: 0 auto 1.5rem;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
