<script setup lang="ts">
import { computed, ref } from 'vue'

const IMAGE_EXT = /\.(jpe?g|png|bmp|webp)$/i
const GT_EXT = /\.(png|jpe?g|bmp|webp)$/i

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  ready: [images: File[], gt: File[]]
}>()

const displayName = ref('')
const imageFiles = ref<File[]>([])
const gtFiles = ref<File[]>([])
const dragOver = ref(false)
const localError = ref<string | null>(null)

function stem(name: string): string {
  const base = name.split(/[/\\]/).pop() ?? name
  return base.replace(/\.[^.]+$/, '').toLowerCase()
}

const matchedCount = computed(() => {
  const imgStems = new Set(
    imageFiles.value.filter((f) => IMAGE_EXT.test(f.name)).map((f) => stem(f.name)),
  )
  const gtStems = new Set(
    gtFiles.value.filter((f) => GT_EXT.test(f.name)).map((f) => stem(f.name)),
  )
  let n = 0
  for (const s of imgStems) {
    if (gtStems.has(s)) n += 1
  }
  return n
})

const canStart = computed(
  () =>
    !props.disabled &&
    displayName.value.trim().length > 0 &&
    matchedCount.value > 0 &&
    matchedCount.value <= 30,
)

function addFiles(files: FileList | File[], kind: 'images' | 'gt') {
  const list = Array.from(files)
  if (kind === 'images') {
    imageFiles.value = [...imageFiles.value, ...list.filter((f) => IMAGE_EXT.test(f.name))]
  } else {
    gtFiles.value = [...gtFiles.value, ...list.filter((f) => GT_EXT.test(f.name))]
  }
  localError.value = null
}

function onImageInput(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) addFiles(input.files, 'images')
  input.value = ''
}

function onGtInput(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) addFiles(input.files, 'gt')
  input.value = ''
}

function onDrop(e: DragEvent) {
  dragOver.value = false
  if (!e.dataTransfer?.files) return
  const files = Array.from(e.dataTransfer.files)
  addFiles(files.filter((f) => IMAGE_EXT.test(f.name)), 'images')
  addFiles(files.filter((f) => GT_EXT.test(f.name)), 'gt')
}

function start() {
  if (!canStart.value) return
  const imgStems = new Set(
    imageFiles.value.filter((f) => IMAGE_EXT.test(f.name)).map((f) => stem(f.name)),
  )
  const gtStems = new Set(
    gtFiles.value.filter((f) => GT_EXT.test(f.name)).map((f) => stem(f.name)),
  )
  const common = [...imgStems].filter((s) => gtStems.has(s))
  if (common.length === 0) {
    localError.value = 'No matching pairs by filename stem.'
    return
  }
  const images = imageFiles.value.filter((f) => common.includes(stem(f.name)))
  const gt = gtFiles.value.filter((f) => common.includes(stem(f.name)))
  emit('ready', images, gt)
}
</script>

<template>
  <div class="upload-zone">
    <label class="field-label" for="name">Display name</label>
    <input
      id="name"
      v-model="displayName"
      class="text-input"
      type="text"
      maxlength="32"
      placeholder="Your name on the leaderboard"
      :disabled="disabled"
    />

    <div
      class="drop-area"
      :class="{ 'drop-area--active': dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop.prevent="onDrop"
    >
      <p class="drop-title">Drop images &amp; masks here</p>
      <p class="drop-hint">Pairs match by filename stem — e.g. <code>cat.jpg</code> + <code>cat.png</code></p>
      <div class="drop-actions">
        <label class="btn-secondary file-btn">
          Images
          <input type="file" multiple accept="image/*" hidden @change="onImageInput" />
        </label>
        <label class="btn-secondary file-btn">
          Folder (images)
          <input type="file" webkitdirectory multiple hidden @change="onImageInput" />
        </label>
        <label class="btn-secondary file-btn">
          Ground truth
          <input type="file" multiple accept="image/*" hidden @change="onGtInput" />
        </label>
        <label class="btn-secondary file-btn">
          Folder (GT)
          <input type="file" webkitdirectory multiple hidden @change="onGtInput" />
        </label>
      </div>
    </div>

    <div class="upload-stats">
      <span>{{ imageFiles.length }} images</span>
      <span>{{ gtFiles.length }} masks</span>
      <span class="upload-stats__match">{{ matchedCount }} matched pairs</span>
    </div>

    <p v-if="matchedCount > 30" class="upload-warn">Max 30 pairs per round.</p>
    <p v-if="localError" class="error-banner">{{ localError }}</p>

    <button class="btn-primary start-btn" type="button" :disabled="!canStart" @click="start">
      Start game — {{ matchedCount }}s on the clock
    </button>
  </div>
</template>

<style scoped>
.upload-zone {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field-label {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.text-input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.85rem 1rem;
  color: var(--text);
  font-family: var(--font-display);
  font-size: 1rem;
}

.text-input:focus {
  outline: none;
  border-color: var(--accent-dim);
}

.drop-area {
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  padding: 2rem;
  text-align: center;
  transition: border-color 0.2s, background 0.2s;
}

.drop-area--active {
  border-color: var(--accent);
  background: rgba(255, 255, 255, 0.03);
}

.drop-title {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.drop-hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0 0 1.25rem;
}

.drop-hint code {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: var(--bg-elevated);
  padding: 0.15em 0.4em;
  border-radius: 4px;
}

.drop-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
}

.file-btn {
  display: inline-block;
  cursor: pointer;
}

.upload-stats {
  display: flex;
  gap: 1.5rem;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--text-muted);
}

.upload-stats__match {
  color: var(--accent);
  font-weight: 700;
}

.upload-warn {
  color: var(--text-muted);
  margin: 0;
  font-size: 0.9rem;
}

.start-btn {
  align-self: flex-start;
  margin-top: 0.5rem;
}
</style>
