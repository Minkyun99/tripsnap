<!-- src/views/KeywordSelectionView.vue -->
<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'
import { useChatStore } from '../stores/chatbot'
import { apiJson } from '../utils/api'

const router = useRouter()
const userStore = useUserStore()
const chatStore = useChatStore()

const isAuthenticated = computed(() => userStore.isAuthenticated)
const displayName = computed(() => {
  const u = userStore.user
  if (!u) return ''
  return u.nickname || u.username || u.email || ''
})

/**
 * 1) 선호 키워드: 여러 개 선택, 최대 3개
 */
const preferenceOptions = [
  { value: '소금빵', label: '소금빵', emoji: '🥐' },
  { value: '바삭한', label: '바삭한', emoji: '✨' },
  { value: '마들렌', label: '마들렌', emoji: '🍰' },
  { value: '건강빵', label: '건강빵', emoji: '🥖' },
  { value: '겉바속촉', label: '겉바속촉', emoji: '🔥' },
  { value: '에그타르트', label: '에그타르트', emoji: '🥧' },
]

// 기본으로는 아무것도 선택되지 않음 (모두 선택 사항)
const selectedPreferences = ref([])

/**
 * 2) 지역: 대전 내 구만 선택
 */
const regionOptions = ['동구', '중구', '서구', '유성구', '대덕구', '대전 전체']
const region = ref('') // 기본값은 서구로 설정 (원하시는 구로 변경 가능)

/**
 * 3) 날짜: from - to (달력)
 */
const startDate = ref('')
const endDate = ref('')

/**
 * 4) 이동 수단
 */
const transportOptions = ['대중교통', '자차', '도보 위주', '상관없음']
const transport = ref('')

const isLoading = ref(false)
const errorMessage = ref('')

/**
 * 선호 키워드 토글 (최대 3개까지)
 */
const togglePreference = (value) => {
  errorMessage.value = ''

  const idx = selectedPreferences.value.indexOf(value)
  if (idx !== -1) {
    // 이미 선택된 상태 → 해제
    selectedPreferences.value.splice(idx, 1)
    return
  }

  // 아직 선택되지 않았는데 3개를 초과하려고 하면 막기
  if (selectedPreferences.value.length >= 3) {
    errorMessage.value = '선호 키워드는 최대 3개까지 선택할 수 있습니다.'
    return
  }

  selectedPreferences.value.push(value)
}

/**
 * 챗봇 시작 (init 호출 후 /chatbot 으로 이동)
 */
