<!-- src/views/ChatbotView.vue -->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'
import { useChatStore } from '../stores/chatbot'
import { getCsrfToken } from '../utils/csrf'
import BakeryModal from './BakeryModal.vue'

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

// 빵집 모달 관련
const showBakeryModal = ref(false)
const selectedBakery = ref(null)
const bakeryComments = ref([])

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
    console.log('❌ 인증되지 않음')
    errorMessage.value = '로그인이 필요합니다.'
    return
  }

  const csrftoken = getCsrfToken()
  console.log('4. CSRF 토큰:', csrftoken ? '있음' : '없음')
  
  if (!csrftoken) {
    errorMessage.value = 'CSRF 토큰을 찾을 수 없습니다.'
    return
  }

  console.log('5. 사용자 메시지 추가 시도')
  chatStore.appendMessage('user', content)
  console.log('6. 로딩 시작')
  
  isLoading.value = true
  userInput.value = ''

  try {
    console.log('7. API 요청 시작')
    console.log('   - Endpoint:', `${API_BASE}/chatbot/chat/`)
    console.log('   - conversationId:', conversationId.value)
    console.log('   - message:', content)
    
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

    console.log('8. API 응답 상태:', res.status, res.statusText)

    if (!res.ok) {
      throw new Error(`서버 응답 에러: ${res.status}`)
    }

    const data = await res.json()
    console.log('9. API 응답 데이터:', data)

    if (data.llm_response) {
      console.log('10. LLM 응답 메시지 추가')
      chatStore.appendMessage('bot', data.llm_response)
    }

    if (data.results && data.results.length > 0) {
      console.log('11. 검색 결과 있음:', data.results.length, '개')
      const msg = {
        id: Date.now(),
        role: 'bot',
        text: '__BAKERY_LIST__',
        results: data.results
      }
      chatStore.messages.push(msg)
    }

    console.log('12. chatStore.messages 상태:', chatStore.messages)

  } catch (err) {
    console.error('❌ sendMessage 에러:', err)
    errorMessage.value = err.message || '메시지 전송 중 오류가 발생했습니다.'
    chatStore.appendMessage('bot', '죄송합니다. 응답을 생성하는 중 오류가 발생했습니다.')
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

const handleBakeryClick = async (bakery) => {
  console.log('=== 빵집 클릭 디버깅 ===')
  console.log('전체 bakery 객체:', bakery)
  console.log('bakery.id:', bakery.id)
  console.log('bakery.name:', bakery.name)
  console.log('bakery.place_name:', bakery.place_name)
  
  if (!bakery.id) {
    errorMessage.value = '빵집 ID가 없습니다. RAG 결과를 확인하세요.'
    console.error('❌ bakery.id가 없음!')
    return
  }
  
  if (!isAuthenticated.value) {
    errorMessage.value = '빵집 정보를 보려면 로그인이 필요합니다.'
    return
  }

  try {
    isLoading.value = true
    
    console.log('API 요청 URL:', `${API_BASE}/chatbot/bakery/${bakery.id}/`)
    
    // 빵집 상세 정보 로드
    const detailRes = await fetch(`${API_BASE}/chatbot/bakery/${bakery.id}/`, {
      credentials: 'include',
    })
    
    console.log('API 응답 상태:', detailRes.status)
    
    if (!detailRes.ok) {
      throw new Error('빵집 정보를 불러올 수 없습니다.')
    }
    
    const detailData = await detailRes.json()
    console.log('빵집 상세 데이터:', detailData)
    selectedBakery.value = detailData
    
    // 댓글 목록 로드
    const commentsRes = await fetch(`${API_BASE}/chatbot/bakery/${bakery.id}/comments/`, {
      credentials: 'include',
    })
    
    if (commentsRes.ok) {
      const commentsData = await commentsRes.json()
      bakeryComments.value = commentsData
    } else {
      bakeryComments.value = []
    }
    
    // 모달 열기
    showBakeryModal.value = true

  } catch (err) {
    console.error('빵집 정보 로드 에러:', err)
    errorMessage.value = err.message || '빵집 정보를 불러오는데 실패했습니다.'
  } finally {
    isLoading.value = false
  }
}

// 빵집 모달 닫기
const closeBakeryModal = () => {
  showBakeryModal.value = false
  selectedBakery.value = null
  bakeryComments.value = []
}

// 빵집 좋아요 토글
const toggleBakeryLike = async () => {
  if (!selectedBakery.value) return

  const csrftoken = getCsrfToken()
  if (!csrftoken) {
    errorMessage.value = 'CSRF 토큰을 찾을 수 없습니다.'
    return
  }

  try {
    const res = await fetch(
      `${API_BASE}/chatbot/bakery/${selectedBakery.value.id}/like/`,
      {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
        },
        credentials: 'include',
      }
    )

    if (!res.ok) {
      throw new Error('좋아요 처리에 실패했습니다.')
    }

    const data = await res.json()
    
    // 상태 업데이트
    selectedBakery.value.is_liked = data.is_liked
    selectedBakery.value.like_count = data.like_count

  } catch (err) {
    console.error('좋아요 토글 에러:', err)
    errorMessage.value = err.message || '좋아요 처리에 실패했습니다.'
  }
}

