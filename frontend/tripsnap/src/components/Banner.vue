<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'

const router = useRouter()
const userStore = useUserStore()

// 최초 진입 시 세션 기반 로그인 상태 동기화
onMounted(() => {
  if (!userStore.user) {
    userStore.fetchMe?.() // fetchMe가 구현되어 있다면 호출
  }
})

// 로그인 여부
const isAuthenticated = computed(() => userStore.isAuthenticated)

// 표시용 이름: nickname > username > email
const displayName = computed(() => {
  const u = userStore.user
  if (!u) return ''
  return u.nickname || u.username || u.email || ''
})

const goHome = () => router.push({ name: 'home' })
const goProfile = () => router.push({ name: 'profile' })
const goLogin = () => router.push({ name: 'login' })
const goSignup = () => router.push({ name: 'signup' })

const handleLogout = async () => {
  if (userStore.logout) {
    await userStore.logout()
  }
  router.push({ name: 'home' })
}
</script>

<template>
  <header class="ts-header pixel-corners">
    <div class="ts-header__inner">
      <!-- 왼쪽: 로고 + 서브 타이틀 -->
      <button type="button" class="ts-logo" @click="goHome">
        <div class="ts-logo__icon bread-float">🍞</div>
        <div class="ts-logo__text">
          <h1 class="ts-logo__title">tripsnap</h1>
          <p class="ts-logo__subtitle">🍞 AI 빵집 추천 서비스</p>
        </div>
      </button>

      <!-- 오른쪽: 로그인 상태에 따른 분기 -->
      <div class="ts-header__actions">
        <!-- 로그인 상태 -->
        <template v-if="isAuthenticated">
          <p class="ts-header__welcome">
            환영합니다,
            <span class="ts-header__welcome-name">{{ displayName }}</span>
            님 🎉
          </p>

          <button type="button" class="ts-btn ts-btn--primary" @click="goProfile">내 프로필</button>

          <button type="button" class="ts-btn ts-btn--ghost" @click="handleLogout">로그아웃</button>
        </template>

        <!-- 비로그인 상태 -->
        <template v-else>
          <button type="button" class="ts-btn ts-btn--primary" @click="goLogin">로그인</button>

          <button type="button" class="ts-btn ts-btn--ghost" @click="goSignup">회원가입</button>
        </template>
      </div>
    </div>
  </header>
</template>

<style scoped lang="scss">
@use 'sass:color';

$ts-header-bg: #ffe8cc;
$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;

/* 헤더 전체 영역 */
.ts-header {
  background-color: $ts-header-bg;
  border-bottom: 4px solid $ts-border-brown;
  padding: 1.5rem;
}

/* 헤더 안쪽 컨테이너 */
.ts-header__inner {
  max-width: 72rem; // 1152px
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
}

/* 로고 영역 (홈 버튼 역할) */
.ts-logo {
  display: flex;
  align-items: center;
  gap: 1rem;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-align: left;
}

.ts-logo__icon {
  font-size: 2.5rem;
}

.ts-logo__title {
  font-size: 2rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin: 0;
}

.ts-logo__subtitle {
  margin: 0.15rem 0 0;
  color: $ts-text-brown;
  font-weight: 600;
}

/* 오른쪽 버튼 영역 */
.ts-header__actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* 환영 문구 */
.ts-header__welcome {
  color: $ts-text-brown;
  font-weight: 600;
  margin: 0;
}

.ts-header__welcome-name {
  color: $ts-border-brown;
}

/* 공통 버튼 스타일 */
.ts-btn {
  border-radius: 0.5rem;
  padding: 0.5rem 1.2rem;
  font-size: 0.875rem;
  font-weight: 700;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

/* 메인(진한) 버튼 */
.ts-btn--primary {
  background-color: $ts-border-brown;
  color: #fff;
  border-color: color.adjust($ts-border-brown, $lightness: -10%);

  &:hover {
    background-color: color.adjust($ts-border-brown, $lightness: -10%);
  }
}

/* 흰색 테두리 버튼 */
.ts-btn--ghost {
  background-color: #fff;
  color: $ts-border-brown;
  border-color: $ts-border-brown;

  &:hover {
    background-color: #ffe8cc;
  }
}

/* 모바일에서 환영 문구는 숨김 */
@media (max-width: 640px) {
  .ts-header__welcome {
    display: none;
  }
}
</style>
