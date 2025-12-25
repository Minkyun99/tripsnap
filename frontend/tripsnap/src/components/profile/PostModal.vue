<!-- src/components/PostModal.vue -->
<template>
  <div class="ts-overlay" @click.self="handleClose">
    <div class="ts-modal">
      <button class="ts-modal-close" type="button" @click="handleClose">✕</button>

      <div class="ts-modal-grid">
        <!-- 좌측: 이미지 슬라이더 (보기 모드 기준) -->
        <div class="ts-modal-media ts-slider-container">
          <div
            class="ts-slider-track"
            :style="{ transform: `translateX(-${currentIndex * 100}%)` }"
          >
            <template v-if="post?.images && post.images.length > 0">
              <div v-for="(img, idx) in post.images" :key="idx" class="ts-slide">
                <img
                  :src="typeof img === 'string' ? img : img.url || img.image || ''"
                  alt="post image"
                />
              </div>
            </template>
            <div v-else class="ts-slide">
              <img v-if="post?.image" :src="post.image" alt="post image" />
              <span v-else class="ts-placeholder">📸</span>
            </div>
          </div>

          <template v-if="post?.images?.length > 1">
            <button class="ts-nav-btn prev" @click="prevSlide" v-show="currentIndex > 0">❮</button>
            <button
              class="ts-nav-btn next"
              @click="nextSlide"
              v-show="currentIndex < post.images.length - 1"
            >
              ❯
            </button>
            <div class="ts-page-indicator">{{ currentIndex + 1 }} / {{ post.images.length }}</div>
          </template>
        </div>

        <!-- 우측: 텍스트/댓글 영역 -->
        <div class="ts-modal-body">
          <!-- 보기 모드 -->
          <div v-if="!editMode">
            <h3 class="ts-modal-title">{{ post?.title }}</h3>
            <p class="ts-modal-writer">@{{ post?.writer_username }}</p>

            <!-- 본문 + 자세히 보기 -->
            <div class="ts-content-box">
              <p
                class="ts-modal-content"
                :class="{ 'ts-modal-content--expanded': showFullContent }"
              >
                {{ fullContent }}
              </p>

              <button
                v-if="isLongContent"
                type="button"
                class="ts-content-toggle"
                @click="toggleContent"
              >
                {{ showFullContent ? '간략히 보기' : '자세히 보기' }}
              </button>
            </div>

            <!-- 좋아요 / 수정·삭제 -->
            <div class="ts-post-actions-row">
              <button
                class="ts-modal-like"
                :class="{ 'ts-modal-like--on': post?.is_liked }"
                type="button"
                @click="onToggleLike"
              >
                <span>{{ post?.is_liked ? '❤️' : '🤍' }}</span>
                <span>{{ post?.like_count ?? 0 }}</span>
              </button>

              <div v-if="post?.is_owner" class="ts-post-owner-actions">
                <button type="button" class="ts-post-action-btn" @click="enterEditMode">
                  게시글 수정
                </button>
                <button
                  type="button"
                  class="ts-post-action-btn ts-post-action-btn--danger"
                  @click="onDeletePost"
                >
                  게시글 삭제
                </button>
              </div>
            </div>
          </div>

          <!-- 수정 모드 -->
          <div v-else class="ts-edit-box">
            <input class="ts-input" v-model="editTitle" placeholder="제목" />
            <textarea
              class="ts-textarea"
              v-model="editContent"
              rows="3"
              placeholder="내용"
            ></textarea>

            <!-- 이미지 수정 영역 -->
            <div class="ts-post-image-edit">
              <h4 class="ts-post-image-title">이미지 수정</h4>

              <!-- 전체 편집 대상 이미지 목록 (기존 + 신규 통합) -->
              <div v-if="editImages.length" class="ts-post-image-list">
                <div v-for="img in editImages" :key="img.id" class="ts-post-image-item">
                  <div class="ts-post-image-thumb-wrap" :class="{ 'is-cover': img.isCover }">
                    <img :src="img.src" alt="preview" class="ts-post-image-thumb" />
                    <span v-if="img.isCover" class="ts-cover-badge">대표</span>
                  </div>
                  <div class="ts-post-image-item-actions">
                    <button type="button" @click="setAsCover(img.id)">대표로</button>
                    <button type="button" @click="removeImage(img.id)">삭제</button>
                  </div>
                </div>
              </div>
              <p v-else class="ts-muted">등록된 이미지가 없습니다.</p>

              <p v-if="imageError" class="ts-error-msg">
                {{ imageError }}
              </p>

              <input
                ref="fileInput"
                type="file"
                accept="image/*"
                multiple
                style="display: none"
                @change="onPickFiles"
              />

              <div class="ts-post-image-buttons">
                <button type="button" class="ts-post-action-btn" @click="openFilePicker">
                  새 이미지 추가
                </button>
                <button
                  type="button"
                  class="ts-post-action-btn ts-post-action-btn--danger"
                  @click="removeAllImages"
                >
                  모든 이미지 삭제
                </button>
              </div>
            </div>

            <!-- 수정 모드 저장/취소 -->
            <div class="ts-post-edit-actions">
              <button type="button" class="ts-post-action-btn" @click="cancelEdit">취소</button>
              <button type="button" class="ts-post-action-btn" @click="saveEdit">저장</button>
            </div>
          </div>

          <!-- 댓글 영역 -->
          <div class="ts-comments-section">
            <p class="ts-comments-title">댓글</p>
            <div class="ts-comments-box custom-scrollbar">
              <div v-for="c in comments" :key="c.id" class="ts-comment-item">
                <div class="ts-comment-row">
                  <span class="ts-comment-writer"> @{{ c.writer_nickname }} </span>
                  <div class="ts-comment-body">
                    <input
                      v-if="editingCommentId === c.id"
                      class="ts-input ts-input--sm"
                      v-model="editingContent"
                    />
                    <span v-else class="ts-comment-text">
                      {{ c.content }}
                    </span>
                  </div>
                </div>
                <div class="ts-comment-meta">
                  <span class="ts-comment-time">{{ c.created_at }}</span>
                  <div v-if="c.is_owner" class="ts-comment-actions">
                    <template v-if="editingCommentId === c.id">
                      <button type="button" @click="confirmEdit(c.id)">저장</button>
                      <button type="button" @click="cancelCommentEdit">취소</button>
                    </template>
                    <template v-else>
                      <button type="button" @click="startEdit(c)">수정</button>
                      <button type="button" @click="onDeleteComment(c.id)">삭제</button>
                    </template>
                  </div>
                </div>
              </div>
              <p v-if="comments.length === 0" class="ts-muted">아직 댓글이 없습니다.</p>
            </div>

            <div class="ts-comment-compose">
              <input
                class="ts-input"
                v-model="commentInput"
                placeholder="댓글을 입력하세요..."
                @keydown.enter.prevent="submit"
              />
              <button class="ts-btn ts-btn--pink" type="button" @click="submit">게시</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useProfileStore } from '@/stores/profile'
