<!-- src/views/LoginView.vue -->
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'

const router = useRouter()
const userStore = useUserStore()

const email = ref('')
const password = ref('')
const errorMessage = ref('')

const handleSubmit = async () => {
  errorMessage.value = ''
  try {
    await userStore.login({ email: email.value, password: password.value })
    router.push({ name: 'home' })
  } catch (e) {
    errorMessage.value = userStore.error || '로그인에 실패했습니다.'
  }
}

const handleKakaoLogin = () => {
  userStore.startKakaoLogin()
}
</script>

<template>
  <div class="login-page">
    <h2>로그인</h2>

    <form @submit.prevent="handleSubmit" class="login-form">
      <div v-if="errorMessage" class="error">
        {{ errorMessage }}
      </div>

      <div class="field">
        <label for="email">이메일</label>
        <input id="email" v-model="email" type="email" autocomplete="email" required />
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

      <button type="submit" :disabled="userStore.isLoading">
        <span v-if="userStore.isLoading">로그인 중...</span>
        <span v-else>이메일로 로그인</span>
      </button>
    </form>

    <hr />

    <button type="button" @click="handleKakaoLogin">카카오로 로그인</button>
  </div>
</template>
