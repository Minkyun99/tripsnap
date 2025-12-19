<!-- src/views/ChatbotView.vue -->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'
import { useChatStore } from '../stores/chatbot'
import { getCsrfToken } from '../utils/csrf'

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
  // conversationId 가 없으면 키워드 선택 화면으로 되돌리기
  if (!conversationId.value) {
    router.push({ name: 'chat_keywords' })
  }
})

const sendMessage = async () => {
  console.log('=== sendMessage 시작 ===')
  errorMessage.value = ''

  const content = userInput.value.trim()
  console.log('1. 입력 내용:', content)
  console.log('2. conversationId:', conversationId.value)
  
  if (!content || !conversationId.value) {
    console.log('❌ 입력 내용 또는 conversationId 없음')
    return
  }

  console.log('3. isAuthenticated:', isAuthenticated.value)
  if (!isAuthenticated.value) {
    errorMessage.value = '챗봇을 사용하려면 먼저 로그인 해주세요.'
    return
  }

  const csrftoken = getCsrfToken()
  console.log('4. CSRF 토큰:', csrftoken ? '있음' : '없음')
  
  if (!csrftoken) {
    errorMessage.value = 'CSRF 토큰을 찾을 수 없습니다. 페이지를 새로고침한 뒤 다시 시도해 주세요.'
    return
  }

  // 사용자 메시지 먼저 화면에 추가
  console.log('5. 사용자 메시지 추가 시도')
  chatStore.appendMessage('user', content)
  userInput.value = ''
  isLoading.value = true
  console.log('6. 로딩 시작')

  try {
    console.log('7. API 요청 시작:', `${API_BASE}/chatbot/chat/`)
    const res = await fetch(`${API_BASE}/chatbot/chat/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken,
      },
      credentials: 'include',
      body: JSON.stringify({
        message: content,
        conversation_id: conversationId.value,
        trigger: true,
      }),
    })

    console.log('8. 응답 상태:', res.status)
    
    if (!res.ok) {
      let detail = '챗봇 서버와 통신 중 오류가 발생했습니다.'
      try {
        const data = await res.json()
        if (data.detail) detail = data.detail
      } catch {
        // HTML 응답 등일 경우 json 파싱 실패 → 기본 메시지 유지
      }
      throw new Error(detail)
    }

    const data = await res.json()
    console.log('9. 응답 데이터:', data)

    const reply = data.llm_response || '응답을 받았지만 표시할 내용이 없습니다.'
    console.log('10. LLM 응답 추가')
    chatStore.appendMessage('bot', reply)

    // 추천 빵집 목록을 별도로 저장
    if (Array.isArray(data.results) && data.results.length > 0) {
      console.log('11. 빵집 목록 추가:', data.results.length, '개')
      // results를 별도 메시지로 추가 (텍스트는 placeholder)
      const msg = {
        id: Date.now(),
        role: 'bot',
        text: '__BAKERY_LIST__',  // 특수 플래그
        results: data.results
      }
      chatStore.messages.push(msg)
      console.log('12. chatStore.messages:', chatStore.messages)
    }
  } catch (err) {
    console.error('❌ 에러 발생:', err)
    errorMessage.value = err.message || '챗봇 서버와 통신 중 알 수 없는 오류가 발생했습니다.'
    chatStore.appendMessage(
      'bot',
      '죄송합니다. 지금은 잠시 응답할 수 없습니다. 잠시 후 다시 시도해 주세요.',
    )
  } finally {
    isLoading.value = false
    console.log('=== sendMessage 종료 ===')
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

const handleBakeryClick = (bakery) => {
  // TODO: 빵집 클릭 시 동작 구현
  console.log('클릭된 빵집:', bakery)
}
</script>

<template>
  <div class="ts-chat-wrapper">
    <div class="ts-chat-header">
      <h2>TripSnap 챗봇</h2>
      <p v-if="displayName">{{ displayName }} 님을 위한 빵집 여행 도우미</p>
    </div>

    <div class="ts-chat-body">
      <div
        v-for="m in messages"
        :key="m.id"
        class="ts-chat-message"
        :class="m.role === 'user' ? 'from-user' : 'from-bot'"
      >
        <div class="bubble">
          <span v-if="m.role === 'user'">👤 {{ m.text }}</span>
          <span v-else-if="m.text !== '__BAKERY_LIST__' && !m.results">🤖 {{ m.text }}</span>
          
          <!-- 빵집 목록이 있는 경우 버튼으로 표시 -->
          <div v-else-if="m.results" class="bakery-list">
            <div class="bakery-list-header">📍 추천 빵집 목록</div>
            <button
              v-for="(bakery, idx) in m.results"
              :key="idx"
              class="bakery-button"
              @click="handleBakeryClick(bakery)"
            >
              <div class="bakery-number">{{ idx + 1 }}</div>
              <div class="bakery-info">
                <div class="bakery-name">
                  {{ bakery.place_name || '이름 미상' }}
                  <span v-if="bakery.rating" class="bakery-rating">⭐ {{ bakery.rating }}</span>
                </div>
                <div v-if="bakery.district || bakery.address" class="bakery-location">
                  📍 
                  <span v-if="bakery.district">대전 {{ bakery.district }}</span>
                  <span v-if="bakery.district && bakery.address"> | </span>
                  <span v-if="bakery.address" class="bakery-address">{{ bakery.address }}</span>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>
      <div v-if="isLoading" class="ts-chat-loading">🤖 생각 중...</div>
    </div>

    <div class="ts-chat-footer">
      <p v-if="errorMessage" class="ts-error">{{ errorMessage }}</p>
      <textarea
        v-model="userInput"
        class="ts-input"
        placeholder="메시지를 입력하고 Enter를 눌러 보내세요. 줄바꿈은 Shift+Enter 입니다."
        @keydown="handleKeydown"
      />
      <button
        class="ts-send-button"
        :disabled="isLoading || !userInput.trim()"
        @click="sendMessage"
      >
        보내기
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'sass:color';

$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;
$ts-bg-cream: #fffaf0;

.ts-chat-wrapper {
  max-width: 52rem;
  width: 100%;
  margin: 2.5rem auto;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  box-shadow: 0 22px 55px rgba(0, 0, 0, 0.15);
  padding: 1.75rem 1.5rem 1.5rem;
  display: flex;
  flex-direction: column;
}

/* 헤더 영역 */
.ts-chat-header {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 1rem;
}

.ts-chat-header h2 {
  font-size: 1.6rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin: 0;
}

.ts-chat-header p {
  font-size: 0.95rem;
  color: $ts-text-brown;
  margin: 0;
}

/* 메시지 영역 */
.ts-chat-body {
  flex: 1;
  min-height: 260px;
  max-height: 480px;
  overflow-y: auto;
  padding: 1rem 0.4rem;
  border-radius: 0.9rem;
  background: $ts-bg-cream;
  border: 1px solid rgba(210, 105, 30, 0.25);
}

/* 한 줄 메시지 */
.ts-chat-message {
  display: flex;
  margin-bottom: 0.6rem;
}

.ts-chat-message.from-user {
  justify-content: flex-end;
}

.ts-chat-message.from-bot {
  justify-content: flex-start;
}

/* 말풍선 */
.bubble {
  max-width: 80%;
  border-radius: 1rem;
  padding: 0.55rem 0.75rem;
  font-size: 0.9rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.ts-chat-message.from-user .bubble {
  background: #ffefdb;
  border: 1px solid rgba(210, 105, 30, 0.4);
}

.ts-chat-message.from-bot .bubble {
  background: #ffffff;
  border: 1px solid rgba(210, 105, 30, 0.3);
}

/* 로딩 표시 */
.ts-chat-loading {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.5rem 0.7rem;
  font-size: 0.9rem;
  color: $ts-text-brown;
}

/* 빵집 목록 스타일 */
.bakery-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.bakery-list-header {
  font-size: 1rem;
  font-weight: 700;
  color: $ts-text-brown;
  margin-bottom: 0.5rem;
}

.bakery-button {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem;
  background: #fffaf0;
  border: 2px solid rgba(210, 105, 30, 0.3);
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  font-family: inherit;
}

.bakery-button:hover {
  background: #fff5e6;
  border-color: $ts-border-brown;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.bakery-number {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  background: $ts-border-brown;
  color: white;
  border-radius: 50%;
  font-weight: 700;
  font-size: 0.85rem;
  flex-shrink: 0;
}

.bakery-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.bakery-name {
  font-weight: 700;
  font-size: 0.95rem;
  color: $ts-text-brown;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.bakery-rating {
  font-size: 0.85rem;
  color: #ff8c00;
  font-weight: 600;
}

.bakery-location {
  font-size: 0.8rem;
  color: #666;
  line-height: 1.4;
}

.bakery-address {
  color: #888;
}

/* 푸터 영역 (입력창 + 버튼) */
.ts-chat-footer {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

/* 에러 메시지 */
.ts-error {
  font-size: 0.85rem;
  color: #b00020;
}

/* 입력창 */
.ts-input {
  flex: 1;
  min-height: 60px;
  max-height: 120px;
  padding: 0.6rem 0.7rem;
  font-size: 0.9rem;
  resize: vertical;
  border-radius: 0.75rem;
  border: 1px solid rgba(210, 105, 30, 0.4);
  font-family: inherit;
}

.ts-input:focus {
  outline: none;
  border-color: $ts-border-brown;
}

/* 전송 버튼 */
.ts-send-button {
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
  transition:
    transform 0.1s ease,
    box-shadow 0.1s ease;
}

.ts-send-button:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 0 color.adjust(#ff69b4, $lightness: -20%);
}

.ts-send-button:disabled {
  cursor: not-allowed;
  background-color: #ffd2e9;
  box-shadow: none;
}

/* (선택) 로딩 점 애니메이션이 필요하다면 */
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