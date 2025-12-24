<!-- src/views/ChatbotView.vue -->
<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'
import { useChatStore } from '../stores/chatbot'
import { useBakeryStore } from '@/stores/bakery'
import { useProfileStore } from '@/stores/profile'
import { getCsrfToken } from '../utils/csrf'
import BakeryModal from './BakeryModal.vue'
import CreatePostModal from '../components/profile/CreatePostModal.vue'

const API_BASE = import.meta.env.VITE_API_BASE || ''

const router = useRouter()
const userStore = useUserStore()
const chatStore = useChatStore()
const bakeryStore = useBakeryStore()
const profileStore = useProfileStore()

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

// 게시글 공유 모달
const showCreatePostModal = ref(false)
const prefilledPostContent = ref('')
const sharedBakeryData = ref([])

// ==========================
// 채팅창 스크롤 하단 고정
// ==========================
const chatBody = ref(null)

const scrollToBottom = () => {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight
    }
  })
}

// 메시지가 변경될 때마다 하단으로 이동
watch(
  messages,
  () => {
    scrollToBottom()
  },
  { deep: true },
)

// ==========================
// 0. 초기 진입 가드 + 프로필 로드
// ==========================
onMounted(() => {
  if (!conversationId.value) {
    router.push({ name: 'chat_keywords' })
  }

  // 로그인 상태인데 프로필이 비어 있으면 한 번 로드
  if (isAuthenticated.value && !profileStore.profile?.nickname) {
    profileStore.loadMyProfile().catch(() => {})
  }

  scrollToBottom()
})

// ==========================
// 0-1. 사용자 아바타 계산
// ==========================
const breadEmojis = ['🥐', '🥖', '🍞', '🥯', '🧁']
const fallbackBreadEmoji = ref(
  breadEmojis[Math.floor(Math.random() * breadEmojis.length)],
)

const userAvatarUrl = computed(() => profileStore.profileImgUrl || '')

// ==========================
// 1. LLM 텍스트 파싱 로직
// ==========================

// 메시지별 파싱 결과 캐시
const parsedSummaryCache = new Map()

/**
 * LLM 텍스트를 파싱해서
 * - 각 추천 N별 방문 시간 계획
 * - 코스 전체 소요 시간 요약
 * 을 추출합니다.
 */
const parseBotTextSections = (text) => {
  if (!text) {
    return {
      sections: [],
      courseSummaryLines: [],
    }
  }

  const lines = text.split('\n')
  const sections = []

  const recHeaderRegex = /^🥖\s*추천\s*(\d+)\s*:/ // "🥖 추천 1: ..."

  let current = null

  lines.forEach((originalLine) => {
    const line = originalLine.trimEnd()
    const headerMatch = line.match(recHeaderRegex)

    if (headerMatch) {
      const index = parseInt(headerMatch[1], 10) - 1
      current = {
        index,
        titleLine: line,
        ratingLine: '',
        moveLine: '',
        planLinesRaw: [],
      }
      sections[index] = current
      return
    }

    if (!current) return

    const trimmed = line.trim()
    if (!trimmed) return

    // 평점 줄
    if (trimmed.startsWith('⭐')) {
      if (!current.ratingLine) current.ratingLine = trimmed
      return
    }

    // 이동 요약 줄
    if (trimmed.startsWith('➡')) {
      if (!current.moveLine) current.moveLine = trimmed
      return
    }

    // 방문 시간 계획 헤더 (⏰) 줄은 건너뛰고, 아래 - / → 줄만 수집
    if (trimmed.startsWith('⏰')) {
      return
    }

    // 방문 계획 상세 줄 ("- ..." 또는 "→ ...")
    if (trimmed.startsWith('-') || trimmed.startsWith('→')) {
      current.planLinesRaw.push(trimmed)
      return
    }
  })

  // 코스 전체 소요 시간 요약 (⏱️ 부터 끝까지)
  const courseSummaryLines = []
  const summaryStartIdx = lines.findIndex((l) =>
    l.trim().startsWith('⏱️'),
  )
  if (summaryStartIdx !== -1) {
    for (let i = summaryStartIdx; i < lines.length; i += 1) {
      const t = lines[i].trim()
      if (!t) continue
      courseSummaryLines.push(t)
    }
  }

  // planLinesRaw → label/value 구조로 변환
  sections.forEach((sec) => {
    if (!sec) return
    const rows = []

    sec.planLinesRaw.forEach((rawLine) => {
      // "- 예상 도착 시각: 17:53" / "→ 다음 매장 이동 시작 시각: 18:08"
      let s = rawLine.replace(/^[-•→]\s*/, '').trim()
      const parts = s.split(':')
      if (parts.length >= 2) {
        const label = parts[0].trim()
        const value = parts.slice(1).join(':').trim()
        rows.push({ label, value })
      } else {
        rows.push({ label: '', value: s })
      }
    })

    sec.planRows = rows
  })

  return {
    sections,
    courseSummaryLines,
  }
}

