<!-- src/views/HomeView.vue -->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'
import { useBakeryStore } from '@/stores/bakery'
import BakeryModal from './BakeryModal.vue'

const router = useRouter()
const userStore = useUserStore()
const bakeryStore = useBakeryStore()

const isAuthenticated = computed(() => userStore.isAuthenticated)

const displayName = computed(() => {
  const u = userStore.user
  if (!u) return ''
  return u.nickname || u.username || u.email || ''
})

const goProfile = () => {
  router.push({ name: 'profile' })
}

const goChatbot = () => {
  router.push({ name: 'chatbot' })
}

const handleKakaoLogin = () => {
  userStore.startKakaoLogin()
}

const handleGoProfileFromModal = (nickname) => {
  // 실제 프로필 상세 라우트 이름/파라미터에 맞게 수정
  router.push({ name: 'profile-detail', params: { nickname } })
}

// API 기본 URL
const API_BASE = import.meta.env.VITE_API_BASE || ''

// 추천 베이커리 목록
const recommendedBakeries = ref([])
const isLoadingRecommended = ref(false)

// 카드 클릭 → Pinia store를 통해 모달 오픈 (ID 기준, 상세 재조회)
const openBakeryModal = async (bakery) => {
  if (!bakery || !bakery.id) {
    console.error('추천 베이커리 ID 없음:', bakery)
    return
  }

  try {
    // 위도/경도 포함된 상세 정보를 가져오고, 댓글도 함께 로드
    await bakeryStore.openModalById(bakery.id, { loadComments: true })
  } catch (err) {
    console.error('추천 베이커리 모달 오픈 중 오류:', err)
  }
}

// 추천 베이커리 로드
onMounted(async () => {
  if (!isAuthenticated.value) return

  isLoadingRecommended.value = true
  try {
    const res = await fetch(`${API_BASE}/users/api/recommended-bakeries/`, {
      credentials: 'include',
    })

    if (!res.ok) {
      console.error('추천 빵집 로드 실패:', await res.text())
      return
    }

    const data = await res.json()
    // 백엔드에서 내려주는 구조: { "results": [ ... ] }
    recommendedBakeries.value = data.results || []
  } catch (err) {
    console.error('추천 빵집 로드 중 오류:', err)
  } finally {
    isLoadingRecommended.value = false
  }
})
</script>

