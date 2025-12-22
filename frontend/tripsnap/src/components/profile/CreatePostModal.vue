<script setup>
import { ref, onMounted } from 'vue'
import { useProfileStore } from '../../stores/profile'

// ✨ props 추가 - 미리 채워진 제목/내용 (선택적)
const props = defineProps({
  prefilledTitle: {
    type: String,
    default: ''
  },
  prefilledContent: {
    type: String,
    default: ''
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

// ✨ 컴포넌트 마운트 시 미리 채워진 내용 설정 (있을 경우에만)
onMounted(() => {
  if (props.prefilledTitle) {
    title.value = props.prefilledTitle
  }
  if (props.prefilledContent) {
    content.value = props.prefilledContent
  }
})

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

      <div class="ts-image-section">
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
  padding: 1rem;
  display: grid;
  place-items: center;
  z-index: 60;
}

.ts-create-modal {
  width: 100%;
  max-width: 34rem;
  background: #fff;
  border: 4px solid $ts-border-brown;
  padding: 1.25rem;
  box-shadow: 0 26px 70px rgba(0, 0, 0, 0.22);
}

.ts-title {
  margin: 0 0 1rem;
  font-size: 1.35rem;
  font-weight: 900;
  color: $ts-border-brown;
}

.ts-input, .ts-textarea {
  width: 100%;
  padding: 0.7rem 0.85rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(0, 0, 0, 0.18);
  margin-bottom: 0.8rem;
  font-family: inherit;
}

.ts-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 700;
  color: #6b4f2a;
}

/* 이미지 그리드 레이아웃 */
.ts-image-section {
  margin-bottom: 1.25rem;
}

.ts-preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 100px);
  gap: 12px;
}

.ts-preview-box {
  width: 100px;
  height: 100px;
  position: relative;
  border: 2px solid $ts-border-brown;
  border-radius: 8px;
  overflow: hidden;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
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
  width: 100px;
  height: 100px;
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
  &:hover { background: $ts-pink-hover; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.ts-btn--white {
  background: #fff;
  color: #6b4f2a;
  &:hover { background: #f8f8f8; }
}

.ts-error {
  margin: 0.5rem 0 0.75rem;
  color: #b00020;
  font-weight: 700;
  font-size: 0.9rem;
}

.ts-preview-box {
  width: 100px;
  height: 100px;
  position: relative;
  border: 2px solid #d2691e;
  border-radius: 8px;
  overflow: hidden;
  background: #eee;
}

.ts-preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  cursor: pointer; // 클릭 가능하다는 시각적 힌트
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
  pointer-events: none; // 배지 클릭 시에도 이미지가 클릭되도록 설정
}
</style>