import '@/assets/styles/users/post-modal.scss'

const emit = defineEmits(['close'])
const ps = useProfileStore()
const { activePost, modalComments } = storeToRefs(ps)

const post = computed(() => activePost.value)
const comments = computed(() => modalComments.value || [])

// 슬라이더 상태 (보기 모드에서 사용)
const currentIndex = ref(0)
const prevSlide = () => {
  if (currentIndex.value > 0) currentIndex.value--
}
const nextSlide = () => {
  if (currentIndex.value < (post.value?.images?.length || 0) - 1) {
    currentIndex.value++
  }
}

// 게시글/댓글 입력 상태
const commentInput = ref('')
const editMode = ref(false)
const editTitle = ref('')
const editContent = ref('')
const editingCommentId = ref(null)
const editingContent = ref('')

// 내용 접기/펼치기 상태
const showFullContent = ref(false)

// 이미지 편집용 상태
// editImages: [{ id, src, source: 'existing'|'new', base64?, isCover }]
const editImages = ref([])
const fileInput = ref(null)
const imageError = ref('')

// 항상 전체 텍스트
const fullContent = computed(() => post.value?.content || '')

// 긴 글 여부 (버튼 노출 기준)
const MAX_CONTENT_CHARS = 140
const isLongContent = computed(() => fullContent.value.length > MAX_CONTENT_CHARS)

