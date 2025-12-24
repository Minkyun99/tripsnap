<template>
  <div class="ts-overlay" @click.self="emit('close')">
    <div class="ts-image-modal pixel-corners">
      <h2 class="ts-image-title">프로필 이미지 변경</h2>

      <div class="ts-image-preview">
        <!-- ✅ 새로 선택한 미리보기 이미지: 클릭하면 선택 취소(다시 기본/기존으로) -->
        <img
          v-if="previewUrl"
          :src="previewUrl"
          alt="preview"
          @click="clearPreview"
          style="cursor: pointer"
          title="클릭하면 선택한 이미지를 취소합니다."
        />
        <!-- ✅ 기존 프로필 이미지: 한 번 클릭하면 기본 상태로 전환 -->
        <img
          v-else-if="!clearedOriginal && currentUrl"
          :src="currentUrl"
          alt="current"
          @click="clearOriginal"
          style="cursor: pointer"
          title="클릭하면 기본 프로필 이미지로 변경됩니다."
        />
        <!-- ✅ 기본 상태 (아무 이미지도 없음) -->
        <span v-else style="font-size: 3rem; line-height: 1">🍞</span>
      </div>

      <!-- 용량 초과 / 기타 에러 메시지 -->
      <p v-if="errorMsg" class="ts-error-msg">
        {{ errorMsg }}
      </p>

      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        style="display: none"
        @change="onPick"
      />

      <div class="ts-image-actions">
        <button class="ts-btn ts-btn--pink" type="button" @click="openPicker">
          이미지 선택
        </button>

        <button
          class="ts-btn ts-btn--green"
          type="button"
          :disabled="uploading || (!selectedFile && !clearedOriginal)"
          @click="handleUpload"
        >
          {{ uploading ? '업로드 중...' : '업로드' }}
        </button>
      </div>

      <button
        class="ts-btn ts-btn--white"
        style="width: 100%; margin-top: 0.75rem"
        type="button"
        @click="emit('close')"
      >
        취소
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'

const props = defineProps({
  // 현재 DB에 저장된 프로필 이미지 URL (없으면 빈 문자열)
  currentUrl: { type: String, default: '' },
})

const emit = defineEmits(['close', 'uploaded']) // uploaded(payload: File|null)

const fileInput = ref(null)
const selectedFile = ref(null)
const previewUrl = ref('')
const uploading = ref(false)
const errorMsg = ref('')

// ✅ 처음에 프로필 이미지가 있었는지, 그리고 그걸 "없애기로" 했는지 추적
const clearedOriginal = ref(false)

// 600KB 제한
const MAX_SIZE = 600 * 1024

function openPicker() {
  errorMsg.value = ''
  fileInput.value?.click()
}

function resetFileInput() {
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

// ✅ 새로 선택한 미리보기/파일 초기화
function clearPreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = ''
  selectedFile.value = null
  errorMsg.value = ''
  resetFileInput()
}

// ✅ 기존 프로필 이미지를 "기본 이미지"로 바꾸겠다는 의도 표시
function clearOriginal() {
  clearedOriginal.value = true
  // currentUrl 미리보기는 v-else-if 조건에서 제외되고, 기본 🍞 화면이 보이게 됨
}

// 파일 선택 시
function onPick(e) {
  errorMsg.value = ''

  const f = e.target.files?.[0]
  if (!f) return

  // ✅ 600KB 초과 시 업로드 불가 + 선택 무효화
  if (f.size > MAX_SIZE) {
    errorMsg.value = '이미지 크기가 600KB를 초과하여 업로드할 수 없습니다.'
    // 이전에 선택해둔 미리보기/파일도 모두 리셋
    clearPreview()
    return
  }

  // 유효한 파일인 경우
  selectedFile.value = f
  clearedOriginal.value = false // 새 파일을 선택했으므로 "기존 이미지를 지우겠다" 상태는 아님

  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = URL.createObjectURL(f)
}

// 업로드 버튼 클릭
async function handleUpload() {
  if (uploading.value) return

  // 선택된 파일도 없고, 기존 이미지를 지우겠다는 표시도 없으면 → 변경 사항 없음
  if (!selectedFile.value && !clearedOriginal.value) {
    errorMsg.value = '변경할 이미지가 없습니다.'
    return
  }

  uploading.value = true
  errorMsg.value = ''

  try {
    // 1) 새 파일이 선택된 경우 → 부모로 File 전달
    if (selectedFile.value) {
      await emit('uploaded', selectedFile.value)
    }
    // 2) 새 파일은 없지만, 기존 이미지를 지우겠다고 한 경우 → 부모로 null 전달
    else if (clearedOriginal.value) {
      await emit('uploaded', null)
    }
  } finally {
    uploading.value = false
  }
}

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>

<style scoped>
.ts-error-msg {
  margin: 0.5rem 0;
  font-size: 0.8rem;
  color: #b00020;
  font-weight: 600;
}
</style>
