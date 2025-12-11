<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'

const router = useRouter()
const userStore = useUserStore()

const email = ref('')
const password1 = ref('')
const password2 = ref('')

const errorMessage = ref('')
const fieldErrors = ref({})

const validate = () => {
  errorMessage.value = ''
  fieldErrors.value = {}

  if (!email.value) {
    fieldErrors.value.email = '이메일을 입력해주세요.'
  }

  if (!password1.value || !password2.value) {
    fieldErrors.value.password = '비밀번호를 모두 입력해주세요.'
  } else if (password1.value !== password2.value) {
    fieldErrors.value.password = '비밀번호가 서로 일치하지 않습니다.'
  }

  return Object.keys(fieldErrors.value).length === 0
}

const handleSignup = async () => {
  if (!validate()) return

  try {
    await userStore.register({
      email: email.value,
      password1: password1.value,
      password2: password2.value,
    })
    // 가입 & 로그인 성공 후 메인으로 이동
    router.push({ name: 'home' })
  } catch (e) {
    errorMessage.value = userStore.error || '회원가입에 실패했습니다.'
  }
}

const handleKakaoSignup = () => {
  // 카카오 연동은 로그인과 동일하게 사용
  userStore.startKakaoLogin()
}
</script>

<template>
  <div class="signup-page">
    <h2 class="signup-title">회원가입</h2>

    <form @submit.prevent="handleSignup" class="signup-form">
      <!-- 서버/공통 에러 -->
      <div v-if="errorMessage" class="signup-error">
        {{ errorMessage }}
      </div>

      <!-- email -->
      <div class="field">
        <label for="email">이메일</label>
        <input id="email" v-model="email" type="email" autocomplete="email" required />
        <p v-if="fieldErrors.email" class="field-error">
          {{ fieldErrors.email }}
        </p>
      </div>

      <!-- password1 -->
      <div class="field">
        <label for="password1">비밀번호</label>
        <input
          id="password1"
          v-model="password1"
          type="password"
          autocomplete="new-password"
          required
        />
      </div>

      <!-- password2 -->
      <div class="field">
        <label for="password2">비밀번호 확인</label>
        <input
          id="password2"
          v-model="password2"
          type="password"
          autocomplete="new-password"
          required
        />
        <p v-if="fieldErrors.password" class="field-error">
          {{ fieldErrors.password }}
        </p>
      </div>

      <button type="submit" class="signup-submit" :disabled="userStore.isLoading">
        <span v-if="userStore.isLoading">가입 처리 중...</span>
        <span v-else>이메일로 가입하기</span>
      </button>
    </form>

    <hr class="signup-divider" />

    <div class="social-signup">
      <p>또는</p>
      <button type="button" class="kakao-button" @click="handleKakaoSignup">
        카카오톡으로 간편 가입 / 로그인
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.signup-page {
  max-width: 420px;
  margin: 2rem auto;
  padding: 2rem 1.5rem;
  background: #fffdf8;
  border-radius: 0.75rem;
  border: 2px solid #ffd09b;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.06);
}

.signup-title {
  margin: 0 0 1.5rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: #d2691e;
  text-align: center;
}

.signup-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

label {
  font-size: 0.9rem;
  font-weight: 600;
  color: #8b4513;
}

input {
  padding: 0.55rem 0.6rem;
  font-size: 0.95rem;
  border-radius: 0.4rem;
  border: 1px solid #d9b38c;
  outline: none;
}

input:focus {
  border-color: #d2691e;
  box-shadow: 0 0 0 1px rgba(210, 105, 30, 0.2);
}

.signup-submit {
  margin-top: 0.5rem;
  padding: 0.6rem;
  font-size: 0.95rem;
  font-weight: 700;
  border-radius: 0.5rem;
  border: 2px solid #d2691e;
  background-color: #d2691e;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.signup-submit:disabled {
  opacity: 0.7;
  cursor: default;
}

.signup-submit:not(:disabled):hover {
  background-color: #8b4513;
}

.signup-error {
  background: #ffe6e6;
  color: #b00020;
  border-radius: 0.5rem;
  padding: 0.5rem 0.6rem;
  font-size: 0.85rem;
}

.field-error {
  font-size: 0.8rem;
  color: #b00020;
}

.signup-divider {
  margin: 1.5rem 0 1rem;
  border: none;
  border-top: 1px solid #f0d3a0;
}

.social-signup {
  text-align: center;
  font-size: 0.9rem;
  color: #8b4513;
}

.kakao-button {
  margin-top: 0.5rem;
  width: 100%;
  padding: 0.6rem;
  font-size: 0.95rem;
  font-weight: 700;
  border-radius: 0.5rem;
  border: none;
  cursor: pointer;
  background-color: #fee500;
  color: #3c1e1e;
  box-shadow: 0 3px 0 #c4a300;
  transition:
    transform 0.07s ease,
    box-shadow 0.07s ease;
}

.kakao-button:hover {
  transform: translateY(1px);
  box-shadow: 0 1px 0 #c4a300;
}
</style>
