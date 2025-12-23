<template>
  <!-- store.modalOpen && store.modalBakery 가 있을 때만 렌더 -->
  <div
    v-if="bakeryStore.modalOpen && bakery"
    class="bakery-overlay"
    @click.self="bakeryStore.closeModal()"
  >
    <div class="bakery-modal">
      <button
        class="bakery-modal-close"
        type="button"
        @click="bakeryStore.closeModal()"
      >
        ✕
      </button>

      <div class="bakery-modal-grid">
        <!-- 왼쪽: 지도 영역 -->
        <div class="bakery-modal-left">
          <div class="bakery-map-container">
            <!-- 위도/경도가 있으면 카카오 지도 표시 -->
            <div
              v-if="bakery?.latitude && bakery?.longitude"
              ref="mapContainer"
              class="kakao-map"
            ></div>

            <!-- 위도/경도가 없으면 안내 메시지 -->
            <div v-else class="bakery-map-placeholder">
              <span class="map-icon">🗺️</span>
              <p class="map-unavailable">지도 정보 미제공</p>
              <p class="map-info">{{ bakery?.name }}</p>
              <p class="map-info-sub">위치 정보가 등록되지 않은 빵집입니다</p>
            </div>
          </div>

          <!-- 빵집 기본 정보 -->
          <div class="bakery-info-section">
            <h2 class="bakery-name">{{ bakery?.name || '빵집 이름' }}</h2>

            <div class="bakery-meta">
              <div v-if="bakery?.category" class="bakery-category">
                🏷️ {{ bakery.category }}
              </div>
              <div v-if="bakery?.district" class="bakery-district">
                📍 대전 {{ bakery.district }}
              </div>
            </div>

            <!-- 평점 -->
            <div
              v-if="bakery?.rate"
              class="bakery-rating"
            >
              <span v-if="bakery.rate" class="rating-item">
                ⭐ tripsnap 평점 {{ bakery.rate }}
              </span>
            </div>

            <!-- 주소 -->
            <div class="bakery-detail-item">
              <span class="detail-label">📍 주소</span>
              <span class="detail-value">
                {{
                  bakery?.road_address ||
                  bakery?.jibun_address ||
                  '주소 정보 없음'
                }}
              </span>
            </div>

            <!-- 전화번호 -->
            <div v-if="bakery?.phone" class="bakery-detail-item">
              <span class="detail-label">📞 전화</span>
              <span class="detail-value">{{ bakery.phone }}</span>
            </div>

            <!-- 영업시간 -->
            <div v-if="hasBusinessHours" class="bakery-detail-item">
              <span class="detail-label">🕐 영업시간</span>
              <div class="business-hours">
                <div v-if="bakery.monday" class="hours-row">
                  <span class="day">월</span>
                  <span class="time">{{ bakery.monday }}</span>
                </div>
                <div v-if="bakery.tuesday" class="hours-row">
                  <span class="day">화</span>
                  <span class="time">{{ bakery.tuesday }}</span>
                </div>
                <div v-if="bakery.wednesday" class="hours-row">
                  <span class="day">수</span>
                  <span class="time">{{ bakery.wednesday }}</span>
                </div>
                <div v-if="bakery.thursday" class="hours-row">
                  <span class="day">목</span>
                  <span class="time">{{ bakery.thursday }}</span>
                </div>
                <div v-if="bakery.friday" class="hours-row">
                  <span class="day">금</span>
                  <span class="time">{{ bakery.friday }}</span>
                </div>
                <div v-if="bakery.saturday" class="hours-row">
                  <span class="day">토</span>
                  <span class="time">{{ bakery.saturday }}</span>
                </div>
                <div v-if="bakery.sunday" class="hours-row">
                  <span class="day">일</span>
                  <span class="time">{{ bakery.sunday }}</span>
                </div>
              </div>
            </div>

            <!-- 키워드 -->
            <div v-if="keywordList.length" class="bakery-keywords">
              <span class="detail-label">🏷️ 특징</span>
              <div class="keywords-list">
                <span
                  v-for="(keyword, idx) in keywordList"
                  :key="idx"
                  class="keyword-tag"
                >
                  {{ keyword }}
                </span>
              </div>
            </div>

            <!-- 지도 보기 버튼 -->
            <a
              v-if="bakery?.url"
              :href="bakery.url"
              target="_blank"
              class="map-link-button"
            >
              🗺️ 네이버 지도에서 보기
            </a>
          </div>
        </div>

        <!-- 오른쪽: 좋아요 & 댓글 영역 -->
        <div class="bakery-modal-right">
          <!-- 좋아요 -->
          <div class="bakery-like-section">
            <button
              class="bakery-like-button"
              :class="bakery?.is_liked ? 'bakery-like-button--on' : ''"
              type="button"
              @click="bakeryStore.toggleLike()"
            >
              <span class="like-icon">
                {{ bakery?.is_liked ? '❤️' : '🤍' }}
              </span>
              <span class="like-count">{{ bakery?.like_count ?? 0 }}</span>
            </button>
          </div>

          <!-- 댓글 섹션 -->
          <div class="bakery-comments-section">
            <p class="comments-title">
              💬 댓글 {{ comments.length }}개
            </p>

            <div class="comments-list">
              <div v-for="c in comments" :key="c.id" class="comment-item">
                <div class="comment-header">
                  <span
                    class="comment-author"
                    @click="emit('go-profile', c.writer_nickname)"
                  >
                    @{{ c.writer_nickname }}
                  </span>
                  <span class="comment-time">{{ c.created_at }}</span>
                </div>
                <p class="comment-content">{{ c.content }}</p>
              </div>

              <p v-if="comments.length === 0" class="no-comments">
                아직 댓글이 없습니다. 첫 댓글을 남겨보세요!
              </p>
            </div>

            <!-- 댓글 입력 -->
            <div class="comment-input-section">
              <input
                class="comment-input"
                v-model="commentInput"
                placeholder="댓글을 입력하세요..."
                @keydown.enter.prevent="submitComment"
              />
              <button
                class="comment-submit-button"
                type="button"
                @click="submitComment"
              >
                게시
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useBakeryStore } from '@/stores/bakery'

