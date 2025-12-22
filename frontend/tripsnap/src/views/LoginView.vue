<!-- src/views/LoginView.vue -->
<script setup>
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'

const router = useRouter()
const userStore = useUserStore()

const email = ref('')
const password = ref('')
const errorMessage = ref('')

// 이메일 인풋 포커스를 위한 ref
const emailInput = ref(null)

const handleSubmit = async () => {
  errorMessage.value = ''

  // 선택: 빈 값 방어
  if (!email.value || !password.value) {
    errorMessage.value = '이메일과 비밀번호를 모두 입력해주세요.'
    return
  }

  const ok = await userStore.login({ email: email.value, password: password.value })

  // ✅ 로그인 실패: 페이지 유지 + 경고문구 + 입력값 초기화
  if (!ok) {
    errorMessage.value = userStore.error || '아이디 또는 비밀번호가 올바르지 않습니다.'

    // 입력값 초기화
    email.value = ''
    password.value = ''

    // 이메일 인풋에 포커스
    await nextTick()
    if (emailInput.value) {
      emailInput.value.focus()
    }
    return
  }

  // ✅ 로그인 성공 시 메인으로 이동
  router.push('/')
}

const handleKakaoLogin = () => {
  userStore.startKakaoLogin()
}
</script>

<template>
  <div class="login-page">
    <div class="login-card pixel-corners">
      <h2 class="login-title">로그인</h2>
      <p class="login-desc">계정으로 로그인하거나 소셜 계정을 사용할 수 있습니다.</p>

      <!-- 카카오 로그인 버튼 -->
      <button type="button" class="kakao-btn" @click="handleKakaoLogin">
        <img
          class="kakao-logo"
          src="https://developers.kakao.com/assets/img/about/logos/kakaolink/kakaolink_btn_small.png"
          alt="kakao-logo"
        />
        카카오로 3초 로그인
      </button>

      <!-- 구분선 -->
      <div class="divider">
        <span class="divider-line"></span>
        <span class="divider-text">또는</span>
        <span class="divider-line"></span>
      </div>

      <!-- 이메일 로그인 폼 -->
      <form @submit.prevent="handleSubmit" class="login-form">
        <div v-if="errorMessage" class="error">
          {{ errorMessage }}
        </div>

        <div class="field">
          <label for="email">이메일</label>
          <input
            id="email"
            ref="emailInput"
            v-model="email"
            type="email"
            autocomplete="email"
            required
          />
        </div>

        <div class="field">
          <label for="password">비밀번호</label>
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
          />
        </div>

        <button class="primary-btn" type="submit" :disabled="userStore.isLoading">
          <span v-if="userStore.isLoading">로그인 중...</span>
          <span v-else>로그인</span>
        </button>
      </form>

      <p class="signup-text">
        아직 계정이 없으신가요?
        <router-link class="signup-link" :to="{ name: 'signup' }">회원가입</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'sass:color';

$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;
$ts-pink: #ff69b4;
$ts-pink-hover: #ff1493;
$ts-kakao: #fee500;
$ts-kakao-text: #3c1e1e;

.login-page {
  /* Layout.vue 내부에서 이미 배경을 깔고 있을 수 있어도 안전하게 동작 */
  min-height: calc(100vh - 160px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 2.5rem 1rem;
}

.login-card {
  width: 100%;
  max-width: 28rem; /* max-w-md */
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 1rem; /* rounded-2xl 느낌 */
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.12);
  padding: 2rem;
  border: 4px solid $ts-border-brown;
}

.login-title {
  font-size: 1.875rem; /* text-3xl */
  font-weight: 800; /* font-extrabold */
  text-align: center;
  color: $ts-border-brown;
  margin: 0 0 0.75rem;
}

.login-desc {
  text-align: center;
  color: #6b7280; /* gray-600 */
  margin: 0 0 1.25rem;
  font-size: 0.95rem;
  line-height: 1.5;
}

/* 에러 박스 */
.error {
  margin-bottom: 1rem;
  padding: 0.75rem 0.9rem;
  border-radius: 0.6rem;
  background: #fee2e2; /* red-100 */
  color: #b91c1c; /* red-700 */
  font-size: 0.875rem;
  border: 1px solid rgba(185, 28, 28, 0.15);
}

/* 카카오 버튼 */
.kakao-btn {
  width: 100%;
  border: 0;
  cursor: pointer;

  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;

  padding: 0.85rem 1rem;
  border-radius: 0.65rem;
  font-size: 1.05rem;
  font-weight: 800;

  background: $ts-kakao;
  color: $ts-kakao-text;

  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
  box-shadow: 0 10px 0 rgba(0, 0, 0, 0.08);

  &:hover {
    transform: translateY(-1px);
  }

  &:active {
    transform: translateY(0);
    box-shadow: 0 6px 0 rgba(0, 0, 0, 0.08);
  }
}

.kakao-logo {
  width: 1.5rem;
  height: 1.5rem;
}

/* 구분선 (또는) */
.divider {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 1.25rem 0;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: #d1d5db; /* gray-300 */
}

.divider-text {
  font-size: 0.85rem;
  color: #6b7280; /* gray-500 */
  padding: 0 0.5rem;
  background: rgba(255, 255, 255, 0.9);
}

/* 폼 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;

  label {
    font-size: 0.9rem;
    font-weight: 700;
    color: $ts-text-brown;
  }

  input {
    width: 100%;
    padding: 0.75rem 0.9rem;
    border-radius: 0.6rem;
    border: 1px solid #d1d5db;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
    font-size: 0.95rem;

    &:focus {
      outline: none;
      border-color: $ts-border-brown;
      box-shadow: 0 0 0 3px rgba(210, 105, 30, 0.22);
    }
  }
}

.primary-btn {
  width: 100%;
  margin-top: 0.2rem;
  padding: 0.85rem 1rem;
  border-radius: 0.65rem;

  border: 0;
  cursor: pointer;

  background: $ts-pink;
  color: #fff;

  font-size: 1rem;
  font-weight: 800;

  transition:
    background 0.15s ease,
    transform 0.15s ease;

  &:hover {
    background: $ts-pink-hover;
    transform: translateY(-1px);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.65;
    transform: none;
  }
}

/* 회원가입 링크 */
.signup-text {
  margin-top: 1.25rem;
  text-align: center;
  font-size: 0.9rem;
  color: #6b7280; /* gray-600 */
}

.signup-link {
  color: $ts-border-brown;
  font-weight: 800;
  text-decoration: none;
  margin-left: 0.25rem;

  &:hover {
    text-decoration: underline;
  }
}
</style>