// 빵집 댓글 작성
const submitBakeryComment = async (content) => {
  if (!selectedBakery.value || !content.trim()) return

  const csrftoken = getCsrfToken()
  if (!csrftoken) {
    errorMessage.value = 'CSRF 토큰을 찾을 수 없습니다.'
    return
  }

  try {
    const res = await fetch(
      `${API_BASE}/chatbot/bakery/${selectedBakery.value.id}/comments/create/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrftoken,
        },
        credentials: 'include',
        body: JSON.stringify({ content }),
      }
    )

    if (!res.ok) {
      throw new Error('댓글 작성에 실패했습니다.')
    }

    const data = await res.json()
    
    // 댓글 목록 맨 위에 추가 (최신순)
    bakeryComments.value.unshift(data)
    
    // 댓글 수 증가
    selectedBakery.value.comment_count += 1

  } catch (err) {
    console.error('댓글 작성 에러:', err)
    errorMessage.value = err.message || '댓글 작성에 실패했습니다.'
  }
}

// 프로필로 이동
const goToBakeryProfile = (nickname) => {
  console.log('프로필로 이동:', nickname)
  // TODO: 프로필 페이지 라우팅
  // router.push({ name: 'profile', params: { nickname } })
}
</script>

<template>
  <div>
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

    <!-- 빵집 모달 -->
    <BakeryModal
      v-if="showBakeryModal"
      :bakery="selectedBakery"
      :comments="bakeryComments"
      @close="closeBakeryModal"
      @toggle-like="toggleBakeryLike"
      @submit-comment="submitBakeryComment"
      @go-profile="goToBakeryProfile"
    />
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
  margin-bottom: 0.85rem;
}

.ts-chat-message.from-user {
  justify-content: flex-end;
}

.ts-chat-message.from-bot {
  justify-content: flex-start;
}

.bubble {
  max-width: 74%;
  padding: 0.75rem 1rem;
  border-radius: 1rem;
  word-break: break-word;
  line-height: 1.45;
  font-size: 0.95rem;
}

.ts-chat-message.from-user .bubble {
  background: color.adjust(#ff69b4, $lightness: 27%);
  color: #fff;
  border-bottom-right-radius: 0.28rem;
  box-shadow: 0 3px 0 color.adjust(#ff69b4, $lightness: -15%);
}

.ts-chat-message.from-bot .bubble {
  background: #fff;
  color: #333;
  border: 3px solid $ts-border-brown;
  border-bottom-left-radius: 0.28rem;
  box-shadow: 0 4px 0 color.adjust($ts-border-brown, $lightness: -12%);
}

/* 빵집 목록 스타일 */
.bakery-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.5rem;
  width: 100%;
  max-width: 100%;
}

.bakery-list-header {
  font-weight: 700;
  font-size: 1rem;
  color: $ts-border-brown;
  margin-bottom: 0.25rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid rgba(210, 105, 30, 0.3);
}

.bakery-button {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  background: $ts-bg-cream;
  border: 2px solid $ts-border-brown;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    border-color: color.adjust($ts-border-brown, $lightness: -10%);
  }

  &:active {
    transform: translateY(0);
  }
}

.bakery-number {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  background: $ts-border-brown;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.9rem;
}

.bakery-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.bakery-name {
  font-weight: 700;
  font-size: 1rem;
  color: #333;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.bakery-rating {
  font-size: 0.85rem;
  color: #ff8c00;
}

.bakery-location {
  font-size: 0.85rem;
  color: #666;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.bakery-address {
  color: #888;
}

/* 로딩 */
.ts-chat-loading {
  text-align: center;
  padding: 1rem;
  font-size: 1.1rem;
}

/* 하단 입력 영역 */
.ts-chat-footer {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.ts-error {
  color: #dc2626;
  font-size: 0.9rem;
  margin: 0 0 0.25rem 0;
}

.ts-input {
  width: 100%;
  min-height: 60px;
  max-height: 140px;
  padding: 0.8rem 1rem;
  border: 3px solid $ts-border-brown;
  border-radius: 0.75rem;
  resize: vertical;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.4;
  background: #fff;

  &:focus {
    outline: none;
    border-color: color.adjust($ts-border-brown, $lightness: -15%);
  }
}

.ts-send-button {
  width: 100%;
  padding: 0.85rem;
  border: 3px solid $ts-border-brown;
  background: #ff69b4;
  color: #fff;
  font-size: 1rem;
  font-weight: 700;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 5px 0 color.adjust(#ff69b4, $lightness: -22%);

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 7px 0 color.adjust(#ff69b4, $lightness: -22%);
  }

  &:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: 0 3px 0 color.adjust(#ff69b4, $lightness: -22%);
  }

  &:disabled {
    background: #ccc;
    border-color: #999;
    cursor: not-allowed;
    box-shadow: 0 3px 0 #999;
  }
}
</style>