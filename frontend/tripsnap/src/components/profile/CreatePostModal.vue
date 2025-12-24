<script setup>
import { ref, onMounted, watch } from 'vue'
import { useProfileStore } from '../../stores/profile'

// ✨ props 추가 - 미리 채워진 제목/내용 + 빵집 위치 데이터
const props = defineProps({
  prefilledTitle: {
    type: String,
    default: ''
  },
  prefilledContent: {
    type: String,
    default: ''
  },
  bakeryLocations: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close'])
const ps = useProfileStore()

const title = ref('')
const content = ref('')
const fileInput = ref(null)
const selectedFiles = ref([]) // 여러 파일을 담을 배열
const previewUrls = ref([])   // 미리보기 URL을 담을 배열
const isLoading = ref(false)
const error = ref('')

// ✨ 카카오 지도 관련
const mapContainer = ref(null)

// ✨ 컴포넌트 마운트 시 미리 채워진 내용 설정 (있을 경우에만)
onMounted(() => {
  if (props.prefilledTitle) {
    title.value = props.prefilledTitle
  }
  if (props.prefilledContent) {
    content.value = props.prefilledContent
  }
  
  // ✨ 빵집 위치 데이터가 있으면 카카오 지도 로드
  if (props.bakeryLocations && props.bakeryLocations.length > 0) {
    loadKakaoMap()
  }
})

// ✨ 카카오 지도 로드 및 마커 표시
const loadKakaoMap = () => {
  console.log('🗺️ 카카오맵 로드 시작')
  
  // index.html에서 이미 로드되었다고 가정
  if (window.kakao && window.kakao.maps) {
    console.log('✅ 카카오맵 SDK 사용 가능')
    
    // services가 로드되었는지 확인
    if (window.kakao.maps.load) {
      window.kakao.maps.load(() => {
        console.log('✅ 카카오맵 API 로드 완료')
        initMap()
      })
    } else {
      initMap()
    }
  } else {
    console.error('❌ 카카오맵 SDK가 로드되지 않았습니다. index.html을 확인하세요.')
    console.error('💡 index.html에 다음 스크립트를 추가하세요:')
    console.error('<' + 'script src="//dapi.kakao.com/v2/maps/sdk.js?appkey=YOUR_KEY&libraries=services"><' + '/script>')
  }
}

// ✨ 지도 초기화 및 마커 표시
const initMap = () => {
  if (!mapContainer.value) {
    console.error('❌ 지도 컨테이너가 없습니다')
    return
  }

  const kakao = window.kakao
  
  if (!kakao || !kakao.maps) {
    console.error('❌ 카카오맵 SDK가 없습니다')
    return
  }
  
  console.log('🗺️ 지도 초기화 시작')
  console.log('📍 빵집 데이터:', props.bakeryLocations)
  
  // 지도 옵션
  const mapOption = {
    center: new kakao.maps.LatLng(36.3504, 127.3845), // 대전 중심
    level: 7
  }
  
  // 지도 생성
  const map = new kakao.maps.Map(mapContainer.value, mapOption)
  
  // Geocoder 초기화
  if (!kakao.maps.services || !kakao.maps.services.Geocoder) {
    console.error('❌ Geocoder를 사용할 수 없습니다')
    console.error('💡 index.html에서 libraries=services를 확인하세요')
    return
  }
  
  const geocoder = new kakao.maps.services.Geocoder()
  console.log('✅ Geocoder 초기화 완료')
  
  // 마커를 표시할 위치 배열
  const positions = []
  let geocodeCount = 0
  const totalBakeries = props.bakeryLocations.length
  
  // 각 빵집에 대해 주소를 좌표로 변환
  props.bakeryLocations.forEach((bakery, index) => {
    const name = bakery.name || bakery.place_name || '빵집'
    const address = bakery.road_address || bakery.jibun_address || bakery.address
    
    console.log(`📍 [${index + 1}] ${name}:`, address)
    
    if (!address) {
      console.warn(`⚠️ [${index + 1}] ${name}: 주소가 없습니다`)
      geocodeCount++
      return
    }
    
    // 주소로 좌표 검색
    geocoder.addressSearch(address, function(result, status) {
      geocodeCount++
      
      if (status === kakao.maps.services.Status.OK) {
        console.log(`✅ [${index + 1}] ${name} 좌표:`, result[0].y, result[0].x)
        
        const coords = new kakao.maps.LatLng(result[0].y, result[0].x)
        
        positions.push({
          title: `${index + 1}. ${name}`,
          latlng: coords
        })
        
        // 마커 생성
        const marker = new kakao.maps.Marker({
          map: map,
          position: coords,
          title: name
        })
        
        // 인포윈도우 생성
        const infowindow = new kakao.maps.InfoWindow({
          content: `<div style="padding:5px 10px;font-size:12px;font-weight:bold;white-space:nowrap;">${index + 1}. ${name}</div>`
        })
        
        // 마커 이벤트
        kakao.maps.event.addListener(marker, 'mouseover', function() {
          infowindow.open(map, marker)
        })
        
        kakao.maps.event.addListener(marker, 'mouseout', function() {
          infowindow.close()
        })
        
        kakao.maps.event.addListener(marker, 'click', function() {
          infowindow.open(map, marker)
        })
        
        // 모든 마커 처리 완료 시 지도 범위 조정
        if (geocodeCount === totalBakeries && positions.length > 0) {
          const bounds = new kakao.maps.LatLngBounds()
          positions.forEach(pos => bounds.extend(pos.latlng))
          map.setBounds(bounds)
          console.log(`✅ 지도 범위 조정 완료 - 총 ${positions.length}개 마커`)
        }
        
      } else {
        console.error(`❌ [${index + 1}] ${name} Geocoding 실패:`, status)
      }
    })
  })
}

// 파일 선택 창 열기
function openFilePicker() {
  fileInput.value.click()
}

// 파일 선택 시 처리
function onPick(e) {
  const files = Array.from(e.target.files)
  if (!files.length) return

  files.forEach(file => {
    // 1. 파일 객체 저장
    selectedFiles.value.push(file)
    // 2. 미리보기용 URL 생성 및 저장
    previewUrls.value.push(URL.createObjectURL(file))
  })
  
  // 동일한 파일을 다시 선택할 수 있도록 input 초기화
  e.target.value = ''
}

// 이미지 순서 바꾸기 
function setAsMain(index) {
  if (index === 0) return // 이미 대표라면 무시
  
  // 선택한 이미지를 배열에서 꺼내서 맨 앞으로 이동
  const selectedFile = selectedFiles.value.splice(index, 1)[0]
  const selectedUrl = previewUrls.value.splice(index, 1)[0]
  
  selectedFiles.value.unshift(selectedFile)
  previewUrls.value.unshift(selectedUrl)
}

// 선택한 이미지 삭제
function removeImage(index) {
  // 메모리 누수 방지를 위해 URL 해제
  URL.revokeObjectURL(previewUrls.value[index])
  
  selectedFiles.value.splice(index, 1)
  previewUrls.value.splice(index, 1)
}

// 파일을 Base64로 변환하는 유틸리티
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// 게시글 제출
async function submit() {
  if (!title.value.trim() || !content.value.trim()) {
    error.value = '제목과 내용을 모두 입력해주세요.'
    return
  }

  error.value = ''
  isLoading.value = true
  
  try {
    // 모든 이미지 파일을 Base64 배열로 변환
    const base64Images = await Promise.all(
      selectedFiles.value.map(file => fileToBase64(file))
    )

    // Pinia 스토어 액션 호출 (images_base64 배열 전달)
    await ps.createPost({ 
      title: title.value, 
      content: content.value, 
      images: base64Images 
    })
    
    // 데이터 재로딩 및 모달 닫기
    await ps.loadMyProfile()
    emit('close')
  } catch (e) {
    console.error(e)
    error.value = '게시글 작성 중 오류가 발생했습니다.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="ts-overlay" @click.self="emit('close')">
    <div class="ts-create-modal pixel-corners" @click.stop>
      <h2 class="ts-title">게시글 작성</h2>
      
      <input class="ts-input" v-model="title" placeholder="제목을 입력하세요" />
      <textarea class="ts-textarea" v-model="content" rows="4" placeholder="오늘의 빵지순례 기록을 남겨보세요!"></textarea>

      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        multiple
        style="display: none"
        @change="onPick"
      />

      <!-- ✨ 공유 모드: 카카오 지도 표시 -->
      <div v-if="bakeryLocations && bakeryLocations.length > 0" class="ts-map-section">
        <label class="ts-label">📍 추천 빵집 위치 ({{ bakeryLocations.length }}곳)</label>
        <div ref="mapContainer" class="ts-map-container"></div>
      </div>

      <!-- 일반 모드: 이미지 업로드 -->
      <div v-else class="ts-image-section">
        <label class="ts-label">이미지 ({{ selectedFiles.length }})</label>
        <div class="ts-preview-grid">
          <div v-for="(url, index) in previewUrls" :key="index" class="ts-preview-box">
            <img 
              :src="url" 
              alt="preview" 
              class="ts-preview-img"
              @click="setAsMain(index)" 
              :title="index === 0 ? '현재 대표 이미지입니다' : '클릭하여 대표 이미지로 설정'"
            />
            
            <span v-if="index === 0" class="ts-main-badge">대표</span>
            
            <button class="ts-remove-btn" type="button" @click="removeImage(index)">×</button>
          </div>
          
          <div class="ts-add-box" @click="openFilePicker">
            <span class="plus-icon">+</span>
          </div>
        </div>
      </div>

      <p v-if="error" class="ts-error">{{ error }}</p>

      <div class="ts-actions">
        <button class="ts-btn ts-btn--pink" type="button" @click="submit" :disabled="isLoading">
          {{ isLoading ? '업로드 중...' : '게시글 올리기' }}
        </button>
        <button class="ts-btn ts-btn--white" type="button" @click="emit('close')">취소</button>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
$ts-border-brown: #d2691e;
$ts-pink: #ff69b4;
$ts-pink-hover: #ff1493;

.pixel-corners {
  border-radius: 1.25rem;
}

.ts-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  padding: 1.5rem;
  display: grid;
  place-items: center;
  z-index: 1000;
}

.ts-create-modal {
  width: 100%;
  max-width: 48rem;          /* ✅ 기존 34rem → 48rem로 확장 */
  max-height: 90vh;          /* ✅ 화면 90%까지만 사용하고 내부 스크롤 */
  background: #fff;
  border: 3px solid $ts-border-brown;
  padding: 1.5rem 1.75rem;
  box-shadow: 0 22px 60px rgba(0, 0, 0, 0.2);
  position: relative;
  z-index: 1001;
  overflow-y: auto;          /* ✅ 내용이 많으면 모달 내부 스크롤 */
}

.ts-title {
  margin: 0 0 1rem;
  font-size: 1.5rem;         /* 약간 키움 */
  font-weight: 900;
  color: $ts-border-brown;
}

.ts-input,
.ts-textarea {
  width: 100%;
  padding: 0.75rem 0.9rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(0, 0, 0, 0.18);
  margin-bottom: 0.9rem;
  font-family: inherit;
}

.ts-textarea {
  min-height: 140px;         /* ✅ rows 대신 최소 높이 확보 */
}

.ts-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 700;
  color: #6b4f2a;
}

/* 이미지 / 지도 섹션 여백 */
.ts-image-section,
.ts-map-section {
  margin-bottom: 1.4rem;
}

/* ✨ 카카오 지도 스타일 */
.ts-map-container {
  width: 100%;
  height: 340px;             /* 기존 300px → 조금 넉넉하게 */
  border: 2px solid $ts-border-brown;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

/* 이미지 그리드 레이아웃 조금 키움 */
.ts-preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 110px);
  gap: 12px;
}

.ts-preview-box {
  width: 110px;
  height: 110px;
  position: relative;
  border: 2px solid $ts-border-brown;
  border-radius: 8px;
  overflow: hidden;
  background: #eee;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.ts-preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  cursor: pointer;
  transition: opacity 0.2s;

  &:hover {
    opacity: 0.9;
  }
}

.ts-main-badge {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(210, 105, 30, 0.85);
  color: white;
  font-size: 11px;
  text-align: center;
  padding: 2px 0;
  font-weight: bold;
  pointer-events: none;
}

.ts-remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  background: rgba(210, 105, 30, 0.9);
  color: white;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;

  &:hover {
    background: #b22222;
  }
}

