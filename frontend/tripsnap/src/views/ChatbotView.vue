<!-- src/views/ChatbotView.vue -->
<script setup>
import { computed } from 'vue'
import { useUserStore } from '../stores/users'

const userStore = useUserStore()
const isAuthenticated = computed(() => userStore.isAuthenticated)
const displayName = computed(() => {
  const u = userStore.user
  if (!u) return ''
  return u.nickname || u.username || u.email || ''
})
</script>

<template>
  <div class="chatbot-page">
    <div class="chatbot-card pixel-corners">
      <h2 class="chatbot-title">🥐 빵집 추천 챗봇</h2>
      <p class="chatbot-subtitle" v-if="isAuthenticated">
        {{ displayName }} 님, 빵집/여행에 대해 무엇이든 물어보세요.
      </p>
      <p class="chatbot-subtitle" v-else>빵집 추천을 받으려면 먼저 로그인 해주세요.</p>

      <!-- 여기부터 실제 챗봇 UI 구성 예정 -->
      <div class="chatbot-placeholder">
        <p>여기에 Django /chatbot API 와 연결된 대화 UI를 붙일 예정입니다.</p>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;

.chatbot-page {
  min-height: calc(100vh - 160px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 3rem 1rem;
}

.chatbot-card {
  max-width: 48rem;
  width: 100%;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.12);
  padding: 2.5rem 2rem;
}

.chatbot-title {
  font-size: 1.8rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 0.75rem;
}

.chatbot-subtitle {
  font-size: 0.95rem;
  color: $ts-text-brown;
  margin-bottom: 1.5rem;
}

.chatbot-placeholder {
  border-radius: 0.9rem;
  border: 2px dashed rgba(139, 69, 19, 0.4);
  padding: 1.5rem;
  text-align: center;
  font-size: 0.9rem;
  color: $ts-text-brown;
}
</style>
