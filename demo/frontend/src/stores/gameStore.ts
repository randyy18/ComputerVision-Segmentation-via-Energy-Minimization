import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  AggregateMetrics,
  Bbox,
  DatasetSummary,
  ImageMetrics,
  LeaderboardEntry,
  SessionCreateResponse,
} from '@/api/client'
import {
  clearDatasetContext,
  createSession,
  finishSession,
  getLeaderboard,
  getResults,
  listDatasets,
  loadDatasetContext,
  retrySession,
  saveDatasetContext,
  submitLeaderboard,
} from '@/api/client'

export type Phase = 'upload' | 'game' | 'processing' | 'results'

export const useGameStore = defineStore('game', () => {
  const phase = ref<Phase>('upload')
  const displayName = ref('')
  const sessionId = ref<string | null>(null)
  const datasetId = ref<string | null>(null)
  const datasetLabel = ref<string | null>(null)
  const stems = ref<string[]>([])
  const imageCount = ref(0)
  const timeLimitSec = ref(0)
  const timeRemaining = ref(0)
  const currentIndex = ref(0)
  const bboxes = ref<(Bbox | null)[]>([])
  const results = ref<ImageMetrics[]>([])
  const aggregate = ref<AggregateMetrics | null>(null)
  const leaderboard = ref<LeaderboardEntry[]>([])
  const datasetList = ref<DatasetSummary[]>([])
  const lastRank = ref<number | null>(null)
  const error = ref<string | null>(null)
  const submittedToBoard = ref(false)

  function reset() {
    phase.value = 'upload'
    sessionId.value = null
    datasetId.value = null
    datasetLabel.value = null
    clearDatasetContext()
    stems.value = []
    imageCount.value = 0
    timeLimitSec.value = 0
    timeRemaining.value = 0
    currentIndex.value = 0
    bboxes.value = []
    results.value = []
    aggregate.value = null
    lastRank.value = null
    error.value = null
    submittedToBoard.value = false
  }

  async function startSession(name: string, images: File[], gt: File[]) {
    error.value = null
    displayName.value = name
    const session: SessionCreateResponse = await createSession(name, images, gt)
    sessionId.value = session.session_id
    datasetId.value = session.dataset_id
    datasetLabel.value = session.dataset_label
    saveDatasetContext(session.dataset_id, session.dataset_label)
    stems.value = session.stems
    imageCount.value = session.image_count
    timeLimitSec.value = session.time_limit_sec
    timeRemaining.value = session.time_limit_sec
    bboxes.value = Array(session.image_count).fill(null)
    currentIndex.value = 0
    phase.value = 'game'
  }

  function setLocalBbox(index: number, bbox: Bbox | null) {
    bboxes.value[index] = bbox
  }

  function tickTimer() {
    if (timeRemaining.value > 0) timeRemaining.value -= 1
  }

  async function runFinish() {
    if (!sessionId.value) return
    phase.value = 'processing'
    error.value = null
    try {
      await finishSession(sessionId.value)
      const res = await getResults(sessionId.value)
      results.value = res.images
      aggregate.value = res.aggregate
      phase.value = 'results'
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Segmentation failed'
      phase.value = 'game'
    }
  }

  async function loadDatasetList() {
    const res = await listDatasets()
    datasetList.value = res.datasets
  }

  async function loadLeaderboard(forDatasetId?: string) {
    const id = forDatasetId ?? datasetId.value ?? loadDatasetContext().datasetId
    if (!id) {
      leaderboard.value = []
      return
    }
    datasetId.value = id
    const res = await getLeaderboard(id)
    datasetLabel.value = res.dataset_label
    saveDatasetContext(id, res.dataset_label)
    leaderboard.value = res.entries
  }

  async function selectDataset(id: string) {
    await loadLeaderboard(id)
  }

  async function postToLeaderboard() {
    if (!sessionId.value) return
    const entry = await submitLeaderboard(sessionId.value, displayName.value)
    lastRank.value = entry.rank
    submittedToBoard.value = true
    await loadLeaderboard()
    await loadDatasetList()
  }

  async function tryAgain() {
    if (!sessionId.value) return
    const res = await retrySession(sessionId.value)
    timeLimitSec.value = res.time_limit_sec
    timeRemaining.value = res.time_limit_sec
    bboxes.value = Array(imageCount.value).fill(null)
    currentIndex.value = 0
    results.value = []
    aggregate.value = null
    lastRank.value = null
    submittedToBoard.value = false
    phase.value = 'game'
  }

  return {
    phase,
    displayName,
    sessionId,
    datasetId,
    datasetLabel,
    stems,
    imageCount,
    timeLimitSec,
    timeRemaining,
    currentIndex,
    bboxes,
    results,
    aggregate,
    leaderboard,
    datasetList,
    lastRank,
    error,
    submittedToBoard,
    reset,
    startSession,
    setLocalBbox,
    tickTimer,
    runFinish,
    loadLeaderboard,
    loadDatasetList,
    selectDataset,
    postToLeaderboard,
    tryAgain,
  }
})