/**
 * 메시지 단위 파싱 결과 가져오기 (캐시 사용)
 */
const getParsedSummary = (msg) => {
  if (!msg || !msg.text) {
    return { sections: [], courseSummaryLines: [] }
  }

  const key = msg.id
  const cached = parsedSummaryCache.get(key)
  if (cached && cached.raw === msg.text) {
    return cached.parsed
  }

  const parsed = parseBotTextSections(msg.text)
  parsedSummaryCache.set(key, { raw: msg.text, parsed })
  return parsed
}

/**
 * 코스 전체 소요 시간 요약
 */
const getCourseSummaryLines = (msg) => {
  const { courseSummaryLines } = getParsedSummary(msg)
  return courseSummaryLines || []
}

const hasCourseSummary = (msg) => {
  return getCourseSummaryLines(msg).length > 0
}

/**
 * 해당 메시지에서, n번째 추천 빵집에 대한 요약 정보
 */
const getBakerySummary = (msg, index) => {
  const { sections } = getParsedSummary(msg)
  return sections[index] || null
}

/**
 * 특정 메시지의 n번째 빵집에 대한 방문 시간 계획 row 리스트
 */
const getPlanRowsFor = (msg, index) => {
  const sec = getBakerySummary(msg, index)
  if (!sec || !sec.planRows) return []

  const allowedLabels = [
    '예상 도착 시각',
    '줄 서는 시간',
    '매장 내 머무는 시간',
    '다음 매장 이동 시작 시각',
  ]

  return sec.planRows.filter((row) => {
    if (!row.label) return false
    return allowedLabels.some((key) => row.label.includes(key))
  })
}

// 메시지별 "자세히 보기" 펼침 상태
const expandedMessageMap = ref({})

const isExpanded = (messageId) => {
  return !!expandedMessageMap.value[messageId]
}

const toggleDetails = (messageId) => {
  const current = !!expandedMessageMap.value[messageId]
  expandedMessageMap.value = {
    ...expandedMessageMap.value,
    [messageId]: !current,
  }
}