const startChat = async () => {
  errorMessage.value = ''

  if (!isAuthenticated.value) {
    errorMessage.value = '챗봇을 사용하려면 먼저 로그인 해주세요.'
    return
  }

  // ✨ 모든 키워드는 선택적(optional)이므로 필수 검증 제거
  // 사용자가 아무것도 선택하지 않아도 챗봇 시작 가능

  isLoading.value = true

  try {
    // preference: 여러 키워드를 ", "로 합쳐서 하나의 문자열로 전송
    // 빈 배열이면 "상관없음"을 기본값으로 전송 (백엔드 필수 검증 통과용)
    const preferenceString = selectedPreferences.value.filter(p => p).length > 0
      ? selectedPreferences.value.filter(p => p).join(', ')
      : '상관없음'
    
    // dates: 날짜가 있으면 "YYYY-MM-DD ~ YYYY-MM-DD" 형태, 없으면 "상관없음"
    const datesString = (startDate.value && endDate.value) 
      ? `${startDate.value} ~ ${endDate.value}` 
      : '상관없음'

    const data = await apiJson('/chatbot/init/', {
      method: 'POST',
      body: JSON.stringify({
        preference: preferenceString,
        region: region.value || '대전 전체',  // 빈 값이면 기본값
        dates: datesString,
        transport: transport.value || '상관없음',  // 빈 값이면 기본값
      }),
    })

    // Pinia store에 초기 대화 상태 세팅
    chatStore.reset()
    chatStore.setInitialConversation(data.conversation_id, data.initial_messages)

    // 키워드 선택 끝 → 실제 챗봇 화면으로 이동
    router.push({ name: 'chatbot' })
  } catch (err) {
    console.error(err)
    errorMessage.value = err.message || '챗봇 초기화 중 알 수 없는 오류가 발생했습니다.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="kw-page">
    <div class="kw-card pixel-corners">
      <div class="kw-header">
        <div class="emoji">🥐</div>
        <h2 class="title">TripSnap 빵집 여행 키워드 선택</h2>
        <p class="subtitle" v-if="displayName">
          {{ displayName }} 님의 취향을 알려주시면 맞춤 빵집을 추천해 드릴게요.
        </p>
        <p class="subtitle" v-else>취향을 선택하고 로그인하면, 맞춤 빵집을 추천해 드립니다.</p>
      </div>

      <!-- 1. 선호 키워드 (최대 3개) -->
      <section class="kw-section">
        <h3 class="section-title">1. 어떤 빵집을 찾으시나요? (선택 사항, 최대 3개)</h3>
        <p class="section-sub">가장 끌리는 키워드를 선택해주세요. 선택하지 않아도 됩니다.</p>
        <div class="chip-group">
          <button
            v-for="opt in preferenceOptions"
            :key="opt.value"
            type="button"
            class="chip"
            :class="{ 'chip--active': selectedPreferences.includes(opt.value) }"
            @click="togglePreference(opt.value)"
          >
            <span class="chip-emoji">{{ opt.emoji }}</span>
            <span class="chip-label">{{ opt.label }}</span>
          </button>
        </div>
      </section>

      <!-- 2. 지역: 대전 구 선택 -->
      <section class="kw-section">
        <h3 class="section-title">2. 대전의 어느 구로 가시나요? (선택 사항)</h3>
        <p class="section-sub">대전 안에서 이동하실 구를 골라주세요. 선택하지 않아도 됩니다.</p>
        <div class="chip-group chip-group--scroll">
          <button
            v-for="opt in regionOptions"
            :key="opt"
            type="button"
            class="chip"
            :class="{ 'chip--active': region === opt }"
            @click="region = opt"
          >
            {{ opt }}
          </button>
        </div>
      </section>

      <!-- 3. 날짜: 달력 from - to -->
      <section class="kw-section">
        <h3 class="section-title">3. 언제 떠나시나요? (선택 사항)</h3>
        <p class="section-sub">여행 시작일과 종료일을 달력에서 선택해주세요. 선택하지 않아도 됩니다.</p>
        <div class="date-range">
          <div class="date-field">
            <label class="date-label">출발일</label>
            <input v-model="startDate" type="date" class="date-input" />
          </div>
          <span class="date-separator">~</span>
          <div class="date-field">
            <label class="date-label">도착일</label>
            <input v-model="endDate" type="date" class="date-input" />
          </div>
        </div>
      </section>

      <!-- 4. 이동수단 -->
      <section class="kw-section">
        <h3 class="section-title">4. 이동 수단을 알려주세요 (선택 사항)</h3>
        <div class="chip-group">
          <button
            v-for="opt in transportOptions"
            :key="opt"
            type="button"
            class="chip"
            :class="{ 'chip--active': transport === opt }"
            @click="transport = opt"
          >
            {{ opt }}
          </button>
        </div>
      </section>

      <p v-if="errorMessage" class="error-msg">
        {{ errorMessage }}
      </p>

      <div class="kw-actions">
        <button
          type="button"
          class="start-btn pixel-corners"
          :disabled="isLoading || !isAuthenticated"
          @click="startChat"
        >
          <span v-if="isLoading">🤖 추천 준비 중...</span>
          <span v-else-if="!isAuthenticated">로그인 후 채팅 시작</span>
          <span v-else>선택 완료하고 채팅 시작하기</span>
        </button>
        <p class="helper-text">
          💡 모든 항목은 선택 사항입니다. 원하는 키워드만 골라도 좋고, 아무것도 선택하지 않아도 챗봇과 대화할 수 있어요!
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'sass:color';

$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;
$ts-bg-cream: #fffaf0;

.kw-page {
  min-height: calc(100vh - 160px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 2.5rem 1rem;
}

.kw-card {
  max-width: 52rem;
  width: 100%;
  margin: 0 auto;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  box-shadow: 0 22px 55px rgba(0, 0, 0, 0.15);
  padding: 1.75rem 1.8rem 1.5rem;
  display: flex;
  flex-direction: column;
}

.kw-header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.emoji {
  font-size: 3.5rem;
  margin-bottom: 0.5rem;
}

.title {
  font-size: 1.8rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 0.3rem;
}

.subtitle {
  font-size: 0.95rem;
  color: $ts-text-brown;
  margin: 0;
}

/* 섹션 공통 */
.kw-section {
  margin-top: 1.4rem;
}

.section-title {
  font-size: 1rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 0.3rem;
}

.section-sub {
  font-size: 0.85rem;
  color: color.adjust($ts-text-brown, $lightness: 5%);
  margin-bottom: 0.6rem;
}

/* 칩(버튼) 그룹 */
.chip-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.chip-group--scroll {
  overflow-x: auto;
  padding-bottom: 0.2rem;

  .chip {
    white-space: nowrap;
  }
}

.chip {
  border-radius: 999px;
  padding: 0.45rem 0.9rem;
  font-size: 0.85rem;
  border: 1px solid rgba(210, 105, 30, 0.4);
  background-color: #ffffff;
  color: $ts-text-brown;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease,
    transform 0.05s ease,
    box-shadow 0.15s ease;

  &:hover {
    background-color: #fff5ea;
    transform: translateY(-1px);
    box-shadow: 0 4px 0 rgba(0, 0, 0, 0.04);
  }
}

.chip--active {
  background-color: #ffefdb;
  border-color: $ts-border-brown;
  box-shadow: 0 4px 0 rgba(0, 0, 0, 0.08);
}

.chip-emoji {
  font-size: 1rem;
}

.error-msg {
  margin-top: 0.8rem;
  font-size: 0.85rem;
  color: #b00020;
}

/* 날짜 범위 */
.date-range {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.date-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.date-label {
  font-size: 0.8rem;
  color: $ts-text-brown;
}

.date-input {
  padding: 0.35rem 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid rgba(210, 105, 30, 0.4);
  font-size: 0.85rem;
}

.date-input:focus {
  outline: none;
  border-color: $ts-border-brown;
}

.date-separator {
  font-size: 1rem;
  color: $ts-text-brown;
}

/* 하단 액션 */
.kw-actions {
  margin-top: 1.6rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}

.start-btn {
  padding: 0.75rem 1.8rem;
  font-size: 0.95rem;
  font-weight: 700;
  border-radius: 0.9rem;
  border: 3px solid $ts-border-brown;
  background-color: #ff69b4;
  color: #ffffff;
  cursor: pointer;
  box-shadow: 0 10px 0 color.adjust(#ff69b4, $lightness: -18%);
  transition:
    transform 0.1s ease,
    box-shadow 0.1s ease,
    opacity 0.1s ease;
}

.start-btn:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 0 color.adjust(#ff69b4, $lightness: -20%);
}

.start-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.helper-text {
  font-size: 0.8rem;
  color: color.adjust($ts-text-brown, $lightness: 10%);
  text-align: center;
}

@media (max-width: 640px) {
  .kw-card {
    padding: 1.4rem 1.1rem 1.1rem;
  }

  .title {
    font-size: 1.5rem;
  }

  .date-range {
    align-items: stretch;
  }
}
</style>