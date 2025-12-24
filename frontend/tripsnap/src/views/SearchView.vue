<!-- src/views/SearchView.vue -->
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useProfileStore } from '@/stores/profile'

const router = useRouter()
const profileStore = useProfileStore()

// Pinia state 참조
const { searchSuggestions, searchIsLoading, searchError } = storeToRefs(profileStore)

const query = ref('')
let typingTimer = null // 디바운스용

// keyup 시 자동완성 호출 (디바운스)
const onKeyup = () => {
  if (typingTimer) {
    clearTimeout(typingTimer)
  }
  typingTimer = setTimeout(() => {
    profileStore.suggestProfiles(query.value)
  }, 200)
}

// 자동완성 항목 클릭 시, 친구 프로필 페이지로 이동
const selectUser = (user) => {
  if (!user?.nickname) return
  router.push(`/profile/${encodeURIComponent(user.nickname)}`)
}

// 엔터 입력 시: 자동완성 1순위로 이동, 없으면 기존 searchProfile 사용
const onEnter = async () => {
  const list = searchSuggestions.value || []
  if (list.length > 0) {
    selectUser(list[0])
    return
  }

  const q = query.value.trim()
  if (!q) return

  try {
    const nickname = await profileStore.searchProfile(q)
    router.push(`/profile/${encodeURIComponent(nickname)}`)
  } catch (e) {
    // searchProfile 내부에서 에러 메시지를 던지므로,
    // 여기서는 alert이나 별도 처리를 원하면 추가
    alert(e.message || '사용자를 찾을 수 없습니다.')
  }
}
</script>

<template>
  <div class="search-page">
    <div class="search-card">
      <h2 class="search-title">친구 검색</h2>

      <div class="search-field">
        <input
          v-model="query"
          type="text"
          placeholder="이메일, 아이디 또는 닉네임으로 검색"
          @keyup="onKeyup"
          @keyup.enter.prevent="onEnter"
        />
      </div>

      <!-- 에러 메시지 -->
      <p v-if="searchError" class="search-error">
        {{ searchError }}
      </p>

      <!-- 로딩 -->
      <p v-if="searchIsLoading" class="search-loading">검색 중...</p>

      <!-- 자동완성 목록 -->
      <ul v-if="!searchIsLoading && searchSuggestions.length" class="suggest-list">
        <li
          v-for="user in searchSuggestions"
          :key="user.nickname || user.email"
          class="suggest-item"
          @click="selectUser(user)"
        >
          <div class="suggest-main">
            <span class="suggest-nickname">{{ user.nickname }}</span>
            <span class="suggest-username" v-if="user.username"> @{{ user.username }} </span>
          </div>
          <div class="suggest-email">
            {{ user.email }}
          </div>
        </li>
      </ul>

      <!-- 결과 없음 -->
      <p v-else-if="query && !searchIsLoading && !searchError" class="no-result">
        검색 결과가 없습니다.
      </p>
    </div>
  </div>
</template>

<style scoped>
.search-page {
  max-width: 480px;
  margin: 0 auto;
  padding: 1.5rem 1rem;
}

.search-card {
  background: #ffffff;
  border-radius: 1rem;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
  padding: 1.5rem;
}

.search-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 1rem;
}

.search-field input {
  width: 100%;
  padding: 0.7rem 0.9rem;
  border-radius: 0.6rem;
  border: 1px solid #d1d5db;
  font-size: 0.95rem;
}

.search-field input:focus {
  outline: none;
  border-color: #d2691e;
  box-shadow: 0 0 0 3px rgba(210, 105, 30, 0.18);
}

.search-error {
  margin-top: 0.5rem;
  color: #b91c1c;
  font-size: 0.85rem;
}

.search-loading {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #6b7280;
}

.suggest-list {
  list-style: none;
  margin: 0.8rem 0 0;
  padding: 0;
  border-radius: 0.6rem;
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.suggest-item {
  padding: 0.55rem 0.8rem;
  cursor: pointer;
  background: #fff;
}

.suggest-item + .suggest-item {
  border-top: 1px solid #f3f4f6;
}

.suggest-item:hover {
  background: #f9fafb;
}

.suggest-main {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.suggest-nickname {
  font-weight: 700;
}

.suggest-username {
  font-size: 0.82rem;
  color: #6b7280;
}

.suggest-email {
  font-size: 0.8rem;
  color: #9ca3af;
}

.no-result {
  margin-top: 0.7rem;
  font-size: 0.85rem;
  color: #9ca3af;
}
</style>
