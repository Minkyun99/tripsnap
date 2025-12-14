<template>
  <div class="ts-overlay" @click.self="emit('close')">
    <div class="ts-image-modal pixel-corners">
      <h2 class="ts-image-title">프로필 이미지 변경</h2>

      <div class="ts-image-preview">
        <img v-if="previewUrl" :src="previewUrl" alt="preview" />
        <img v-else-if="currentUrl" :src="currentUrl" alt="current" />
        <span v-else style="font-size: 3rem; line-height: 1">🍞</span>
      </div>

      <input ref="fileInput" type="file" accept="image/*" style="display: none" @change="onPick" />

      <div class="ts-image-actions">
        <button class="ts-btn ts-btn--pink" type="button" @click="openPicker">이미지 선택</button>

        <button
          class="ts-btn ts-btn--green"
          type="button"
          :disabled="!selectedFile || uploading"
          @click="handleUpload"
        >
          {{ uploading ? '업로드 중...' : '업로드' }}
        </button>
      </div>

      <button
        class="ts-btn ts-btn--white"
        style="width: 100%; margin-top: 0.75rem"
        type="button"
        @click="emit('close')"
      >
        취소
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'

const props = defineProps({
  currentUrl: { type: String, default: '' }, // 현재 프로필 이미지 URL
})

const emit = defineEmits(['close', 'uploaded']) // uploaded(payload)

const fileInput = ref(null)
const selectedFile = ref(null)
const previewUrl = ref('')
const uploading = ref(false)

function openPicker() {
  fileInput.value?.click()
}

function onPick(e) {
  const f = e.target.files?.[0]
  if (!f) return
  selectedFile.value = f

  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(f)
}

async function handleUpload() {
  if (!selectedFile.value || uploading.value) return

  uploading.value = true
  try {
    // ProfileBase(부모)에서 실제 API 호출을 수행하도록 위임
    // payload로 File 전달
    await emit('uploaded', selectedFile.value)
  } finally {
    uploading.value = false
  }
}

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>