<template>
  <div class="home-page">
    <div class="home-card pixel-corners">
      <!-- 로그인 상태 -->
      <div v-if="isAuthenticated" class="home-section home-section--logged-in">
        <div class="home-icon bread-float">🥐</div>

        <h2 class="home-title">맛있는 빵집 여행을 시작하세요!</h2>

        <p class="home-subtitle">
          {{ displayName }}님의 취향에 맞는 빵집을 추천합니다
        </p>

        <div class="home-actions">
          <button
            type="button"
            class="home-btn-profile pixel-corners"
            @click="goProfile"
          >
            내 프로필 보기
          </button>

          <button
            type="button"
            class="home-btn-chat pixel-corners"
            @click="goChatbot"
          >
            챗봇 대화
          </button>
        </div>
      </div>

      <!-- 비로그인 상태 -->
      <div v-else class="home-section home-section--logged-out">
        <div class="home-icon bread-float">🥖</div>

        <h2 class="home-title">당신만을 위한 빵집을 찾아드려요!</h2>

        <p class="home-subtitle">카카오 계정으로 간편하게 로그인</p>

        <button
          type="button"
          class="home-btn-kakao pixel-corners"
          @click="handleKakaoLogin"
        >
          카카오로 3초 로그인
        </button>

        <div class="home-features">
          <div class="home-feature-card">
            <div class="home-feature-icon">🎯</div>
            <h4 class="home-feature-title">맞춤 추천</h4>
            <p class="home-feature-desc">AI가 당신의 취향을 분석해요</p>
          </div>

          <div class="home-feature-card">
            <div class="home-feature-icon">🗺️</div>
            <h4 class="home-feature-title">지역 탐색</h4>
            <p class="home-feature-desc">전국의 숨은 빵집을 발견해요</p>
          </div>

          <div class="home-feature-card">
            <div class="home-feature-icon">💖</div>
            <h4 class="home-feature-title">리뷰 공유</h4>
            <p class="home-feature-desc">다른 여행자와 경험을 나눠요</p>
          </div>
        </div>
      </div>

      <!-- 추천 빵집 섹션 -->
      <section
        v-if="isAuthenticated && recommendedBakeries.length"
        class="home-reco"
      >
        <h2 class="home-reco-title">이런 빵집은 어떤가요?</h2>

        <p class="home-reco-subtitle">
          최근 활동과 선호도를 바탕으로 TripSnap이 골라본 빵집이에요.
        </p>

        <div class="home-reco-list">
          <article
            v-for="b in recommendedBakeries"
            :key="b.id"
            class="home-reco-card"
            @click="openBakeryModal(b)"
          >
            <!-- 상단: 빵집 이름 + 평점 배지 -->
            <header class="home-reco-card-header">
              <h3 class="home-reco-name">
                {{ b.name }}
              </h3>
              <div class="home-reco-rating-badge" v-if="b.rate !== null && b.rate !== undefined">
                ⭐ {{ b.rate }}
              </div>
              <div class="home-reco-rating-badge rating-empty" v-else>
                평점 준비중
              </div>
            </header>

            <!-- 중단: 위치 정보 -->
            <p class="home-reco-meta">
              <span v-if="b.district">대전 {{ b.district }}</span>
              <span v-if="b.district && b.road_address"> · </span>
              <span v-if="b.road_address">{{ b.road_address }}</span>
            </p>

            <!-- 하단: 간단한 메타 정보 (카테고리, 좋아요/댓글 수) -->
            <footer class="home-reco-footer">
              <span v-if="b.category" class="home-reco-chip">
                {{ b.category }}
              </span>
              <span class="home-reco-chip" v-if="b.like_count > 0">
                ❤ {{ b.like_count }}
              </span>
              <span class="home-reco-chip" v-if="b.comment_count > 0">
                💬 {{ b.comment_count }}
              </span>
            </footer>
          </article>
        </div>
      </section>

      <!-- 로그인은 했지만 추천 없음 (예: 빵집 데이터가 아예 없거나 에러) -->
      <section
        v-else-if="isAuthenticated && !isLoadingRecommended"
        class="home-reco home-reco-empty"
      >
        <h2 class="home-reco-title">이런 빵집은 어떤가요?</h2>
        <p class="home-reco-desc">
          아직 추천할 빵집이 없어요. 먼저 빵집 관련 게시글을 올려서 취향을 알려주세요!
        </p>
      </section>
    </div>

    <!-- 공용 베이커리 모달 (Pinia 기반) -->
    <BakeryModal @go-profile="handleGoProfileFromModal" />
  </div>
</template>

<style scoped lang="scss">
@use 'sass:color';

$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;

/* 페이지 전체 컨테이너: 중앙 정렬 */
.home-page {
  min-height: calc(100vh - 160px); // 헤더/푸터 제외 대략 값
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 3rem 1rem;
}

/* 메인 카드 */
.home-card {
  max-width: 64rem; // ~max-w-4xl
  width: 100%;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.15);
  padding: 3rem;
}

/* 공통 섹션 */
.home-section {
  text-align: center;
}

.home-icon {
  font-size: 5rem; // text-9xl 느낌
  margin-bottom: 2rem;
}

.home-title {
  font-size: 2.25rem; // text-4xl
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 1rem;
}

.home-subtitle {
  font-size: 1.1rem; // text-xl 근사값
  color: $ts-text-brown;
  margin-bottom: 2.5rem;
}

/* 버튼 영역 */
.home-actions {
  display: flex;
  justify-content: center;
  gap: 1rem;
}

