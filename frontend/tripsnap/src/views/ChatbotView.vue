<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'
import { useChatStore } from '../stores/chatbot'
import { apiFetch, apiJson } from '../utils/api'
import BakeryModal from './BakeryModal.vue'
import CreatePostModal from '../components/profile/CreatePostModal.vue'

const API_BASE = import.meta.env.VITE_API_BASE

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

// ✨ 게시글 공유 모달 관련
const showCreatePostModal = ref(false)
const prefilledPostContent = ref('')
const sharedBakeryData = ref([])  // ✨ 빵집 데이터 저장

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

  // [수정] getCsrfToken() 호출부 삭제 (apiJson 내부에서 자동으로 처리됨)

  console.log('5. 사용자 메시지 추가 시도')
  chatStore.appendMessage('user', content)
  console.log('6. 로딩 시작')
  
  isLoading.value = true
  userInput.value = ''

  try {
    console.log('7. API 요청 시작')
    console.log('   - Endpoint:', `/chatbot/chat/`)
    console.log('   - conversationId:', conversationId.value)
    console.log('   - message:', content)
    
    // apiJson이 내부적으로 credentials: 'include'와 X-CSRFToken 헤더를 관리합니다.
    const data = await apiJson('/chatbot/chat/', {
      method: 'POST',
      body: JSON.stringify({
        message: content,
        conversation_id: conversationId.value,
        trigger: true,
      }),
    })

    console.log('8. API 응답:', data)

    if (data.llm_response) {
      console.log('10. LLM 응답 메시지 추가')
      if (data.results) {
        console.log('11. 검색 결과 있음:', data.results.length, '개')
        chatStore.appendMessage('bot', data.llm_response, data.results)
      } else {
        chatStore.appendMessage('bot', data.llm_response)
      }
    }

    console.log('12. chatStore.messages 상태:', messages.value)

  } catch (err) {
    console.error('❌ 에러 발생:', err)
    errorMessage.value = err.message || '오류가 발생했습니다.'
    chatStore.appendMessage('bot', '죄송합니다. 오류가 발생했습니다.')
  } finally {
    isLoading.value = false
  }

  console.log('=== sendMessage 종료 ===')
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 빵집 버튼 클릭 처리
const handleBakeryClick = async (bakery) => {
  console.log('=== 빵집 클릭 디버깅 ===')
  
  if (!bakery.id) {
    console.log('❌ bakery.id가 없음!')
    alert('빵집 ID가 없습니다. RAG 결과를 확인하세요.')
    return
  }

  // [수정] getCsrfToken() 호출부 삭제 (apiJson 내부에서 자동으로 처리됨)

  try {
    // 빵집 상세 정보 가져오기
    const detailData = await apiJson(`/chatbot/bakery/${bakery.id}/`)

    selectedBakery.value = detailData

    // 댓글 가져오기
    try {
      const comments = await apiJson(`/chatbot/bakery/${bakery.id}/comments/`)
      bakeryComments.value = comments
    } catch {
      bakeryComments.value = []
    }

    // 모달 열기
    showBakeryModal.value = true

  } catch (err) {
    console.error('빵집 정보 로드 에러:', err)
    errorMessage.value = err.message || '빵집 정보를 가져오는데 실패했습니다.'
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

  try {
    const data = await apiJson(`/chatbot/bakery/${selectedBakery.value.id}/like/`, {
      method: 'POST',
    })

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

  try {
    const data = await apiJson(
      `/chatbot/bakery/${selectedBakery.value.id}/comments/create/`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
      }
    )
    
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
  
  if (!nickname) {
    console.warn('닉네임이 없습니다.')
    return
  }
  
  closeBakeryModal()
  router.push({ name: 'profile-detail', params: { nickname } })
}

// ✨✨ 게시글 공유 기능 ✨✨
const shareToPost = (results) => {
  console.log('=== 게시글 공유 시작 ===')
  console.log('추천 빵집:', results)
  
  if (!results || results.length === 0) {
    alert('공유할 빵집이 없습니다.')
    return
  }

  // ✨ 빵집 데이터 저장 (지도 표시용)
  sharedBakeryData.value = results

  // 빵집 목록을 텍스트로 변환
  const bakeryText = results
    .map((bakery, idx) => {
      const name = bakery.name || bakery.place_name || '이름 미상'
      const rate = bakery.rate ? ` ⭐${bakery.rate}` : ''
      const district = bakery.district ? `대전 ${bakery.district}` : ''
      const address = bakery.address || ''
      const location = [district, address].filter(Boolean).join(' | ')
      
      return `${idx + 1}. ${name}${rate}\n   📍 ${location}`
    })
    .join('\n\n')

  // 미리 채워진 내용 설정
  prefilledPostContent.value = `🍞 TripSnap 챗봇 추천 빵집\n\n${bakeryText}\n\n✨ AI가 추천해준 대전의 맛있는 빵집들이에요!`
  
  // 모달 열기
  showCreatePostModal.value = true
  
  console.log('게시글 작성 모달 열림')
}

// 게시글 모달 닫기
const closeCreatePostModal = () => {
  showCreatePostModal.value = false
  prefilledPostContent.value = ''
  sharedBakeryData.value = []  // ✨ 빵집 데이터 초기화
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
            
            <div v-else-if="m.role === 'bot'">
              <div v-if="m.text && m.text !== '__BAKERY_LIST__'" class="bot-text">
                🤖 {{ m.text }}
              </div>
              
              <div v-if="m.results" class="bakery-list">
                <div class="bakery-list-header">📍 추천 빵집 목록</div>
                
                <button 
                  class="share-to-post-button"
                  @click="shareToPost(m.results)"
                >
                  📝 내 게시글에 공유하기
                </button>
                
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

    <BakeryModal
      v-if="showBakeryModal"
      :bakery="selectedBakery"
      :comments="bakeryComments"
      @close="closeBakeryModal"
      @toggle-like="toggleBakeryLike"
      @submit-comment="submitBakeryComment"
      @go-profile="goToBakeryProfile"
    />

    <CreatePostModal
      v-if="showCreatePostModal"
      :prefilled-title="'🍞 챗봇 추천 빵집 여행'"
      :prefilled-content="prefilledPostContent"
      :bakery-locations="sharedBakeryData"
      @close="closeCreatePostModal"
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
  color: #6b7280;
  margin: 0;
}

.ts-chat-body {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 1.25rem;
  padding: 0.25rem;
  max-height: 28rem;
}

.ts-chat-message {
  display: flex;
  margin-bottom: 1rem;
}

.ts-chat-message.from-user {
  justify-content: flex-end;
}

.ts-chat-message.from-bot {
  justify-content: flex-start;
}

.bubble {
  background: white;
  padding: 0.85rem 1.1rem;
  border-radius: 1.2rem;
  max-width: 75%;
  border: 2px solid $ts-border-brown;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
  font-size: 0.95rem;
  line-height: 1.5;
  color: #333;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.from-user .bubble {
  background: color.adjust($ts-bg-cream, $lightness: -3%);
}

.bakery-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  width: 100%;
}

.bot-text {
  margin-bottom: 1rem;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.bakery-list-header {
  font-weight: 700;
  font-size: 1rem;
  color: $ts-border-brown;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid $ts-border-brown;
}

.share-to-post-button {
  background: linear-gradient(135deg, #ff6b9d 0%, #ffa06b 100%);
  color: white;
  border: none;
  border-radius: 0.75rem;
  padding: 0.85rem 1.2rem;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(255, 107, 157, 0.3);
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(255, 107, 157, 0.4);
  }
}

.bakery-button {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  background: white;
  border: 2px solid $ts-border-brown;
  border-radius: 0.75rem;
  padding: 0.85rem 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;

  &:hover {
    background: $ts-bg-cream;
    transform: translateX(4px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
}

.bakery-number {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
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
  gap: 0.35rem;
  min-width: 0;
}

.bakery-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: $ts-text-brown;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.bakery-rating {
  font-size: 0.85rem;
  color: #f59e0b;
}

.bakery-location {
  font-size: 0.85rem;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ts-chat-loading {
  text-align: center;
  font-size: 0.9rem;
  color: #9ca3af;
  padding: 0.5rem;
}

.ts-chat-footer {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.ts-error {
  color: #dc2626;
  font-size: 0.85rem;
  margin: 0;
}

.ts-input {
  width: 100%;
  padding: 0.85rem 1rem;
  border: 2px solid $ts-border-brown;
  border-radius: 0.75rem;
  font-size: 0.95rem;
  resize: vertical;
  min-height: 3.5rem;
}

.ts-send-button {
  align-self: flex-end;
  background: $ts-border-brown;
  color: white;
  border: none;
  padding: 0.75rem 2rem;
  border-radius: 0.75rem;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>