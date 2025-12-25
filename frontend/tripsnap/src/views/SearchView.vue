<!-- src/views/SearchView.vue -->
<template>
  <main class="ts-search-page">
    <div class="ts-shell ts-stack">
      <section class="ts-card pixel-corners ts-search-card">
        <h2 class="ts-search-title">검색</h2>

        <!-- 검색 바 -->
        <div class="ts-search-bar">
          <input
            v-model="searchQ"
            class="ts-input ts-search-input"
            type="text"
            placeholder="닉네임, 사용자 이름 또는 빵집 이름으로 검색하세요"
            @keydown.enter.prevent="handleSubmit"
          />
          <button
            class="ts-btn ts-btn--pink"
            type="button"
            :disabled="isSearching"
            @click="handleSubmit"
          >
            {{ isSearching ? '검색 중...' : '검색' }}
          </button>
        </div>

        <!-- 에러/안내 메시지 -->
        <p v-if="errorMsg" class="ts-search-error">
          {{ errorMsg }}
        </p>

        <!-- 검색 결과 -->
        <div class="ts-search-results" v-if="hasAnyResult">
          <!-- 유저 결과 -->
          <section v-if="userResults.length" class="ts-search-section">
            <h3 class="ts-search-section-title">유저</h3>
            <div class="ts-search-grid">
              <article
                v-for="u in userResults"
                :key="u.nickname || u.username"
                class="ts-search-card-item"
                @click="goProfile(u.nickname)"
              >
                <div class="ts-search-avatar">
                  <img v-if="u.profile_img" :src="u.profile_img" alt="user profile" />
                  <div v-else class="ts-search-avatar-placeholder">🍞</div>
                </div>
                <div class="ts-search-card-body">
                  <h4 class="ts-search-card-title">
                    {{ u.nickname || '(닉네임 없음)' }}
                  </h4>
                  <p class="ts-search-card-sub">@{{ u.username }}</p>
                </div>
              </article>
            </div>
          </section>

          <!-- 빵집 결과 -->
          <section v-if="bakeryResults.length" class="ts-search-section">
            <h3 class="ts-search-section-title">빵집</h3>
            <div class="ts-search-grid">
              <article
                v-for="b in bakeryResults"
                :key="b.id"
                class="ts-search-card-item"
                @click="openBakeryModal(b.id)"
              >
                <div class="ts-search-avatar ts-search-avatar--bakery">
                  <!-- 빵집은 기본 아이콘만 사용 -->
                  🥐
                </div>
                <div class="ts-search-card-body">
                  <h4 class="ts-search-card-title">
                    {{ b.name }}
                  </h4>
                  <p class="ts-search-card-sub">
                    {{ b.district || '지역 정보 없음' }}
                  </p>
                  <p class="ts-search-card-meta">
                    {{ b.road_address || b.jibun_address || '주소 정보 없음' }}
                  </p>
                  <p class="ts-search-card-meta">
                    평점: {{ b.rate ?? 'N/A' }} · 좋아요 {{ b.like_count ?? 0 }}
                  </p>
                </div>
              </article>
            </div>
          </section>
        </div>

        <!-- 검색 결과 없음 -->
        <div v-else-if="!isSearching && searchQ.trim()" class="ts-search-empty">
          일치하는 유저나 빵집을 찾지 못했습니다.
        </div>

        <!-- 초기 상태 (검색 전) -->
        <div v-else-if="!searchQ.trim() && !isSearching" class="ts-search-empty">
          검색어를 입력하고 엔터를 눌러주세요.
        </div>
      </section>
    </div>

    <!-- 빵집 모달 -->
    <BakeryModal v-if="bakeryStore.modalOpen" @close="bakeryStore.modalOpen = false" />
  </main>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useProfileStore } from '@/stores/profile'
import { useBakeryStore } from '@/stores/bakery'
import BakeryModal from '@/views/BakeryModal.vue' // 실제 경로에 맞게 조정 필요

const API_BASE = import.meta.env.VITE_API_BASE || ''

const router = useRouter()
const profileStore = useProfileStore()
const bakeryStore = useBakeryStore()

const searchQ = ref('')
const isSearching = ref(false)
const errorMsg = ref('')