const bakeryStore = useBakeryStore()

// Pinia에서 상태 가져오기
const bakery = computed(() => bakeryStore.modalBakery)
const comments = computed(() => bakeryStore.modalComments)
const isOpen = computed(() => bakeryStore.modalOpen)

const emit = defineEmits(['go-profile'])

const commentInput = ref('')
const mapContainer = ref(null)
let kakaoMap = null
let kakaoMarker = null
let mapInitRetryCount = 0
const MAX_RETRY = 10

// 영업시간 존재 여부
const hasBusinessHours = computed(() => {
  const b = bakery.value
  if (!b) return false
  return (
    b.monday ||
    b.tuesday ||
    b.wednesday ||
    b.thursday ||
    b.friday ||
    b.saturday ||
    b.sunday
  )
})

// 키워드 리스트 (배열/문자열 모두 대응)
const keywordList = computed(() => {
  const b = bakery.value
  if (!b || !b.keywords) return []

  if (Array.isArray(b.keywords)) {
    return b.keywords.filter((k) => !!k && k.trim().length > 0)
  }

  return String(b.keywords)
    .split(',')
    .map((k) => k.trim())
    .filter((k) => k.length > 0)
})

// 카카오 지도 초기화
const initKakaoMap = () => {
  console.log('=== 카카오 지도 초기화 시도 ===')

  const b = bakery.value
  if (!b) {
    // 아직 선택된 베이커리가 없음
    return
  }

  // latitude / longitude 또는 lat / lng 둘 다 대응
  const latRaw = b.latitude ?? b.lat
  const lngRaw = b.longitude ?? b.lng

  if (!latRaw || !lngRaw) {
    // 실제로 좌표가 없는 빵집인 경우 (정상적인 시나리오)
    console.warn('⚠️ 위도/경도 정보 없음 → 지도 미표시')
    return
  }

  const lat = parseFloat(latRaw)
  const lng = parseFloat(lngRaw)

  if (Number.isNaN(lat) || Number.isNaN(lng)) {
    console.warn('⚠️ 위도/경도 값이 숫자가 아닙니다:', latRaw, lngRaw)
    return
  }

  // Kakao SDK 로딩 대기
  if (!window.kakao) {
    mapInitRetryCount++
    console.warn(`⏳ 카카오 SDK 로드 대기 중... (${mapInitRetryCount}/${MAX_RETRY})`)

    if (mapInitRetryCount >= MAX_RETRY) {
      console.error('❌ 카카오 SDK 로드 실패')
      return
    }

    setTimeout(() => {
      initKakaoMap()
    }, 500)
    return
  }

  if (!window.kakao.maps) {
    console.warn('⏳ kakao.maps 로딩 중...')
    setTimeout(() => {
      initKakaoMap()
    }, 100)
    return
  }

  mapInitRetryCount = 0

  // DOM 업데이트 이후에 컨테이너 접근
  nextTick(() => {
    if (!mapContainer.value) {
      console.error('❌ 지도 컨테이너 없음')
      return
    }

    try {
      const center = new window.kakao.maps.LatLng(lat, lng)

      const mapOption = {
        center,
        level: 3,
      }

      kakaoMap = new window.kakao.maps.Map(mapContainer.value, mapOption)

      // 크기 재조정
      setTimeout(() => {
        kakaoMap && kakaoMap.relayout()
      }, 100)

      kakaoMarker = new window.kakao.maps.Marker({
        position: center,
        map: kakaoMap,
      })

      const infowindow = new window.kakao.maps.InfoWindow({
        content: `<div style="padding:5px;font-size:12px;text-align:center;width:150px;">${b.name}</div>`,
      })

      infowindow.open(kakaoMap, kakaoMarker)

      console.log('✅ 카카오 지도 초기화 완료')
    } catch (error) {
      console.error('❌ 카카오 지도 초기화 실패:', error)
    }
  })
}

