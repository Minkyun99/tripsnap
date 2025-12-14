<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/users'

const router = useRouter()
const userStore = useUserStore()

onMounted(() => {
  // 새로고침/최초 진입 시 세션 동기화
  if (!userStore.user) userStore.fetchMe()
})

const isAuthenticated = computed(() => userStore.isAuthenticated)

const displayName = computed(() => {
  const u = userStore.user
  if (!u) return ''
  return u.nickname || u.username || u.email || ''
})

const goHome = () => router.push({ name: 'home' })
const goLogin = () => router.push({ name: 'login' })
const goSignup = () => router.push({ name: 'signup' })

// ✅ 검색 페이지로 이동
const goSearch = () => router.push({ name: 'profile-search' })

// ✅ 본인 프로필로 이동
const goProfile = () => router.push({ name: 'profile' })

const handleLogout = async () => {
  await userStore.logout()
  // 필요하면 홈으로
  router.push({ name: 'home' })
}
</script>

<template>
  <header class="ts-header pixel-corners">
    <div class="ts-header__inner">
      <button type="button" class="ts-logo" @click="goHome">
        <div class="ts-logo__icon">🍞</div>
        <div class="ts-logo__text">
          <h1 class="ts-logo__title">tripsnap</h1>
          <p class="ts-logo__subtitle">🍞 AI 빵집 추천 서비스</p>
        </div>
      </button>

      <div class="ts-header__actions">
        <template v-if="isAuthenticated">
          <p class="ts-header__welcome">
            환영합니다, <span class="ts-header__welcome-name">{{ displayName }}</span> 님
          </p>

          <button type="button" class="ts-btn ts-btn--ghost" @click="goSearch">검색</button>
          <button type="button" class="ts-btn ts-btn--primary" @click="goProfile">프로필</button>
          <button type="button" class="ts-btn ts-btn--ghost" @click="handleLogout">로그아웃</button>
        </template>

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

.ts-header {
  background-color: $ts-header-bg;
  border-bottom: 4px solid $ts-border-brown;
  padding: 1.5rem;
}
.ts-header__inner {
  max-width: 72rem;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
}
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
.ts-header__actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.ts-header__welcome {
  color: $ts-text-brown;
  font-weight: 600;
  margin: 0;
}
.ts-header__welcome-name {
  color: $ts-border-brown;
}

.ts-btn {
  border-radius: 0.5rem;
  padding: 0.5rem 1.2rem;
  font-size: 0.875rem;
  font-weight: 700;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}
.ts-btn--primary {
  background-color: $ts-border-brown;
  color: #fff;
  border-color: color.adjust($ts-border-brown, $lightness: -10%);
  &:hover {
    background-color: color.adjust($ts-border-brown, $lightness: -10%);
  }
}
.ts-btn--ghost {
  background-color: #fff;
  color: $ts-border-brown;
  border-color: $ts-border-brown;
  &:hover {
    background-color: #ffe8cc;
  }
}

@media (max-width: 640px) {
  .ts-header__welcome {
    display: none;
  }
}
</style>
