<!-- src/components/Banner.vue -->
<script setup>
import { ref, computed, onMounted, Teleport } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/users'

// 이 컴포넌트 전용 스타일
import '@/assets/styles/banner.scss'

const router = useRouter()
const userStore = useUserStore()

const isMenuOpen = ref(false)

onMounted(() => {
  // 새로고침/최초 진입 시 세션 동기화
  if (!userStore.user) {
    userStore.fetchMe()
  }
})

const isAuthenticated = computed(() => userStore.isAuthenticated)

const displayInitial = computed(() => {
  const u = userStore.user
  if (!u) return ''
  const base = u.nickname || u.username || u.email || ''
  return base ? base[0].toUpperCase() : ''
})

const closeMenu = () => {
  isMenuOpen.value = false
}

const goHome = () => {
  router.push({ name: 'home' })
  closeMenu()
}

const goLogin = () => {
  router.push({ name: 'login' })
}

const goSignup = () => {
  router.push({ name: 'signup' })
}

// ✅ 프로필 검색(드롭다운에서 사용)
const goSearch = () => {
  router.push({ name: 'profile-search' })
  closeMenu()
}

// ✅ 챗봇 화면으로 이동 (상단 버튼용)
const goChatbot = () => {
  router.push({ name: 'chatbot' })
  closeMenu()
}

// ✅ 본인 프로필로 이동
const goProfile = () => {
  router.push({ name: 'profile' })
  closeMenu()
}

const handleLogout = async () => {
  await userStore.logout()
  closeMenu()
  router.push({ name: 'home' })
}

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}
</script>

<template>
  <header class="ts-header pixel-corners">
    <div class="ts-header__inner">
      <!-- 로고 영역 -->
      <button type="button" class="ts-logo" @click="goHome">
        <div class="ts-logo__icon">🍞</div>
        <div class="ts-logo__text">
          <h1 class="ts-logo__title">tripsnap</h1>
          <p class="ts-logo__subtitle">AI 빵집 추천 서비스</p>
        </div>
      </button>

      <!-- 우측 액션 영역 -->
      <div class="ts-header__actions">
        <!-- 로그인 상태 -->
        <template v-if="isAuthenticated">
          <!-- ✅ 상단 고정 버튼: 챗봇 대화 -->
          <button
            type="button"
            class="ts-icon-btn pixel-corners"
            @click="goChatbot"
            title="챗봇 대화"
          >
            <span class="ts-icon-btn__icon">💬</span>
            <span class="ts-icon-btn__label">챗봇 대화</span>
          </button>

          <!-- 프로필 아바타 버튼 -->
          <div class="ts-profile-wrap">
            <button
              type="button"
              class="ts-profile-btn"
              @click="toggleMenu"
              aria-label="프로필 메뉴 열기"
            >
              <span class="ts-profile-avatar pixel-corners">
                <span
                  v-if="displayInitial"
                  class="ts-profile-initial"
                >
                  {{ displayInitial }}
                </span>
                <span
                  v-else
                  class="ts-profile-emoji"
                >
                  🍞
                </span>
              </span>
            </button>
          </div>

          <!-- 드롭다운: Teleport로 body에 부착 -->
          <Teleport to="body">
            <div
              v-if="isMenuOpen"
              class="ts-profile-menu-layer"
              @click.self="closeMenu"
            >
              <div class="ts-profile-menu pixel-corners">
                <button
                  type="button"
                  class="ts-profile-menu__item"
                  @click="goProfile"
                >
                  내 프로필
                </button>
                <button
                  type="button"
                  class="ts-profile-menu__item"
                  @click="goSearch"
                >
                  빵지순례 검색
                </button>
                <button
                  type="button"
                  class="ts-profile-menu__item ts-profile-menu__item--danger"
                  @click="handleLogout"
                >
                  로그아웃
                </button>
              </div>
            </div>
          </Teleport>
        </template>

        <!-- 비로그인 상태 -->
        <template v-else>
          <button
            type="button"
            class="ts-btn pixel-corners"
            @click="goLogin"
          >
            로그인
          </button>
          <button
            type="button"
            class="ts-btn pixel-corners"
            @click="goSignup"
          >
            회원가입
          </button>
        </template>
      </div>
    </div>
  </header>
</template>