// 1) 베이커리가 바뀔 때: 입력/리트라이 초기화만
watch(
  () => bakery.value,
  () => {
    commentInput.value = ''
    mapInitRetryCount = 0
    // 여기서는 지도 바로 초기화 X (모달 오픈 여부와 타이밍 문제 때문)
  },
)

// 2) 모달이 열릴 때(isOpen → true) + 베이커리가 있는 경우에만 지도 초기화
watch(
  () => isOpen.value,
  (open) => {
    if (open && bakery.value) {
      initKakaoMap()
    }
  },
  { immediate: true },
)

// 모달 닫기
const closeModal = () => {
  bakeryStore.closeModal()
}

// 좋아요 토글
const toggleLike = () => {
  bakeryStore.toggleLike()
}

// 댓글 작성
const submitComment = () => {
  const content = commentInput.value.trim()
  if (!content) return
  bakeryStore.submitComment(content)
  commentInput.value = ''
}

// 프로필로 이동 (부모 라우터로 전달)
const goProfile = (nickname) => {
  emit('go-profile', nickname)
}
</script>

<style scoped lang="scss">
@use 'sass:color';

$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;
$ts-bg-cream: #fffaf0;

/* 오버레이 */
.bakery-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

/* 모달 */
.bakery-modal {
  position: relative;
  width: 100%;
  max-width: 1200px;
  max-height: 90vh;
  background: white;
  border-radius: 1.5rem;
  border: 4px solid $ts-border-brown;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;
$ts-bg-cream: #fffaf0;

/* 오버레이 */
.bakery-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

/* 모달 (PostModal보다 큼) */
.bakery-modal {
  position: relative;
  width: 100%;
  max-width: 1200px;
  max-height: 90vh;
  background: white;
  border-radius: 1.5rem;
  border: 4px solid $ts-border-brown;
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 닫기 버튼 */
.bakery-modal-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid $ts-border-brown;
  background: white;
  font-size: 1.5rem;
  cursor: pointer;
  z-index: 10;
  transition: all 0.2s;

  &:hover {
    background: $ts-bg-cream;
    transform: rotate(90deg);
  }
}

/* 그리드 레이아웃 (좌우 2분할) */
.bakery-modal-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 0;
  height: 100%;
  overflow: hidden;
}

/* 왼쪽 영역 */
.bakery-modal-left {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: $ts-bg-cream;
  padding: 1.5rem;
}

/* 지도 컨테이너 */
.bakery-map-container {
  width: 100%;
  height: 350px;
  min-height: 350px; /* 최소 높이 추가 */
  margin-bottom: 1.5rem;
  border-radius: 1rem;
  overflow: hidden;
  border: 2px solid rgba(210, 105, 30, 0.3);
}

.kakao-map {
  width: 100% !important;
  height: 100% !important;
  min-height: 350px !important; /* 명시적 높이 */
}

.bakery-map-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #fff5e6 0%, #ffe4cc 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: $ts-text-brown;
  padding: 2rem;

  .map-icon {
    font-size: 4rem;
    margin-bottom: 0.5rem;
    opacity: 0.6;
  }

  .map-unavailable {
    margin: 0.5rem 0;
    font-size: 1.1rem;
    font-weight: 700;
    color: $ts-border-brown;
  }

  .map-info {
    margin: 0.25rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: $ts-border-brown;
  }

  .map-info-sub {
    margin: 0.5rem 0 0 0;
    font-size: 0.85rem;
    color: #999;
  }
}

/* 빵집 정보 섹션 */
.bakery-info-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.bakery-name {
  font-size: 2rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin: 0;
}

.bakery-meta {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.bakery-category,
.bakery-district {
  padding: 0.4rem 0.8rem;
  background: white;
  border: 1px solid rgba(210, 105, 30, 0.3);
  border-radius: 0.5rem;
  font-size: 0.9rem;
  color: $ts-text-brown;
}

.bakery-rating {
  display: flex;
  gap: 1rem;
  font-size: 1.1rem;
  font-weight: 600;
  color: #ff8c00;
}

.rating-item {
  padding: 0.5rem 1rem;
  background: white;
  border-radius: 0.75rem;
  border: 2px solid rgba(255, 140, 0, 0.3);
}

.bakery-detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: white;
  border-radius: 0.75rem;
  border: 1px solid rgba(210, 105, 30, 0.2);
}

