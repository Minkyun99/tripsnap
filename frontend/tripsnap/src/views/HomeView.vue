<!-- src/views/HomeView.vue -->
<script setup>
import { computed, watch } from 'vue'
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
  router.push({ name: 'profile-detail', params: { nickname } })
}

// ✅ 추천 빵집 목록 & 로딩 상태는 Pinia(userStore)에서 가져옴
const recommendedBakeries = computed(() => userStore.recommendedBakeries)
const isLoadingRecommended = computed(
  () => userStore.isLoadingRecommendedBakeries,
)

// 카드 클릭 → Pinia bakeryStore를 통해 모달 오픈 (ID 기준, 상세 재조회)
const openBakeryModal = async (bakery) => {
  if (!bakery || !bakery.id) {
    console.error('추천 베이커리 ID 없음:', bakery)
    return
  }

  try {
    await bakeryStore.openModalById(bakery.id, { loadComments: true })
  } catch (err) {
    console.error('추천 베이커리 모달 오픈 중 오류:', err)
  }
}

/**
 * ✅ 인증 상태를 감시해서:
 *  - 로그인 완료 시마다 fetchRecommendedBakeries 호출
 *  - 이미 로그인된 상태에서 새로고침해도 즉시 한 번 호출 (immediate: true)
 */
watch(
  () => isAuthenticated.value,
  async (authed) => {
    if (!authed) {
      // 로그아웃 상태에서는 목록 비워두기 (선택 사항)
      userStore.recommendedBakeries = []
      return
    }

    // 로그인된 상태 → 추천 목록 로드 (랜덤 5개)
    await userStore.fetchRecommendedBakeries({ maxCount: 5 })
  },
  { immediate: true },
)
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
          최근 활동과 취향을 바탕으로 TripSnap이 고른 추천 빵집이에요.
        </p>

        <div class="home-reco-list">
          <button
            v-for="(b, idx) in recommendedBakeries"
            :key="b.id"
            type="button"
            class="bakery-button"
            @click="openBakeryModal(b)"
          >
            <div class="bakery-number">{{ idx + 1 }}</div>
            <div class="bakery-info">
              <div class="bakery-name">
                {{ b.name }}
                <span
                  v-if="b.rate !== null && b.rate !== undefined"
                  class="bakery-rating"
                >
                  ⭐ {{
                    typeof b.rate === 'number'
                      ? b.rate.toFixed(1)
                      : b.rate
                  }}
                </span>
              </div>

              <div class="bakery-location">
                📍
                <span v-if="b.district">대전 {{ b.district }}</span>
                <span v-if="b.district && b.road_address"> | </span>
                <span
                  v-if="b.road_address"
                  class="bakery-address"
                >
                  {{ b.road_address }}
                </span>
              </div>
            </div>
          </button>
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
  margin: 0 0 1.25rem;
  font-size: 0.9rem;
  color: #6b7280;
}

/* 추천 리스트 컨테이너: Chatbot의 빵집 리스트와 유사한 vertical 리스트 */
.home-reco-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

/* 🥐 ChatbotView의 bakery-button 느낌 재현 */
.bakery-button {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  background: white;
  border: 2px solid $ts-border-brown;
  border-radius: 0.75rem;
  padding: 0.85rem 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;

  &:hover {
    background: #fffaf0;
    transform: translateX(4px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  &:active {
    transform: translateX(2px);
  }
}

.bakery-number {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  background: $ts-border-brown;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.9rem;
}

.bakery-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
}

.bakery-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: $ts-text-brown;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.bakery-rating {
  font-size: 0.85rem;
  color: #f59e0b;
}

.bakery-location {
  font-size: 0.85rem;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bakery-address {
  color: #9ca3af;
}

.home-reco-empty {
  text-align: center;
}

.home-reco-desc {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  color: $ts-text-brown;
}
</style>
