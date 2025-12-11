<!-- src/views/KeywordSelectionView.vue -->
<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'
import { useChatStore } from '../stores/chatbot'

const router = useRouter()
const userStore = useUserStore()
const chatStore = useChatStore()

const API_BASE = import.meta.env.VITE_API_BASE

const isAuthenticated = computed(() => userStore.isAuthenticated)

// 폼 상태
const preference = ref('')
const region = ref('')
const dates = ref('')
const transport = ref('')
const errorMessage = ref('')
const isSubmitting = ref(false)

// 샘플 키워드 버튼 목록 (실제 keyword_selection.html 을 참고해서 수정 가능)
const keywordOptions = [
  '줄 서도 먹는 빵집',
  '디저트가 맛있는 카페',
  '아침에 가기 좋은 빵집',
  '뷰가 좋은 베이커리',
]

const selectKeyword = (kw) => {
  preference.value = kw
}

const startChat = async () => {
  errorMessage.value = ''

  if (!isAuthenticated.value) {
    errorMessage.value = '챗봇을 사용하려면 로그인이 필요합니다.'
    return
  }

  if (!preference.value.trim()) {
    errorMessage.value = '최소 한 가지 선호 키워드를 입력하거나 선택해 주세요.'
    return
  }

  isSubmitting.value = true

  try {
    const res = await fetch(`${API_BASE}/chatbot/init/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        preference: preference.value.trim(),
        region: region.value.trim(),
        dates: dates.value.trim(),
        transport: transport.value.trim(),
      }),
    })

    if (!res.ok) {
      let detail = '챗봇 초기화 중 오류가 발생했습니다.'
      try {
        const data = await res.json()
        if (data.detail) detail = data.detail
      } catch {
        // ignore
      }
      throw new Error(detail)
    }

    const data = await res.json()

    // Pinia에 초기 대화 상태 저장
    chatStore.setInitialConversation(data.conversation_id, data.initial_messages || [])

    // 챗봇 화면으로 이동
    router.push({ name: 'chatbot' })
  } catch (err) {
    console.error(err)
    errorMessage.value = err.message || '챗봇 초기화 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="keyword-page">
    <div class="keyword-card pixel-corners">
      <h2 class="keyword-title">🥐 빵집 추천 챗봇 시작하기</h2>
      <p class="keyword-subtitle">
        먼저 여행/빵집 취향을 간단히 알려주시면, 그에 맞춰 챗봇이 대화를 시작합니다.
      </p>

      <div v-if="!isAuthenticated" class="keyword-alert">
        로그인 후에 챗봇을 사용할 수 있습니다.
      </div>

      <div class="keyword-section">
        <label class="field-label">선호 키워드</label>
        <input
          v-model="preference"
          type="text"
          class="field-input"
          placeholder="예: 줄 서도 먹는 빵집, 디저트 맛집, 아침에 가기 좋은 빵집 등"
        />

        <div class="keyword-options">
          <button
            v-for="kw in keywordOptions"
            :key="kw"
            type="button"
            class="keyword-chip"
            @click="selectKeyword(kw)"
          >
            {{ kw }}
          </button>
        </div>
      </div>

      <div class="keyword-grid">
        <div class="keyword-section">
          <label class="field-label">지역 (선택)</label>
          <input
            v-model="region"
            type="text"
            class="field-input"
            placeholder="예: 대전 중구, 서울 성동구 등"
          />
        </div>

        <div class="keyword-section">
          <label class="field-label">여행 날짜 (선택)</label>
          <input v-model="dates" type="text" class="field-input" placeholder="예: 12/30 ~ 1/1" />
        </div>

        <div class="keyword-section">
          <label class="field-label">이동 수단 (선택)</label>
          <input
            v-model="transport"
            type="text"
            class="field-input"
            placeholder="예: 도보, 대중교통, 자가용 등"
          />
        </div>
      </div>

      <div class="keyword-actions">
        <button
          type="button"
          class="btn-start pixel-corners"
          :disabled="isSubmitting || !isAuthenticated"
          @click="startChat"
        >
          {{ isSubmitting ? '준비 중...' : '챗봇 입장하기' }}
        </button>
      </div>

      <p v-if="errorMessage" class="keyword-error">
        {{ errorMessage }}
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;

.keyword-page {
  min-height: calc(100vh - 160px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 2.5rem 1rem;
}

.keyword-card {
  max-width: 52rem;
  width: 100%;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  box-shadow: 0 22px 55px rgba(0, 0, 0, 0.15);
  padding: 2rem 1.8rem;
}

.keyword-title {
  font-size: 1.7rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 0.4rem;
}

.keyword-subtitle {
  font-size: 0.95rem;
  color: $ts-text-brown;
  margin-bottom: 1.5rem;
}

.keyword-alert {
  margin-bottom: 1rem;
  padding: 0.8rem 1rem;
  border-radius: 0.8rem;
  background: #fff2f2;
  border: 1px solid #f28b82;
  color: #b00020;
  font-size: 0.9rem;
}

.keyword-section {
  margin-bottom: 1.25rem;
}

.field-label {
  display: block;
  font-size: 0.9rem;
  font-weight: 600;
  color: $ts-text-brown;
  margin-bottom: 0.3rem;
}

.field-input {
  width: 100%;
  font-size: 0.9rem;
  padding: 0.55rem 0.7rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(210, 105, 30, 0.4);
}

.field-input:focus {
  outline: none;
  border-color: $ts-border-brown;
}

.keyword-options {
  margin-top: 0.5rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.keyword-chip {
  padding: 0.3rem 0.7rem;
  font-size: 0.8rem;
  border-radius: 999px;
  border: 1px solid rgba(210, 105, 30, 0.4);
  background: #fffaf0;
  cursor: pointer;
}

.keyword-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.keyword-actions {
  margin-top: 1rem;
  text-align: center;
}

.btn-start {
  padding: 0.7rem 2.4rem;
  font-size: 1rem;
  font-weight: 700;
  border-radius: 0.9rem;
  border: 3px solid $ts-border-brown;
  background-color: #ff69b4;
  color: #ffffff;
  cursor: pointer;
}

.btn-start:disabled {
  cursor: not-allowed;
  background-color: #ffd2e9;
  border-color: #f8a9cf;
}

.keyword-error {
  margin-top: 0.8rem;
  font-size: 0.85rem;
  color: #b00020;
}

@media (min-width: 768px) {
  .keyword-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
