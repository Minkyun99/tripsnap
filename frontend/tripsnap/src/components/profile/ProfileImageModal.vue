<script setup>
import { ref } from 'vue'
import { useProfileStore } from '../../stores/profile'

const emit = defineEmits(['close'])
const ps = useProfileStore()

const file = ref(null)
const preview = ref('')

function onPick(e) {
  const f = e.target.files?.[0]
  if (!f) return
  file.value = f
  preview.value = URL.createObjectURL(f)
}

function toBase64(f) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(f)
  })
}

async function upload() {
  if (!file.value) return
  const base64 = await toBase64(file.value)
  await ps.uploadProfileImageBase64(base64)
  emit('close')
}
</script>

<template>
  <div class="ts-overlay" @click.self="emit('close')">
    <div class="ts-image-modal pixel-corners">
      <h2 class="ts-image-title">프로필 이미지 변경</h2>

      <div class="ts-image-preview">
        <img v-if="preview" :src="preview" />
        <img v-else-if="ps.profileImgUrl" :src="ps.profileImgUrl" />
        <span v-else style="font-size: 3rem">🍞</span>
      </div>

      <input type="file" accept="image/*" @change="onPick" />

      <div class="ts-image-actions">
        <button class="ts-btn ts-btn--pink" type="button" @click="upload" :disabled="!file">
          업로드
        </button>
        <button class="ts-btn ts-btn--white" type="button" @click="emit('close')">취소</button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'sass:color';

$ts-border-brown: #d2691e;
$ts-cream-2: #ffe8cc;
$ts-pink: #ff69b4;
$ts-pink-hover: #ff1493;

.pixel-corners {
  border-radius: 1.25rem;
}
.ts-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  padding: 1rem;
  display: grid;
  place-items: center;
  z-index: 60;
}
.ts-image-modal {
  width: 100%;
  max-width: 28rem;
  background: #fff;
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  padding: 1.5rem;
  box-shadow: 0 26px 70px rgba(0, 0, 0, 0.22);
}
.ts-image-title {
  margin: 0 0 1rem;
  font-size: 1.45rem;
  font-weight: 900;
  text-align: center;
  color: $ts-border-brown;
}
.ts-image-preview {
  width: 192px;
  height: 192px;
  margin: 0 auto 1rem;
  border-radius: 999px;
  overflow: hidden;
  border: 4px solid $ts-border-brown;
  background: $ts-cream-2;
  display: grid;
  place-items: center;
}
.ts-image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ts-image-actions {
  margin-top: 0.75rem;
  display: flex;
  gap: 0.75rem;
}
.ts-btn {
  padding: 0.65rem 1rem;
  border-radius: 0.7rem;
  font-weight: 900;
  border: 2px solid $ts-border-brown;
  cursor: pointer;
}
.ts-btn--pink {
  background: $ts-pink;
  color: #fff;
  &:hover {
    background: $ts-pink-hover;
  }
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
.ts-btn--white {
  background: #fff;
  color: #6b4f2a;
}
</style>
