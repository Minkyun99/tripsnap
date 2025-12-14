<script setup>
import { ref } from 'vue'
import { useProfileStore } from '../../stores/profile'

const emit = defineEmits(['close'])
const ps = useProfileStore()

const title = ref('')
const content = ref('')
const file = ref(null)
const isLoading = ref(false)
const error = ref('')

function onPick(e) {
  file.value = e.target.files?.[0] || null
}

async function submit() {
  error.value = ''
  isLoading.value = true
  try {
    await ps.createPost({ title: title.value, content: content.value, file: file.value })
    // 작성 후 내 프로필 데이터 재로딩
    await ps.loadMyProfile()
    emit('close')
  } catch (e) {
    error.value = e.message
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="ts-overlay" @click.self="emit('close')">
    <div class="ts-create-modal pixel-corners" @click.stop>
      <h2 class="ts-title">게시글 작성</h2>

      <input class="ts-input" v-model="title" placeholder="제목" />
      <textarea class="ts-textarea" v-model="content" rows="4" placeholder="내용"></textarea>
      <input class="ts-input" type="file" @change="onPick" />

      <p v-if="error" class="ts-error">{{ error }}</p>

      <div class="ts-actions">
        <button class="ts-btn ts-btn--pink" type="button" @click="submit" :disabled="isLoading">
          {{ isLoading ? '업로드 중...' : '게시글 올리기' }}
        </button>
        <button class="ts-btn ts-btn--white" type="button" @click="emit('close')">취소</button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
$ts-border-brown: #d2691e;
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
.ts-create-modal {
  width: 100%;
  max-width: 34rem;
  background: #fff;
  border: 4px solid $ts-border-brown;
  padding: 1.25rem;
  box-shadow: 0 26px 70px rgba(0, 0, 0, 0.22);
}
.ts-title {
  margin: 0 0 1rem;
  font-size: 1.35rem;
  font-weight: 900;
  color: $ts-border-brown;
}
.ts-input {
  width: 100%;
  padding: 0.7rem 0.85rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(0, 0, 0, 0.18);
  margin-bottom: 0.65rem;
}
.ts-textarea {
  width: 100%;
  padding: 0.7rem 0.85rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(0, 0, 0, 0.18);
  margin-bottom: 0.65rem;
  resize: vertical;
}
.ts-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
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
.ts-error {
  margin: 0.5rem 0 0.75rem;
  color: #b00020;
  font-weight: 700;
}
</style>
