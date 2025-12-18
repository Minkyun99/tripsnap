<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useProfileStore } from '../stores/profile'

const router = useRouter()
const ps = useProfileStore()

const q = ref('')
const error = ref('')
const isLoading = ref(false)

async function onSubmit() {
  error.value = ''
  isLoading.value = true
  try {
    const nickname = await ps.searchProfile(q.value)
    router.push({ name: 'profile-detail', params: { nickname } })
  } catch (e) {
    error.value = e.message
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <main style="padding: 1.5rem">
    <section
      style="
        max-width: 48rem;
        margin: 0 auto;
        background: rgba(255, 255, 255, 0.92);
        border: 4px solid #d2691e;
        border-radius: 1.25rem;
        padding: 1.5rem;
        box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
      "
    >
      <h2 style="margin: 0 0 0.75rem; color: #d2691e; font-weight: 900; font-size: 1.6rem">
        프로필 검색
      </h2>

      <p style="margin: 0 0 1rem; color: #8b4513; font-weight: 700">
        닉네임 또는 이메일로 다른 사용자를 찾아 프로필로 이동합니다.
      </p>

      <form @submit.prevent="onSubmit" style="display: flex; gap: 0.75rem; align-items: center">
        <input
          v-model="q"
          placeholder="닉네임 또는 이메일"
          style="
            flex: 1;
            padding: 0.75rem 0.9rem;
            border-radius: 0.75rem;
            border: 1px solid rgba(0, 0, 0, 0.18);
            font-size: 1rem;
          "
        />
        <button
          type="submit"
          :disabled="isLoading"
          style="
            padding: 0.75rem 1rem;
            border-radius: 0.75rem;
            border: 2px solid #d2691e;
            background: #ff69b4;
            color: #fff;
            font-weight: 900;
            cursor: pointer;
          "
        >
          {{ isLoading ? '검색 중...' : '검색' }}
        </button>
      </form>

      <p v-if="error" style="margin: 0.75rem 0 0; color: #b00020; font-weight: 700">
        {{ error }}
      </p>
    </section>
  </main>
</template>