const toggleContent = () => {
  showFullContent.value = !showFullContent.value
}

// post 변경 시 초기화
watch(
  () => post.value,
  (p) => {
    if (!p) return
    currentIndex.value = 0
    editMode.value = false
    editTitle.value = p.title || ''
    editContent.value = p.content || ''
    editingCommentId.value = null
    editingContent.value = ''
    commentInput.value = ''
    showFullContent.value = false
    imageError.value = ''

    // 기존 이미지들을 편집 리스트로 초기화
    editImages.value = buildEditImagesFromPost(p)

    // 파일 인풋 초기화
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  },
  { immediate: true },
)

function buildEditImagesFromPost(p) {
  const list = []
  const images = p?.images

  if (Array.isArray(images) && images.length > 0) {
    images.forEach((img, idx) => {
      let url = ''
      let isCover = false

      if (typeof img === 'string') {
        url = img
        isCover = idx === 0 // 문자열 배열인 경우 0번을 대표로 간주
      } else if (img && typeof img === 'object') {
        url = img.url || img.image || img.src || ''
        isCover = !!img.is_cover || !!img.isCover
      }

      if (!url) return

      list.push({
        id: `existing-${idx}-${Date.now()}`,
        src: url,
        source: 'existing',
        base64: null,
        isCover,
      })
    })
  } else if (p?.image) {
    // images 필드가 없고 단일 image만 있는 경우
    list.push({
      id: `existing-0-${Date.now()}`,
      src: p.image,
      source: 'existing',
      base64: null,
      isCover: true,
    })
  }

  // 대표 이미지가 하나도 없다면 첫 번째를 대표로 지정
  if (list.length > 0 && !list.some((x) => x.isCover)) {
    list[0].isCover = true
  }

  return list
}

function handleClose() {
  emit('close')
}

async function onToggleLike() {
  if (!post.value) return
  await ps.toggleLike(post.value.id)
}

async function submit() {
  if (!post.value || !commentInput.value.trim()) return
  await ps.submitComment(post.value.id, commentInput.value)
  commentInput.value = ''
}

function startEdit(c) {
  editingCommentId.value = c.id
  editingContent.value = c.content
}

function cancelCommentEdit() {
  editingCommentId.value = null
  editingContent.value = ''
}

async function confirmEdit(commentId) {
  await ps.editComment(commentId, editingContent.value)
  cancelCommentEdit()
}

async function onDeleteComment(commentId) {
  await ps.deleteComment(commentId)
}

function enterEditMode() {
  editMode.value = true
}

function cancelEdit() {
  editMode.value = false
  editTitle.value = post.value?.title || ''
  editContent.value = post.value?.content || ''
  imageError.value = ''
  editImages.value = buildEditImagesFromPost(post.value || {})
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

// FileList → base64 리스트
function filesToBase64List(files) {
  const tasks = []
  for (const f of files) {
    tasks.push(
      new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = (e) => {
          if (typeof e.target?.result === 'string') resolve(e.target.result)
          else reject(new Error('이미지를 읽을 수 없습니다.'))
        }
        reader.onerror = () => reject(new Error('이미지를 읽는 중 오류가 발생했습니다.'))
        reader.readAsDataURL(f)
      }),
    )
  }
  return Promise.all(tasks)
}

// URL → base64 (기존 이미지 유지용)
async function urlToDataUrl(url) {
  const res = await fetch(url, { credentials: 'include' })
  const blob = await res.blob()
  return await new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      if (typeof e.target?.result === 'string') resolve(e.target.result)
      else reject(new Error('이미지를 읽을 수 없습니다.'))
    }
    reader.onerror = () => reject(new Error('이미지를 읽는 중 오류가 발생했습니다.'))
    reader.readAsDataURL(blob)
  })
}

function openFilePicker() {
  imageError.value = ''
  fileInput.value?.click()
}

