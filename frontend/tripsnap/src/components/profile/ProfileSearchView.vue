<!-- src/components/ProfileSearchView.vue (컴포넌트용) -->
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useProfileStore } from '@/stores/profile'
import { useBakeryStore } from '@/stores/bakery'

const router = useRouter()
const ps = useProfileStore()
const bakeryStore = useBakeryStore()

// 통합 검색 결과는 store에서 가져옴
const { searchUserResults, searchBakeryResults } = storeToRefs(ps)

const q = ref('')
const error = ref('')
const isLoading = ref(false)

/**
 * 프로필 + 빵집 통합 검색
 */
async function onSubmit() {
  error.value = ''
  isLoading.value = true

  try {
    await ps.searchUsersAndBakeries(q.value)
  } catch (e) {
    error.value = e.message || '검색 중 오류가 발생했습니다.'
  } finally {
    isLoading.value = false
  }
}

/**
 * 유저 카드 클릭 → 프로필 페이지 이동
 */
function goUserProfile(nickname) {
  if (!nickname) return
  router.push({ name: 'profile-detail', params: { nickname } }).catch(() => {})
}

/**
 * 빵집 카드 클릭 → 빵집 모달 오픈
 * (BakeryModal은 부모 컴포넌트나 상위 레이아웃에서 렌더링)
 */
function openBakeryModal(id) {
  if (!id) return
  bakeryStore.openModalById(id)
}
</script>

<template>
  <section class="ts-profile-search">
    <!-- 헤더 / 설명 -->
    <header class="ts-search-header">
      <h2 class="ts-search-title">프로필 / 빵집 검색</h2>
      <p class="ts-search-subtitle">
        닉네임, 이메일 또는 빵집 이름으로 유사한 유저와 빵집을 함께 찾아보세요.
      </p>
    </header>

    <!-- 검색 폼 -->
    <form class="ts-search-form" @submit.prevent="onSubmit">
      <input
        v-model="q"
        class="ts-search-input"
        placeholder="닉네임 / 이메일 / 빵집 이름"
        @keydown.enter.prevent="onSubmit"
      />
      <button type="submit" class="ts-search-btn" :disabled="isLoading">
        {{ isLoading ? '검색 중...' : '검색' }}
      </button>
    </form>

    <p v-if="error" class="ts-search-error">
      {{ error }}
    </p>

    <!-- 검색 결과: 유저 카드 -->
    <section v-if="searchUserResults.length" class="ts-result-block">
      <h3 class="ts-result-title">유저</h3>
      <div class="ts-card-grid">
        <article
          v-for="u in searchUserResults"
          :key="u.nickname"
          class="ts-result-card"
          @click="goUserProfile(u.nickname)"
        >
          <div class="ts-result-thumb">
            <img v-if="u.profile_img" :src="u.profile_img" alt="user profile" />
            <span v-else>🍞</span>
          </div>
          <div class="ts-result-body">
            <p class="ts-result-name">{{ u.nickname }}</p>
            <p class="ts-result-sub">@{{ u.username }}</p>
          </div>
        </article>
      </div>
    </section>

    <!-- 검색 결과: 빵집 카드 -->
    <section v-if="searchBakeryResults.length" class="ts-result-block">
      <h3 class="ts-result-title">빵집</h3>
      <div class="ts-card-grid">
        <article
          v-for="b in searchBakeryResults"
          :key="b.id"
          class="ts-result-card"
          @click="openBakeryModal(b.id)"
        >
          <div class="ts-result-thumb">
            <img v-if="b.thumbnail_url" :src="b.thumbnail_url" alt="bakery" />
            <span v-else>🥐</span>
          </div>
          <div class="ts-result-body">
            <p class="ts-result-name">{{ b.name }}</p>
            <p class="ts-result-sub">
              {{ b.district }}
              <span v-if="b.road_address"> · {{ b.road_address }}</span>
            </p>
          </div>
        </article>
      </div>
    </section>

    <!-- 아무 결과도 없을 때 -->
    <p
      v-if="!isLoading && !error && q && !searchUserResults.length && !searchBakeryResults.length"
      class="ts-search-empty"
    >
      해당 검색어와 일치하는 유저나 빵집이 없습니다.
    </p>
  </section>
</template>

<style scoped>
.ts-profile-search {
  max-width: 48rem;
  margin: 0 auto;
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.92);
  border: 4px solid #d2691e;
  border-radius: 1.25rem;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
}

.ts-search-header {
  margin-bottom: 1rem;
}

.ts-search-title {
  margin: 0 0 0.5rem;
  color: #d2691e;
  font-weight: 900;
  font-size: 1.6rem;
}

.ts-search-subtitle {
  margin: 0;
  color: #8b4513;
  font-weight: 700;
  font-size: 0.95rem;
}

.ts-search-form {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.ts-search-input {
  flex: 1;
  padding: 0.75rem 0.9rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(0, 0, 0, 0.18);
  font-size: 1rem;
}

.ts-search-btn {
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  border: 2px solid #d2691e;
  background: #ff69b4;
  color: #fff;
  font-weight: 900;
  cursor: pointer;
}

.ts-search-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.ts-search-error {
  margin: 0.25rem 0 0;
  color: #b00020;
  font-weight: 700;
  font-size: 0.9rem;
}

.ts-result-block {
  margin-top: 1.25rem;
}

.ts-result-title {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
  font-weight: 800;
  color: #8b4513;
}

.ts-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
}

.ts-result-card {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.7rem;
  border-radius: 0.8rem;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: #fffaf3;
  cursor: pointer;
  transition:
    transform 0.08s ease,
    box-shadow 0.12s ease,
    border-color 0.12s ease;
}

.ts-result-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  border-color: #f0b878;
}

.ts-result-thumb {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  overflow: hidden;
  background: #ffe7c2;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ts-result-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ts-result-body {
  flex: 1;
  min-width: 0;
}

.ts-result-name {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 800;
  color: #5a3414;
}

.ts-result-sub {
  margin: 0.1rem 0 0;
  font-size: 0.8rem;
  color: #8b4513;
  opacity: 0.8;
}

.ts-search-empty {
  margin-top: 1rem;
  color: #8b4513;
  font-weight: 600;
  font-size: 0.9rem;
}
</style>