.ts-add-box {
  width: 110px;
  height: 110px;
  border: 2px dashed $ts-border-brown;
  border-radius: 8px;
  background: #fffaf0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: #faebd7;
  }

  .plus-icon {
    font-size: 2rem;
    color: $ts-border-brown;
    font-weight: bold;
  }
}

.ts-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  position: relative;
  z-index: 10;
  margin-top: 0.75rem;
}

.ts-btn {
  padding: 0.65rem 1.25rem;
  border-radius: 0.7rem;
  font-weight: 900;
  border: 2px solid $ts-border-brown;
  cursor: pointer;
  font-family: inherit;
}

.ts-btn--pink {
  background: $ts-pink;
  color: #fff;

  &:hover {
    background: $ts-pink-hover;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.ts-btn--white {
  background: #fff;
  color: #6b4f2a;

  &:hover {
    background: #f8f8f8;
  }
}

.ts-error {
  margin: 0.5rem 0 0.75rem;
  color: #b00020;
  font-weight: 700;
  font-size: 0.9rem;
}

/* 반응형 - 모바일에서는 너무 넓지 않게 */
@media (max-width: 640px) {
  .ts-create-modal {
    max-width: 100%;
    padding: 1.25rem;
  }

  .ts-map-container {
    height: 260px;
  }
}
</style>