// ==========================
// 2. 채팅 전송/입력 로직
// ==========================
const sendMessage = async () => {
  const content = userInput.value.trim()
  errorMessage.value = ''

  if (!content || !conversationId.value) return

  if (!isAuthenticated.value) {
    errorMessage.value = '로그인이 필요합니다.'
    return
  }

  const csrftoken = getCsrfToken()
  if (!csrftoken) {
    errorMessage.value = 'CSRF 토큰을 찾을 수 없습니다.'
    return
  }

  // 사용자 메시지 추가
  chatStore.appendMessage('user', content)
  isLoading.value = true
  userInput.value = ''
  scrollToBottom()

  try {
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

    if (!res.ok) {
      throw new Error('서버 응답 오류')
    }

    const data = await res.json()

    if (data.llm_response) {
      if (data.results) {
        chatStore.appendMessage('bot', data.llm_response, data.results)
      } else {
        chatStore.appendMessage('bot', data.llm_response)
      }
    }
  } catch (err) {
    console.error('❌ 에러 발생:', err)
    errorMessage.value = err.message || '오류가 발생했습니다.'
    chatStore.appendMessage('bot', '죄송합니다. 오류가 발생했습니다.')
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// ==========================
// 3. 빵집 버튼 클릭 → BakeryModal (Pinia 사용)
// ==========================
const openBakeryModal = async (bakery) => {
  if (!bakery || !bakery.id) {
    alert('빵집 ID가 없습니다. RAG 결과를 확인해주세요.')
    return
  }

  try {
    await bakeryStore.openModalById(bakery.id, { loadComments: true })
  } catch (err) {
    console.error('빵집 모달 오픈 중 오류:', err)
  }
}

// 프로필로 이동
const goToBakeryProfile = (nickname) => {
  if (!nickname) return
  router.push({ name: 'profile-detail', params: { nickname } })
}

// ==========================
// 4. 게시글 공유 기능
// ==========================
const shareToPost = (results) => {
  if (!results || !results.length) {
    alert('공유할 빵집이 없습니다.')
    return
  }

  sharedBakeryData.value = results

  const bakeryText = results
    .map((b, idx) => {
      const name = b.name || b.place_name || '이름 미상'
      const rate =
        b.rate !== null && b.rate !== undefined
          ? ` ⭐${typeof b.rate === 'number' ? b.rate.toFixed(1) : b.rate}`
          : ''
      const district = b.district ? `대전 ${b.district}` : ''
      const address = b.address || b.road_address || ''
      const location = [district, address].filter(Boolean).join(' | ')

      return `${idx + 1}. ${name}${rate}\n   📍 ${location}`
    })
    .join('\n\n')

  prefilledPostContent.value =
    `🍞 TripSnap 챗봇 추천 빵집\n\n${bakeryText}\n\n` +
    `✨ AI가 추천해준 빵집들이에요!`

  showCreatePostModal.value = true
}

const closeCreatePostModal = () => {
  showCreatePostModal.value = false
  prefilledPostContent.value = ''
  sharedBakeryData.value = []
}
</script>

<template>
  <div class="ts-chat-page">
    <div class="ts-chat-wrapper">
      <div class="ts-chat-header">
        <div class="ts-chat-header-main">
          <h2>TripSnap 챗봇</h2>
          <p v-if="displayName">
            {{ displayName }} 님을 위한 빵집 여행 도우미
          </p>
          <p v-else>로그인 후 맞춤 빵지순례 코스를 받아보세요.</p>
        </div>
      </div>

      <!-- ✅ 스크롤 하단 고정 대상 영역 -->
      <div class="ts-chat-body" ref="chatBody">
        <transition-group name="fade" tag="div">
          <div
            v-for="m in messages"
            :key="m.id"
            class="ts-chat-message"
            :class="m.role === 'user' ? 'from-user' : 'from-bot'"
          >
            <!-- 사용자 메시지 + 아바타 -->
            <div v-if="m.role === 'user'" class="ts-message-inner ts-message-user">
              <div class="bubble user-bubble">
                {{ m.text }}
              </div>

              <div class="ts-avatar ts-avatar-user">
                <img
                  v-if="userAvatarUrl"
                  :src="userAvatarUrl"
                  alt="내 프로필 이미지"
                  class="ts-avatar-img"
                />
                <span v-else class="ts-avatar-emoji">
                  {{ fallbackBreadEmoji }}
                </span>
              </div>
            </div>

            <!-- 봇 메시지 -->
            <div v-else class="ts-message-inner ts-message-bot">
              <div class="ts-avatar ts-avatar-bot">
                <span class="ts-avatar-emoji">🥯</span>
              </div>

              <div class="bubble bot-bubble">
                <!-- 추천/코스 응답 -->
                <div
                  v-if="(m.results && m.results.length > 0) || hasCourseSummary(m)"
                  class="bot-reco-wrapper"
                >
                  <div class="bot-summary-card">
                    <div class="bot-summary-title">
                      ⏱️ 예상 소요 시간 요약
                    </div>
                    <ul class="bot-summary-list">
                      <li
                        v-for="(line, sIdx) in getCourseSummaryLines(m)"
                        :key="sIdx"
                      >
                        {{ line }}
                      </li>
                    </ul>

                    <button
                      type="button"
                      class="details-toggle-button"
                      @click="toggleDetails(m.id)"
                    >
                      {{ isExpanded(m.id) ? '접기' : '자세히 보기' }}
                    </button>
                  </div>

                  <!-- 방문 시간 계획(자세히 보기) -->
                  <transition name="fade">
                    <div
                      v-if="isExpanded(m.id) && m.results && m.results.length"
                      class="visit-plan-list"
                    >
                      <h3 class="visit-plan-title">
                        ⏰ 방문 시간 계획(예상)
                      </h3>

                      <div
                        v-for="(bakery, bIdx) in m.results"
                        :key="'plan-' + (bakery.id || bIdx)"
                        class="visit-plan-item"
                      >
                        <div class="visit-plan-bakery-name">
                          {{ bIdx + 1 }}.
                          {{ bakery.name || bakery.place_name || '이름 미상' }}
                        </div>

                        <ul
                          v-if="
                            getPlanRowsFor(m, bIdx) &&
                            getPlanRowsFor(m, bIdx).length
                          "
                          class="bakery-plan-list"
                        >
                          <li
                            v-for="row in getPlanRowsFor(m, bIdx)"
                            :key="row.label + row.value"
                          >
                            <span v-if="row.label" class="plan-label">
                              - {{ row.label }}:
                            </span>
                            <span class="plan-value">
                              {{ row.value }}
                            </span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </transition>

                  <!-- 빵집 버튼 리스트 -->
                  <div
                    v-if="m.results && m.results.length"
                    class="bakery-list"
                  >
                    <div class="bakery-list-header">
                      📍 추천 빵집 목록
                    </div>

                    <button
                      type="button"
                      class="share-to-post-button"
                      @click="shareToPost(m.results)"
                    >
                      📝 내 게시글에 공유하기
                    </button>

                    <button
                      v-for="(bakery, bIdx) in m.results"
                      :key="bakery.id || bIdx"
                      type="button"
                      class="bakery-button"
                      @click="openBakeryModal(bakery)"
                    >
                      <div class="bakery-number">
                        {{ bIdx + 1 }}
                      </div>

                      <div class="bakery-info">
                        <div class="bakery-name">
                          {{ bakery.name || bakery.place_name || '이름 미상' }}
                          <span
                            v-if="
                              bakery.rate !== null &&
                              bakery.rate !== undefined
                            "
                            class="bakery-rating"
                          >
                            ⭐
                            {{
                              typeof bakery.rate === 'number'
                                ? bakery.rate.toFixed(1)
                                : bakery.rate
                            }}
                          </span>
                        </div>

                        <div
                          v-if="bakery.district || bakery.address"
                          class="bakery-location"
                        >
                          📍
                          <span v-if="bakery.district">
                            대전 {{ bakery.district }}
                          </span>
                          <span v-if="bakery.district && bakery.address">
                            |
                          </span>
                          <span
                            v-if="bakery.address"
                            class="bakery-address"
                          >
                            {{ bakery.address }}
                          </span>
                        </div>
                      </div>
                    </button>
                  </div>
                </div>

                <!-- 일반 응답 (설명형 텍스트 등) -->
                <div
                  v-else-if="m.text && m.text !== '__BAKERY_LIST__'"
                  class="bot-text-only"
                >
                  🤖 {{ m.text }}
                </div>
              </div>
            </div>
          </div>
        </transition-group>

        <div v-if="isLoading" class="ts-chat-loading">
          🤖 생각 중...
        </div>
      </div>

      <div class="ts-chat-footer">
        <p v-if="errorMessage" class="ts-error">
          {{ errorMessage }}
        </p>

        <div class="ts-input-row">
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
    </div>

    <!-- 공용 베이커리 모달 (Pinia 기반) -->
    <BakeryModal @go-profile="goToBakeryProfile" />

    <!-- 게시글 작성 모달 -->
    <CreatePostModal
      v-if="showCreatePostModal"
      :prefilled-title="'🍞 챗봇 추천 빵집 여행'"
      :prefilled-content="prefilledPostContent"
      :bakery-locations="sharedBakeryData"
      @close="closeCreatePostModal"
    />
  </div>
</template>

<style lang="scss" scoped>
@import '@/assets/styles/chatbot/chatbot.scss';

</style>
