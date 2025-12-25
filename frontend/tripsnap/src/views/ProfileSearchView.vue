<!-- src/views/ProfileSearchView.vue -->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useProfileStore } from '../stores/profile'
import { useBakeryStore } from '@/stores/bakery'
import { useUserStore } from '@/stores/users'
import BakeryModal from './BakeryModal.vue'

const router = useRouter()
const ps = useProfileStore()
const bakeryStore = useBakeryStore()
const userStore = useUserStore()

// 통합 검색 결과 (profile.js 안에 있다고 가정)
const { searchUserResults, searchBakeryResults } = storeToRefs(ps)

const q = ref('')
const error = ref('')
const isLoading = ref(false)

// 현재 로그인한 내 닉네임
const myNickname = computed(() => {
  const fromUser = userStore.user?.nickname || userStore.user?.username || ''
  const fromProfile = ps.myProfile?.nickname || ps.profile?.nickname || ''
  return fromUser || fromProfile || ''
})

// 필요하면 내 프로필 정보를 한 번 로드해서 myNickname 보정
onMounted(async () => {
  try {
    if (!myNickname.value) {
      await ps.loadMyProfile().catch(() => {})
    }
  } catch {
    // 비로그인 등은 조용히 무시
  }
})

/**
 * 프로필 + 빵집 통합 검색
 */
async function onSubmit() {
  error.value = ''
  isLoading.value = true

  try {
    if (!q.value.trim()) {
      error.value = '검색어를 입력해주세요.'
      return
    }
    // 유저 + 베이커리 통합 검색 API (profile.js에서 구현)
    await ps.searchUsersAndBakeries(q.value)
  } catch (e) {
    error.value = e?.message || '검색 중 오류가 발생했습니다.'
  } finally {
    isLoading.value = false
  }
}

/**
 * 유저 카드 클릭 → 내 닉네임이면 /profile, 아니면 /profile-detail/:nickname
 */
function goUserProfile(nickname) {
  if (!nickname) return

  if (myNickname.value && nickname === myNickname.value) {
    // 내 계정 → 내 프로필 화면으로
    router.push({ name: 'profile' }).catch(() => {})
  } else {
    // 다른 유저 → 상세 프로필 페이지
    router.push({ name: 'profile-detail', params: { nickname } }).catch(() => {})
  }
}

/**
 * 빵집 카드 클릭 → 빵집 모달 오픈
 */
function openBakeryModal(id) {
  if (!id) return
  bakeryStore.openModalById(id)
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
        프로필 / 빵집 검색
      </h2>

      <p style="margin: 0 0 1rem; color: #8b4513; font-weight: 700">
        닉네임, 이메일 또는 빵집 이름으로 유저와 빵집을 함께 검색합니다.
      </p>

      <!-- 검색 폼 -->
      <form
        @submit.prevent="onSubmit"
        style="display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1rem"
      >
        <input
          v-model="q"
          placeholder="닉네임 / 이메일 / 빵집 이름"
          style="
            flex: 1;
            padding: 0.75rem 0.9rem;
            border-radius: 0.75rem;
            border: 1px solid rgba(0, 0, 0, 0.18);
            font-size: 1rem;
          "
          @keydown.enter.prevent="onSubmit"
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

      <!-- 검색 결과: 유저 -->
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

      <!-- 검색 결과: 빵집 -->
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
        style="margin-top: 1rem; color: #8b4513; font-weight: 600"
      >
        해당 검색어와 일치하는 유저나 빵집이 없습니다.
      </p>
    </section>

    <!-- 빵집 모달 (전역 스토어 기반) -->
    <BakeryModal v-if="bakeryStore.modalOpen" />
  </main>
</template>

<style scoped>
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
</style>
