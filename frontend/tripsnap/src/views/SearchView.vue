<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiJson } from '../utils/api'

const router = useRouter()

const q = ref('')
const isLoading = ref(false)
const error = ref('')
const results = ref([])

async function onSearch() {
  error.value = ''
  const query = q.value.trim()
  if (!query) {
    results.value = []
    return
  }

  isLoading.value = true
  try {
    // ✅ (권장) 서버에 JSON 검색 API를 추가하세요. 아래 “Django 추가 API” 참고
    // GET /api/users/search/?q=...
    const data = await apiJson(`/api/users/search/?q=${encodeURIComponent(query)}`)
    results.value = data.results || []
  } catch (e) {
    error.value = e.message
    results.value = []
  } finally {
    isLoading.value = false
  }
}

function goProfile(nickname) {
  router.push({ name: 'profile-detail', params: { nickname } })
}
</script>

<template>
  <div class="ts-search-page">
    <div class="ts-search-card pixel-corners">
      <h2 class="ts-search-title">프로필 검색</h2>

      <form class="ts-search-form" @submit.prevent="onSearch">
        <input class="ts-input" v-model="q" placeholder="닉네임 또는 이메일을 입력하세요" />
        <button class="ts-btn ts-btn--pink" type="submit" :disabled="isLoading">
          {{ isLoading ? '검색 중...' : '검색' }}
        </button>
      </form>

      <p v-if="error" class="ts-error">{{ error }}</p>

      <div class="ts-search-results">
        <button
          v-for="u in results"
          :key="u.nickname"
          class="ts-user-row"
          type="button"
          @click="goProfile(u.nickname)"
        >
          <div class="ts-user-avatar">
            <img v-if="u.profile_img" :src="u.profile_img" alt="" />
            <span v-else>🍞</span>
          </div>
          <div class="ts-user-meta">
            <div class="ts-user-name">{{ u.nickname }}</div>
            <div class="ts-user-sub">@{{ u.username }}</div>
          </div>
        </button>

        <p v-if="!isLoading && results.length === 0 && q.trim()" class="ts-empty">
          검색 결과가 없습니다.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;
$ts-cream: #fff5e6;
$ts-pink: #ff69b4;
$ts-pink-hover: #ff1493;

.pixel-corners {
  border-radius: 1.25rem;
}

.ts-search-page {
  padding: 1rem;
}
.ts-search-card {
  max-width: 44rem;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.92);
  border: 4px solid $ts-border-brown;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
  padding: 1.5rem;
}

.ts-search-title {
  margin: 0 0 1rem;
  color: $ts-border-brown;
  font-weight: 900;
  font-size: 1.6rem;
}

.ts-search-form {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  background: $ts-cream;
  border: 1px solid rgba(210, 105, 30, 0.35);
  padding: 0.85rem;
  border-radius: 0.95rem;
}

.ts-input {
  flex: 1;
  padding: 0.65rem 0.85rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(0, 0, 0, 0.18);
  background: #fff;
}
.ts-input:focus {
  outline: none;
  border-color: $ts-pink;
  box-shadow: 0 0 0 3px rgba(255, 105, 180, 0.18);
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
}
.ts-btn--pink:hover {
  background: $ts-pink-hover;
}
.ts-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ts-error {
  margin-top: 0.75rem;
  color: #b00020;
  font-weight: 700;
}

.ts-search-results {
  margin-top: 1rem;
  display: grid;
  gap: 0.5rem;
}

.ts-user-row {
  width: 100%;
  display: flex;
  gap: 0.75rem;
  align-items: center;
  padding: 0.8rem;
  border-radius: 0.9rem;
  border: 1px solid rgba(0, 0, 0, 0.14);
  background: #fff;
  cursor: pointer;
  text-align: left;
}
.ts-user-row:hover {
  border-color: rgba(210, 105, 30, 0.5);
}

.ts-user-avatar {
  width: 44px;
  height: 44px;
  border-radius: 999px;
  overflow: hidden;
  background: #ffe8cc;
  display: grid;
  place-items: center;
  border: 1px solid rgba(0, 0, 0, 0.14);
}
.ts-user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ts-user-name {
  font-weight: 900;
  color: $ts-border-brown;
}
.ts-user-sub {
  font-size: 0.85rem;
  color: #6b7280;
}

.ts-empty {
  margin-top: 0.75rem;
  color: #9ca3af;
}
</style>
