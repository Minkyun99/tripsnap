<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'

const router = useRouter()
const userStore = useUserStore()

const isAuthenticated = computed(() => userStore.isAuthenticated)

const displayName = computed(() => {
  const u = userStore.user
  if (!u) return ''
  return u.nickname || u.username || u.email || ''
})

const goProfile = () => {
  router.push({ name: 'profile' })
}

const handleKakaoLogin = () => {
  userStore.startKakaoLogin()
}
</script>

<template>
  <div class="home-page">
    <div class="home-card pixel-corners">
      <!-- 로그인 상태 -->
      <div v-if="isAuthenticated" class="home-section home-section--logged-in">
        <div class="home-icon bread-float">🥐</div>

        <h2 class="home-title">맛있는 빵집 여행을 시작하세요!</h2>

        <p class="home-subtitle">{{ displayName }}님의 취향에 맞는 빵집을 추천합니다</p>

        <button type="button" class="home-btn-profile pixel-corners" @click="goProfile">
          내 프로필 보기
        </button>
      </div>

      <!-- 비로그인 상태 -->
      <div v-else class="home-section home-section--logged-out">
        <div class="home-icon bread-float">🥖</div>

        <h2 class="home-title">당신만을 위한 빵집을 찾아드려요!</h2>

        <p class="home-subtitle">카카오 계정으로 간편하게 로그인</p>

        <button type="button" class="home-btn-kakao pixel-corners" @click="handleKakaoLogin">
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
    </div>
  </div>
</template>

<style scoped lang="scss">
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

/* 로그인 상태 버튼 (내 프로필 보기) */
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
  box-shadow: 0 8px 0 darken(#ff69b4, 12%);
}

.home-btn-profile:hover {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 10px 0 darken(#ff69b4, 15%);
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
  box-shadow: 0 8px 0 #c4a300;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.home-btn-kakao:hover {
  transform: translateY(-2px) scale(1.03);
  box-shadow: 0 10px 0 #c4a300;
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
</style>