// 결과 리스트
const userResults = ref([]) // [{ nickname, username, profile_img }, ...]
const bakeryResults = ref([]) // BakeryListSerializer 결과

const hasAnyResult = computed(() => userResults.value.length > 0 || bakeryResults.value.length > 0)

/**
 * 유저 + 빵집 통합 검색
 */
async function handleSubmit() {
  const q = searchQ.value.trim()
  if (!q) {
    errorMsg.value = '검색어를 입력해주세요.'
    userResults.value = []
    bakeryResults.value = []
    return
  }

  isSearching.value = true
  errorMsg.value = ''
  userResults.value = []
  bakeryResults.value = []

  try {
    // 1) 유저 검색 (기존 suggestProfiles 활용)
    try {
      const users = await profileStore.suggestProfiles(q)
      // suggestProfiles는 store 내부 상태도 업데이트하지만,
      // 여기서는 반환값을 로컬에 저장해서 사용합니다.
      userResults.value = Array.isArray(users) ? users : []
    } catch (e) {
      console.error('유저 검색 오류:', e)
      // 유저 쪽 오류는 치명적이지 않으므로, 메시지만 기록
    }

    // 2) 빵집 검색 (/chatbot/bakery/?search=)
    try {
      const url = `${API_BASE}/chatbot/bakery/?search=${encodeURIComponent(q)}`
      const res = await fetch(url, {
        credentials: 'include',
      })

      if (!res.ok) {
        console.error('빵집 검색 실패:', res.status, await res.text())
      } else {
        const data = await res.json()
        // 배열 / {results: []} / {bakeries: []} 모두 대응
        const list = Array.isArray(data) ? data : data.results || data.bakeries || []
        bakeryResults.value = list
      }
    } catch (e) {
      console.error('빵집 검색 오류:', e)
    }

    if (!hasAnyResult.value) {
      errorMsg.value = '일치하는 유저나 빵집을 찾지 못했습니다.'
    }
  } finally {
    isSearching.value = false
  }
}

/**
 * 유저 카드 클릭 → 해당 유저 프로필 페이지로 이동
 */
function goProfile(nickname) {
  if (!nickname) return
  router.push({ name: 'profile-detail', params: { nickname } }).catch(() => {})
}

/**
 * 빵집 카드 클릭 → BakeryModal 오픈
 */
async function openBakeryModal(bakeryId) {
  if (!bakeryId) return
  await bakeryStore.openModalById(bakeryId, { loadComments: true })
}
</script>

<style scoped lang="scss">
.ts-search-page {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  padding: 2rem 1rem;
}

.ts-search-card {
  max-width: 960px;
  margin: 0 auto;
}

.ts-search-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 1rem;
}

.ts-search-bar {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.ts-search-input {
  flex: 1;
}

.ts-search-error {
  margin: 0.25rem 0 0.5rem;
  font-size: 0.85rem;
  color: #b00020;
  font-weight: 600;
}

.ts-search-results {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.ts-search-section-title {
  font-size: 1rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.ts-search-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 0.75rem;
}

.ts-search-card-item {
  display: flex;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: #fffdf7;
  cursor: pointer;
  transition:
    transform 0.12s ease-out,
    box-shadow 0.12s ease-out,
    border-color 0.12s ease-out;
}

.ts-search-card-item:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.06);
  border-color: #ffd2a3;
}

.ts-search-avatar {
  width: 48px;
  height: 48px;
  border-radius: 999px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff2dc;
  flex-shrink: 0;
}

.ts-search-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ts-search-avatar-placeholder {
  font-size: 1.6rem;
  line-height: 1;
}

.ts-search-avatar--bakery {
  font-size: 1.8rem;
}

.ts-search-card-body {
  flex: 1;
  min-width: 0;
}

.ts-search-card-title {
  font-size: 0.95rem;
  font-weight: 700;
  margin-bottom: 0.15rem;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.ts-search-card-sub {
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 0.25rem;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.ts-search-card-meta {
  font-size: 0.78rem;
  color: #999;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.ts-search-empty {
  margin-top: 1.5rem;
  text-align: center;
  font-size: 0.9rem;
  color: #777;
}
</style>
