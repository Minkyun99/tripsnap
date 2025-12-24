<!-- src/components/Banner.vue -->
<script setup>
import { ref, computed, onMounted, nextTick, Teleport } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/users'
import { useProfileStore } from '@/stores/profile'

const router = useRouter()
const userStore = useUserStore()
const profileStore = useProfileStore()

// 드롭다운 토글 상태
const isMenuOpen = ref(false)

// 프로필 아바타 DOM 참조
const avatarRef = ref(null)

// 드롭다운 위치 (뷰포트 기준)
const menuPosition = ref({
  top: 0,
  left: 0,
})

onMounted(async () => {
  // 새로고침/최초 진입 시 세션 동기화
  try {
    if (!userStore.user) {
      await userStore.fetchMe()
    }
  } catch {
    // 인증 안 된 상태 등은 무시
  }

  // 로그인 상태면 내 프로필(이미지) 로드
  if (userStore.isAuthenticated) {
    try {
      await profileStore.loadMyProfile()
    } catch {
      // 프로필이 없어도 배너는 동작하게
    }
  }
})

const isAuthenticated = computed(() => userStore.isAuthenticated)

// 프로필 이니셜 (닉네임/아이디/이메일 첫 글자)
const displayInitial = computed(() => {
  const u = userStore.user
  if (!u) return ''
  const base = u.nickname || u.username || u.email || ''
  return base ? base[0].toUpperCase() : ''
})

// 프로필 이미지 URL (없으면 빈 문자열)
const profileImageUrl = computed(() => profileStore.myProfileImgUrl || '')

const closeMenu = () => {
  isMenuOpen.value = false
}

// 아바타 바로 아래에 메뉴를 열도록 위치 계산
const openMenuAtAvatar = async () => {
  if (!avatarRef.value) {
    isMenuOpen.value = true
    return
  }

  await nextTick()
  const rect = avatarRef.value.getBoundingClientRect()

  // 아바타 가로 중앙 아래쪽 기준
  menuPosition.value = {
    top: rect.bottom + 8,                        // 아바타 아래로 8px 띄우기
    left: rect.left + rect.width / 2,           // 아바타 중앙 x 좌표
  }

  isMenuOpen.value = true
}

const toggleMenu = () => {
  if (isMenuOpen.value) {
    closeMenu()
  } else {
    openMenuAtAvatar()
  }
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

// 🔍 검색 페이지로 이동
const goSearch = () => {
  router.push({ name: 'profile-search' })
  closeMenu()
}

// 💬 챗봇 화면으로 이동
const goChatbot = () => {
  router.push({ name: 'chatbot' })
  closeMenu()
}

// 👤 내 프로필로 이동
const goProfile = () => {
  router.push({ name: 'profile' })
  closeMenu()
}

// 🚪 로그아웃
const handleLogout = async () => {
  await userStore.logout()
  closeMenu()
  router.push({ name: 'home' })
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
          <!-- 💬 챗봇 버튼 -->
          <button
            type="button"
            class="ts-icon-btn pixel-corners"
            @click="goChatbot"
            title="챗봇 대화"
          >
            <span class="ts-icon-btn__icon">💬</span>
            <span class="ts-icon-btn__label">챗봇 대화</span>
          </button>

          <!-- 🔍 검색 버튼 -->
          <button
            type="button"
            class="ts-icon-btn pixel-corners"
            @click="goSearch"
            title="빵지순례 검색"
          >
            <span class="ts-icon-btn__icon">🔍</span>
            <span class="ts-icon-btn__label">검색</span>
          </button>

          <!-- 👤 프로필 아바타 버튼 (동그란 이미지) -->
          <div class="ts-profile-wrap" ref="avatarRef">
            <button
              type="button"
              class="ts-profile-btn"
              @click="toggleMenu"
              aria-label="프로필 메뉴 열기"
            >
              <span class="ts-profile-avatar">
                <!-- 프로필 이미지가 있으면 이미지 사용 -->
                <img
                  v-if="profileImageUrl"
                  :src="profileImageUrl"
                  alt="프로필 이미지"
                />
                <!-- 없으면 이니셜 -->
                <span
                  v-else-if="displayInitial"
                  class="ts-profile-initial"
                >
                  {{ displayInitial }}
                </span>
                <!-- 이니셜도 없으면 기본 이모지 -->
                <span
                  v-else
                  class="ts-profile-emoji"
                >
                  🍞
                </span>
              </span>
            </button>
          </div>

          <!-- 드롭다운 메뉴 (Teleport → body) -->
          <Teleport to="body">
            <div
              v-if="isMenuOpen"
              class="ts-profile-menu-layer"
              @click.self="closeMenu"
            >
              <div
                class="ts-profile-menu pixel-corners"
                :style="{
                  top: menuPosition.top + 'px',
                  left: menuPosition.left + 'px',
                }"
              >
                <button
                  type="button"
                  class="ts-profile-menu__item"
                  @click="goProfile"
                >
                  내 프로필
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

<style lang="scss" scoped>
@import '../assets/styles/banner.scss';
</style>
