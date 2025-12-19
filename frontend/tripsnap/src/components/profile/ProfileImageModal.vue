<template>
  <div class="ts-overlay" @click.self="$emit('close')">
    <div class="ts-image-modal pixel-corners">
      <h2 class="ts-image-title">프로필 이미지 변경</h2>

      <div class="ts-image-preview">
        <img v-if="previewUrl" :src="previewUrl" />
        <span v-else style="font-size: 3rem">🍞</span>
      </div>

      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        style="display: none"
        @change="onPickProfileImage"
      />

      <div class="ts-image-actions">
        <button class="ts-btn ts-btn--pink" type="button" @click="openFilePicker">
          이미지 선택
        </button>
        <button
          class="ts-btn ts-btn--green"
          type="button"
          :disabled="!selectedFile"
          @click="upload"
        >
          업로드
        </button>
      </div>

      <button
        class="ts-btn ts-btn--white"
        style="width: 100%; margin-top: 0.75rem"
        type="button"
        @click="$emit('close')"
      >
        취소
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useProfileStore } from '@/stores/profile'

defineEmits(['close'])

const ps = useProfileStore()

const fileInput = ref(null)
const selectedFile = ref(null)
const previewUrl = ref('')

function openFilePicker() {
  fileInput.value?.click()
}

function onPickProfileImage(e) {
  const f = e.target.files?.[0]
  if (!f) return
  selectedFile.value = f
  previewUrl.value = URL.createObjectURL(f)
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result) // data:image/...;base64,...
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

async function upload() {
  if (!selectedFile.value) return
  const base64 = await fileToBase64(selectedFile.value)
  await ps.uploadProfileImageBase64(base64)
  ps.closeImageModal()
}
</script>

<style scoped lang="scss">
@use '@/assets/profile.scss' as *;
</style>