async function onPickFiles(e) {
  imageError.value = ''
  const files = Array.from(e.target.files || [])
  if (!files.length) return

  try {
    const base64List = await filesToBase64List(files)

    const newItems = base64List.map((src, idx) => ({
      id: `new-${Date.now()}-${idx}`,
      src,
      source: 'new',
      base64: src,
      isCover: false,
    }))

    // 편집 리스트에 추가
    editImages.value = [...editImages.value, ...newItems]

    // 대표 이미지가 하나도 없으면 첫 번째 이미지를 대표로
    if (editImages.value.length > 0 && !editImages.value.some((x) => x.isCover)) {
      editImages.value[0].isCover = true
    }
  } catch (err) {
    console.error(err)
    imageError.value = err?.message || '이미지를 읽는 중 오류가 발생했습니다.'
  } finally {
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

// 개별 삭제
function removeImage(id) {
  const idx = editImages.value.findIndex((img) => img.id === id)
  if (idx === -1) return

  const wasCover = editImages.value[idx].isCover
  editImages.value.splice(idx, 1)

  // 대표 이미지를 삭제했다면, 남아있는 첫번째 이미지를 대표로 지정
  if (wasCover && editImages.value.length > 0) {
    editImages.value[0].isCover = true
  }
}

// 전체 삭제
function removeAllImages() {
  editImages.value = []
}

// 대표 이미지 지정
function setAsCover(id) {
  editImages.value = editImages.value.map((img) => ({
    ...img,
    isCover: img.id === id,
  }))
}

// 최종 저장용 base64 리스트 생성 (대표 이미지를 맨 앞으로)
async function buildFinalImagesBase64() {
  if (!editImages.value.length) {
    // 모든 이미지를 삭제한 경우
    return []
  }

  // 대표 이미지가 맨 앞에 오도록 정렬
  const ordered = [...editImages.value].sort((a, b) => {
    if (a.isCover === b.isCover) return 0
    return a.isCover ? -1 : 1
  })

  const result = []
  for (const img of ordered) {
    if (img.base64) {
      result.push(img.base64)
    } else if (img.source === 'existing') {
      // 기존 이미지는 URL → base64 변환
      const dataUrl = await urlToDataUrl(img.src)
      img.base64 = dataUrl
      result.push(dataUrl)
    }
  }
  return result
}

async function saveEdit() {
  if (!post.value) return

  try {
    const imagesBase64 = await buildFinalImagesBase64()

    const payload = {
      title: editTitle.value,
      content: editContent.value,
      images: imagesBase64, // []: 모두 삭제, [...]: 대표 + 일반 이미지
    }

    // ⚠️ ps.updatePost는 (postId, payload) 시그니처라고 가정
    await ps.updatePost(post.value.id, payload)
    editMode.value = false
  } catch (e) {
    console.error(e)
    alert(e?.message || '게시글 수정 중 오류가 발생했습니다.')
  }
}

async function onDeletePost() {
  if (!post.value) return
  const ok = window.confirm('게시글을 삭제하시겠습니까?')
  if (!ok) return
  await ps.deletePost(post.value.id)
  handleClose()
}
</script>

<style scoped>
.ts-post-image-edit {
  margin-top: 0.75rem;
}

.ts-post-image-title {
  font-size: 0.9rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.ts-post-image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 0.5rem;
}

.ts-post-image-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.ts-post-image-thumb-wrap {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid transparent;
}

.ts-post-image-thumb-wrap.is-cover {
  border-color: #ff8a3d;
}

.ts-post-image-thumb {
  width: 96px;
  height: 96px;
  object-fit: cover;
  display: block;
}

.ts-cover-badge {
  position: absolute;
  left: 4px;
  top: 4px;
  padding: 2px 6px;
  font-size: 0.7rem;
  background: rgba(255, 138, 61, 0.9);
  color: #fff;
  border-radius: 999px;
}

.ts-post-image-item-actions {
  display: flex;
  gap: 4px;
}

.ts-post-image-item-actions button {
  border: none;
  background: #ffe7c8;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.7rem;
  cursor: pointer;
}

.ts-post-image-item-actions button:hover {
  background: #ffd29a;
}

.ts-post-image-buttons {
  display: flex;
  gap: 8px;
  margin-top: 0.25rem;
}

.ts-error-msg {
  margin-top: 0.25rem;
  font-size: 0.8rem;
  color: #b00020;
  font-weight: 600;
}
</style>