/* 로그인 상태: 내 프로필 버튼 */
.home-btn-profile {
  display: inline-block;
  padding: 1rem 2.5rem;
  font-size: 1.1rem;
  font-weight: 700;
  background-color: #ff69b4;
  color: #ffffff;
  border-radius: 0.85rem;
  border: 3px solid $ts-border-brown;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
  box-shadow: 0 8px 0 color.adjust(#ff69b4, $lightness: -15%, $saturation: 5%);
}

.home-btn-profile:hover {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 10px 0 color.adjust(#ff69b4, $lightness: -18%, $saturation: 5%);
}

/* 로그인 상태: 챗봇 버튼 */
.home-btn-chat {
  display: inline-block;
  padding: 1rem 2.2rem;
  font-size: 1.05rem;
  font-weight: 700;
  background-color: #ffefdb;
  color: $ts-text-brown;
  border-radius: 0.85rem;
  border: 3px solid $ts-border-brown;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
  box-shadow: 0 8px 0 color.adjust(#ffefdb, $lightness: -15%, $saturation: -5%);
}

.home-btn-chat:hover {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 10px 0 color.adjust(#ffefdb, $lightness: -18%, $saturation: -5%);
}

/* 비로그인 상태 카카오 버튼 */
.home-btn-kakao {
  display: inline-block;
  padding: 1.1rem 2.8rem;
  font-size: 1.2rem;
  font-weight: 700;
  background-color: #fee500;
  color: #3c1e1e;
  border-radius: 0.9rem;
  border: 3px solid $ts-border-brown;
  cursor: pointer;
  box-shadow: 0 8px 0 color.adjust(#c4a300, $lightness: -5%, $saturation: 5%);
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.home-btn-kakao:hover {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 10px 0 color.adjust(#c4a300, $lightness: -10%, $saturation: 5%);
}

/* 기능 카드 영역 */
.home-features {
  margin-top: 2.5rem;
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

.home-feature-card {
  background: rgba(255, 255, 255, 0.8);
  padding: 1rem;
  border-radius: 0.9rem;
  border: 2px solid $ts-border-brown;
}

.home-feature-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.home-feature-title {
  margin: 0 0 0.25rem;
  font-weight: 700;
  color: $ts-border-brown;
}

.home-feature-desc {
  margin: 0;
  font-size: 0.9rem;
  color: $ts-text-brown;
}

/* 반응형: md 이상에서 3열 */
@media (min-width: 768px) {
  .home-features {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.home-reco {
  margin-top: 3rem;
  padding: 2rem 1.5rem;
  background-color: #fff7f0;
  border-radius: 1.5rem;
  border: 1px solid $ts-border-brown;
}

.home-reco-title {
  margin: 0 0 0.5rem;
  font-size: 1.2rem;
  font-weight: 700;
  color: $ts-text-brown;
}

.home-reco-subtitle {
  margin: 0 0 1.5rem;
  font-size: 0.9rem;
  color: #6b7280;
}

.home-reco-list {
  display: grid;
  gap: 1rem;
}

.home-reco-card {
  padding: 1rem 1.2rem;
  border-radius: 1rem;
  background-color: #ffffff;
  border: 1px solid rgba(210, 105, 30, 0.35);
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease,
    background-color 0.15s ease;
}

.home-reco-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.08);
  border-color: $ts-border-brown;
  background-color: #fffdf8;
}

/* 카드 상단: 이름 + 평점 배지 */
.home-reco-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}

.home-reco-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: $ts-text-brown;
}

/* 평점 배지 */
.home-reco-rating-badge {
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  background-color: #fffbeb;
  color: #b45309;
  border: 1px solid rgba(245, 158, 11, 0.6);
}

.home-reco-rating-badge.rating-empty {
  background-color: #f3f4f6;
  color: #6b7280;
  border-color: #d1d5db;
}

/* 위치 정보 */
.home-reco-meta {
  margin: 0.1rem 0 0.6rem;
  font-size: 0.85rem;
  color: #6b7280;
}

/* 하단 메타(카테고리, 좋아요/댓글) */
.home-reco-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.3rem;
}

.home-reco-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  padding: 0.25rem 0.55rem;
  border-radius: 999px;
  border: 1px solid rgba(210, 105, 30, 0.25);
  font-size: 0.78rem;
  color: $ts-text-brown;
  background-color: #fff7f0;
}

/* 추천 없음 섹션 */
.home-reco-empty {
  margin-top: 3rem;
  padding: 2rem 1.5rem;
  background-color: #fff7f0;
  border-radius: 1.5rem;
  border: 1px solid $ts-border-brown;
  text-align: center;
}

.home-reco-desc {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  color: $ts-text-brown;
}

/* 반응형: md 이상에서 3열 */
@media (min-width: 768px) {
  .home-reco-list {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

</style>
