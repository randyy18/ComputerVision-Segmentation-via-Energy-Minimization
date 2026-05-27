<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import UploadZone from '@/components/UploadZone.vue'
import { useGameStore } from '@/stores/gameStore'

const store = useGameStore()
const router = useRouter()
const loading = ref(false)
const error = ref<string | null>(null)

async function onReady(images: File[], gt: File[]) {
  loading.value = true
  error.value = null
  try {
    const nameInput = document.getElementById('name') as HTMLInputElement | null
    const name = nameInput?.value.trim() || 'Player'
    store.displayName = name
    await store.startSession(name, images, gt)
    router.push('/game')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to start session'
  } finally {
    loading.value = false
  }
}

function onReadyWithName(images: File[], gt: File[]) {
  onReady(images, gt)
}
</script>

<template>
  <main class="page animate-fade-up">
    <h1 class="page-title">GrabCut Challenge</h1>
    <p class="page-subtitle">
      Upload image + ground-truth pairs, draw bounding boxes under the clock, and let classical
      graph cuts refine your segmentation. Score more images with tighter boxes to climb
      the leaderboard.
    </p>

    <div v-if="error || store.error" class="error-banner">{{ error || store.error }}</div>

    <UploadZone :disabled="loading" @ready="onReadyWithName" />
  </main>
</template>
