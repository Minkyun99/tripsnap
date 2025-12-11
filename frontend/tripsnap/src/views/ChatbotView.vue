<!-- src/views/ChatbotView.vue -->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'
import { useChatStore } from '../stores/chatbot'

const API_BASE = import.meta.env.VITE_API_BASE

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const chatStore = useChatStore()

const isAuthenticated = computed(() => userStore.isAuthenticated)
const displayName = computed(() => {
  const u = userStore.user
  if (!u) return ''
  return u.nickname || u.username || u.email || ''
})

const messages = computed(() => chatStore.messages)
const conversationId = computed(() => chatStore.conversationId)

const userInput = ref('')
const isLoading = ref(false)
const errorMessage = ref('')

onMounted(() => {
  // 키워드 선택 없이 직접 들어온 경우 → 키워드 선택 화면으로 돌려보냄
  if (!conversationId.value) {
    router.push({ name: 'chat_keywords' })
  }
})

// 실제 백엔드로 메시지 전송
const sendMessage = async () => {
  errorMessage.value = ''

  const content = userInput.value.trim()
  if (!content || !conversationId.value) return

  if (!isAuthenticated.value) {
    errorMessage.value = '챗봇을 사용하려면 먼저 로그인 해주세요.'
    return
  }

  // 사용자 메시지 화면에 추가
  chatStore.appendMessage('user', content)
  userInput.value = ''
  isLoading.value = true

  try {
    const res = await fetch(`${API_BASE}/chatbot/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        message: content,
        conversation_id: conversationId.value,
        trigger: true, // 추천 호출 강제
      }),
    })

    if (!res.ok) {
      let detail = '챗봇 서버와 통신 중 오류가 발생했습니다.'
      try {
        const data = await res.json()
        if (data.detail) detail = data.detail
      } catch {
        // ignore
      }
      throw new Error(detail)
    }

    const data = await res.json()

    const reply = data.llm_response || '응답을 받았지만 표시할 내용이 없습니다.'
    chatStore.appendMessage('bot', reply)

    // candidates(results) 리스트가 있다면, 메시지에 요약해서 붙일 수도 있습니다.
    if (Array.isArray(data.results) && data.results.length > 0) {
      const lines = ['\n추천 빵집 목록:']
      data.results.forEach((r, idx) => {
        const name = r.name || r.store_name || '이름 미상'
        const district = r.district || r.address || ''
        lines.push(`${idx + 1}. ${name} ${district && `(${district})`}`)
      })
      chatStore.appendMessage('bot', lines.join('\n'))
    }
  } catch (err) {
    console.error(err)
    errorMessage.value = err.message || '챗봇 서버와 통신 중 알 수 없는 오류가 발생했습니다.'
    chatStore.appendMessage(
      'bot',
      '죄송합니다. 지금은 잠시 응답할 수 없습니다. 잠시 후 다시 시도해 주세요.',
    )
  } finally {
    isLoading.value = false
  }
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (!isLoading.value) {
      sendMessage()
    }
  }
}
</script>

<template>
  <div class="chatbot-page">
    <div class="chatbot-card pixel-corners">
      <header class="chatbot-header">
        <div>
          <h2 class="chatbot-title">🥐 빵집 추천 챗봇</h2>
          <p class="chatbot-subtitle" v-if="isAuthenticated">
            {{ displayName }} 님, 빵집/여행에 대해 무엇이든 물어보세요.
          </p>
          <p class="chatbot-subtitle" v-else>챗봇을 사용하려면 먼저 로그인 해주세요.</p>
        </div>
      </header>

      <section class="chatbot-messages">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="chat-message"
          :class="{
            'chat-message--user': msg.role === 'user',
            'chat-message--bot': msg.role === 'bot',
          }"
        >
          <div class="chat-bubble">
            <pre class="chat-text">{{ msg.text }}</pre>
          </div>
        </div>

        <div v-if="isLoading" class="chat-loading">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      </section>

      <footer class="chatbot-input-box">
        <textarea
          v-model="userInput"
          class="chat-input"
          :placeholder="
            isAuthenticated
              ? '예: 대전 중구에 줄 서서 먹을만한 빵집 추천해줘'
              : '로그인 후 챗봇을 이용할 수 있습니다.'
          "
          :disabled="!isAuthenticated || isLoading || !conversationId"
          @keydown="handleKeydown"
        />
        <button
          type="button"
          class="chat-send-btn pixel-corners"
          :disabled="!isAuthenticated || isLoading || !userInput.trim() || !conversationId"
          @click="sendMessage"
        >
          {{ isLoading ? '전송 중...' : '전송' }}
        </button>
      </footer>

      <p v-if="errorMessage" class="chat-error">
        {{ errorMessage }}
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'sass:color';

$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;
$ts-bg-cream: #fffaf0;

/* (스타일은 앞서 사용하신 것과 동일하게 유지) */
.chatbot-page {
  min-height: calc(100vh - 160px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 2.5rem 1rem;
}

.chatbot-card {
  max-width: 52rem;
  width: 100%;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  box-shadow: 0 22px 55px rgba(0, 0, 0, 0.15);
  padding: 1.75rem 1.5rem 1.5rem;
  display: flex;
  flex-direction: column;
}

.chatbot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.chatbot-title {
  font-size: 1.6rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 0.25rem;
}

.chatbot-subtitle {
  font-size: 0.95rem;
  color: $ts-text-brown;
  margin: 0;
}

.chatbot-messages {
  flex: 1;
  min-height: 260px;
  max-height: 480px;
  overflow-y: auto;
  padding: 1rem 0.2rem;
  border-radius: 0.9rem;
  background: $ts-bg-cream;
  border: 1px solid rgba(210, 105, 30, 0.25);
}

.chat-message {
  display: flex;
  margin-bottom: 0.6rem;
}
.chat-message--user {
  justify-content: flex-end;
}
.chat-message--bot {
  justify-content: flex-start;
}

.chat-bubble {
  max-width: 80%;
  border-radius: 1rem;
  padding: 0.55rem 0.75rem;
  font-size: 0.9rem;
  line-height: 1.5;
  white-space: pre-wrap;
}
.chat-message--user .chat-bubble {
  background: #ffefdb;
  border: 1px solid rgba(210, 105, 30, 0.4);
}
.chat-message--bot .chat-bubble {
  background: #ffffff;
  border: 1px solid rgba(210, 105, 30, 0.3);
}

.chat-text {
  margin: 0;
  font-family: inherit;
}

.chatbot-input-box {
  margin-top: 1rem;
  display: flex;
  gap: 0.5rem;
}

.chat-input {
  flex: 1;
  min-height: 60px;
  max-height: 120px;
  padding: 0.6rem 0.7rem;
  font-size: 0.9rem;
  resize: vertical;
  border-radius: 0.75rem;
  border: 1px solid rgba(210, 105, 30, 0.4);
}
.chat-input:focus {
  outline: none;
  border-color: $ts-border-brown;
}

.chat-send-btn {
  align-self: flex-end;
  padding: 0.6rem 1.4rem;
  font-size: 0.9rem;
  font-weight: 700;
  border-radius: 0.75rem;
  border: 3px solid $ts-border-brown;
  background-color: #ff69b4;
  color: #ffffff;
  cursor: pointer;
  box-shadow: 0 8px 0 color.adjust(#ff69b4, $lightness: -18%);
}
.chat-send-btn:disabled {
  cursor: not-allowed;
  background-color: #ffd2e9;
  box-shadow: none;
}

.chat-error {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #b00020;
}

.chat-loading {
  display: flex;
  gap: 0.3rem;
  padding: 0.5rem 0.7rem;
  align-items: center;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background-color: $ts-text-brown;
  animation: bounce 0.9s infinite alternate;
}
.dot:nth-child(2) {
  animation-delay: 0.15s;
}
.dot:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes bounce {
  from {
    transform: translateY(0);
    opacity: 0.5;
  }
  to {
    transform: translateY(-5px);
    opacity: 1;
  }
}
</style>
