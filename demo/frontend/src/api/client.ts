export interface Bbox {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface SessionCreateResponse {
  session_id: string
  display_name: string
  image_count: number
  time_limit_sec: number
  stems: string[]
  dataset_id: string
  dataset_label: string
}

export interface SessionResponse {
  session_id: string
  display_name: string
  image_count: number
  time_limit_sec: number
  phase: 'game' | 'processing' | 'done'
  images: { index: number; stem: string; has_bbox: boolean }[]
  bbox_count: number
}

export interface ImageMetrics {
  index: number
  stem: string
  iou: number
  dice: number
  pixel_error: number
  mask_url: string
  overlay_url: string
  skipped: boolean
}

export interface AggregateMetrics {
  mean_iou: number
  mean_dice: number
  mean_pixel_error: number
  scored_count: number
  image_count: number
  leaderboard_score: number
}

export interface ResultsResponse {
  session_id: string
  status: 'processing' | 'done' | 'idle'
  images: ImageMetrics[]
  aggregate: AggregateMetrics | null
}

export interface LeaderboardEntry {
  rank: number
  display_name: string
  leaderboard_score: number
  mean_iou: number
  scored_count: number
  image_count: number
  submitted_at: string
}

export interface LeaderboardResponse {
  dataset_id: string
  dataset_label: string
  entries: LeaderboardEntry[]
}

export interface DatasetSummary {
  dataset_id: string
  dataset_label: string
  image_count: number
  entry_count: number
}

export interface DatasetListResponse {
  datasets: DatasetSummary[]
}

const DATASET_ID_KEY = 'grabcut_dataset_id'
const DATASET_LABEL_KEY = 'grabcut_dataset_label'

// Backend URL dari Vercel Environment Variable.
// Contoh value di Vercel:
// VITE_API_BASE_URL=https://randyy18-grabcut-backend.hf.space
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

function apiUrl(path: string): string {
  // Kalau path sudah absolute URL, langsung return.
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path
  }

  // Kalau tidak ada API_BASE_URL, fallback ke relative path untuk local dev/proxy.
  if (!API_BASE_URL) {
    return path
  }

  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

export function saveDatasetContext(datasetId: string, datasetLabel: string): void {
  localStorage.setItem(DATASET_ID_KEY, datasetId)
  localStorage.setItem(DATASET_LABEL_KEY, datasetLabel)
}

export function loadDatasetContext(): { datasetId: string | null; datasetLabel: string | null } {
  return {
    datasetId: localStorage.getItem(DATASET_ID_KEY),
    datasetLabel: localStorage.getItem(DATASET_LABEL_KEY),
  }
}

export function clearDatasetContext(): void {
  localStorage.removeItem(DATASET_ID_KEY)
  localStorage.removeItem(DATASET_LABEL_KEY)
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(url), init)

  if (!res.ok) {
    let detail = res.statusText

    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* ignore */
    }

    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  return res.json() as Promise<T>
}

export async function createSession(
  displayName: string,
  imageFiles: File[],
  gtFiles: File[],
): Promise<SessionCreateResponse> {
  const form = new FormData()
  form.append('display_name', displayName)

  for (const f of imageFiles) {
    form.append('images', f)
  }

  for (const f of gtFiles) {
    form.append('gt', f)
  }

  return request<SessionCreateResponse>('/api/sessions', {
    method: 'POST',
    body: form,
  })
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  return request<SessionResponse>(`/api/sessions/${sessionId}`)
}

export function imageUrl(sessionId: string, index: number): string {
  return apiUrl(`/api/sessions/${sessionId}/images/${index}`)
}

export async function setBbox(sessionId: string, index: number, bbox: Bbox): Promise<void> {
  await request<void>(`/api/sessions/${sessionId}/bboxes/${index}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bbox),
  })
}

export async function finishSession(sessionId: string): Promise<void> {
  await request<void>(`/api/sessions/${sessionId}/finish`, {
    method: 'POST',
  })
}

export async function getResults(sessionId: string): Promise<ResultsResponse> {
  const data = await request<ResultsResponse>(`/api/sessions/${sessionId}/results`)

  return {
    ...data,
    images: data.images.map((img) => ({
      ...img,
      mask_url: img.mask_url ? apiUrl(img.mask_url) : '',
      overlay_url: img.overlay_url ? apiUrl(img.overlay_url) : '',
    })),
  }
}

export async function retrySession(sessionId: string): Promise<{ time_limit_sec: number }> {
  return request<{ time_limit_sec: number }>(`/api/sessions/${sessionId}/retry`, {
    method: 'POST',
  })
}

export function downloadMasksUrl(sessionId: string): string {
  return apiUrl(`/api/sessions/${sessionId}/download`)
}

export async function listDatasets(): Promise<DatasetListResponse> {
  return request<DatasetListResponse>('/api/leaderboard/datasets')
}

export async function getLeaderboard(datasetId: string): Promise<LeaderboardResponse> {
  return request<LeaderboardResponse>(`/api/leaderboard?dataset_id=${encodeURIComponent(datasetId)}`)
}

export async function submitLeaderboard(
  sessionId: string,
  displayName: string,
): Promise<LeaderboardEntry> {
  return request<LeaderboardEntry>('/api/leaderboard', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      display_name: displayName,
    }),
  })
}