.detail-label {
  font-weight: 700;
  color: $ts-text-brown;
  font-size: 0.95rem;
}

.detail-value {
  color: #555;
  font-size: 0.9rem;
  line-height: 1.5;
}

/* 영업시간 */
.business-hours {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.hours-row {
  display: flex;
  gap: 1rem;
  font-size: 0.85rem;

  .day {
    min-width: 30px;
    font-weight: 700;
    color: $ts-border-brown;
  }

  .time {
    color: #555;
  }
}

/* 키워드 */
.bakery-keywords {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: white;
  border-radius: 0.75rem;
  border: 1px solid rgba(210, 105, 30, 0.2);
}

.keywords-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.keyword-tag {
  padding: 0.4rem 0.8rem;
  background: #ffefdb;
  border: 1px solid rgba(210, 105, 30, 0.4);
  border-radius: 1rem;
  font-size: 0.85rem;
  color: $ts-text-brown;
}

/* 지도 보기 버튼 */
.map-link-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem 1.5rem;
  background: $ts-border-brown;
  color: white;
  border-radius: 0.75rem;
  text-decoration: none;
  font-weight: 700;
  transition: all 0.2s;
  margin-top: 0.5rem;

  &:hover {
    background: color.adjust($ts-border-brown, $lightness: -10%);
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  }
}

/* 오른쪽 영역 */
.bakery-modal-right {
  display: flex;
  flex-direction: column;
  background: white;
  padding: 1.5rem;
  overflow-y: auto;
}

/* 좋아요 섹션 */
.bakery-like-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 2px solid rgba(210, 105, 30, 0.2);
}

.bakery-like-button {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1.5rem;
  border: 3px solid $ts-border-brown;
  background: white;
  border-radius: 2rem;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 1.1rem;
  font-weight: 700;

  &:hover {
    background: $ts-bg-cream;
    transform: scale(1.05);
  }

  &--on {
    background: #ffe4e6;
    border-color: #ff69b4;
  }

  .like-icon {
    font-size: 1.5rem;
  }

  .like-count {
    color: $ts-text-brown;
  }
}

/* 댓글 섹션 */
.bakery-comments-section {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.comments-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: $ts-text-brown;
  margin: 0 0 1rem 0;
}

.comments-list {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 1rem;
  padding-right: 0.5rem;
}

.comment-item {
  padding: 0.75rem;
  margin-bottom: 0.75rem;
  background: $ts-bg-cream;
  border-radius: 0.75rem;
  border: 1px solid rgba(210, 105, 30, 0.2);
}

.comment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.comment-author {
  font-weight: 700;
  color: $ts-border-brown;
  cursor: pointer;
  font-size: 0.9rem;

  &:hover {
    text-decoration: underline;
  }
}

.comment-time {
  font-size: 0.75rem;
  color: #999;
}

.comment-content {
  margin: 0;
  color: #333;
  font-size: 0.9rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.no-comments {
  text-align: center;
  color: #999;
  font-size: 0.9rem;
  padding: 2rem;
}

/* 댓글 입력 */
.comment-input-section {
  display: flex;
  gap: 0.5rem;
  padding-top: 1rem;
  border-top: 2px solid rgba(210, 105, 30, 0.2);
}

.comment-input {
  flex: 1;
  padding: 0.75rem;
  border: 2px solid rgba(210, 105, 30, 0.3);
  border-radius: 0.75rem;
  font-family: inherit;
  font-size: 0.9rem;

  &:focus {
    outline: none;
    border-color: $ts-border-brown;
  }
}

.comment-submit-button {
  padding: 0.75rem 1.5rem;
  background: #ff69b4;
  color: white;
  border: 3px solid $ts-border-brown;
  border-radius: 0.75rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 0 color.adjust(#ff69b4, $lightness: -18%);

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 0 color.adjust(#ff69b4, $lightness: -20%);
  }

  &:active {
    transform: translateY(0);
    box-shadow: 0 2px 0 color.adjust(#ff69b4, $lightness: -18%);
  }
}

/* 반응형 */
@media (max-width: 968px) {
  .bakery-modal-grid {
    grid-template-columns: 1fr;
  }

  .bakery-modal-left {
    border-bottom: 3px solid $ts-border-brown;
  }

  .bakery-map-container {
    height: 250px;
  }
}
</style>
