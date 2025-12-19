<template>
  <div class="ts-overlay" @click.self="handleClose">
    <div class="ts-modal">
      <button class="ts-modal-close" type="button" @click="handleClose">✕</button>

      <div class="ts-modal-grid">
        <div class="ts-modal-media ts-slider-container">
          <div 
            class="ts-slider-track" 
            :style="{ transform: `translateX(-${currentIndex * 100}%)` }"
          >
            <template v-if="post?.images && post.images.length > 0">
              <div v-for="(img, idx) in post.images" :key="idx" class="ts-slide">
                <img :src="img" alt="post image" />
              </div>
            </template>
            <div v-else class="ts-slide">
              <img v-if="post?.image" :src="post.image" alt="post image" />
              <span v-else class="ts-placeholder">📸</span>
            </div>
          </div>

          <template v-if="post?.images?.length > 1">
            <button class="ts-nav-btn prev" @click="prevSlide" v-show="currentIndex > 0">❮</button>
            <button class="ts-nav-btn next" @click="nextSlide" v-show="currentIndex < post.images.length - 1">❯</button>
            <div class="ts-page-indicator">{{ currentIndex + 1 }} / {{ post.images.length }}</div>
          </template>
        </div>

        <div class="ts-modal-body">
          <div v-if="!editMode">
            <h3 class="ts-modal-title">{{ post?.title }}</h3>
            <p class="ts-modal-writer">@{{ post?.writer_username }}</p>
            <p class="ts-modal-content">{{ post?.content }}</p>

            <button
              class="ts-modal-like"
              :class="{ 'ts-modal-like--on': post?.is_liked }"
              type="button"
              @click="onToggleLike"
            >
              <span>{{ post?.is_liked ? '❤️' : '🤍' }}</span>
              <span>{{ post?.like_count ?? 0 }}</span>
            </button>
          </div>

          <div v-else class="ts-edit-box">
            <input class="ts-input" v-model="editTitle" placeholder="제목" />
            <textarea
              class="ts-textarea"
              v-model="editContent"
              rows="3"
              placeholder="내용"
            ></textarea>
            <div class="ts-right">
              <button class="ts-btn ts-btn--white" type="button" @click="cancelEdit">취소</button>
              <button class="ts-btn ts-btn--pink" type="button" @click="saveEdit">저장</button>
            </div>
          </div>

          <div v-if="post?.is_owner && !editMode" class="ts-owner-actions">
            <button class="ts-btn ts-btn--pink" type="button" @click="enterEditMode">
              게시글 수정
            </button>
            <button class="ts-danger-link" type="button" @click="onDeletePost">게시글 삭제</button>
          </div>

          <div class="ts-comments-section">
            <p class="ts-comments-title">댓글</p>
            <div class="ts-comments-box custom-scrollbar">
              <div v-for="c in comments" :key="c.id" class="ts-comment-item">
                <div class="ts-comment-row">
                  <span class="ts-comment-writer">@{{ c.writer_nickname }}</span>
                  <div class="ts-comment-body">
                    <input v-if="editingCommentId === c.id" class="ts-input ts-input--sm" v-model="editingContent" />
                    <span v-else class="ts-comment-text">{{ c.content }}</span>
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

const emit = defineEmits(['close'])
const ps = useProfileStore()
const { activePost, modalComments } = storeToRefs(ps)

const post = computed(() => activePost.value)
const comments = computed(() => modalComments.value || [])

// 슬라이더 상태
const currentIndex = ref(0)
const prevSlide = () => { if (currentIndex.value > 0) currentIndex.value-- }
const nextSlide = () => { if (currentIndex.value < (post.value?.images?.length || 0) - 1) currentIndex.value++ }

// 게시글/댓글 입력 상태
const commentInput = ref('')
const editMode = ref(false)
const editTitle = ref('')
const editContent = ref('')
const editingCommentId = ref(null)
const editingContent = ref('')

watch(
  () => post.value,
  (p) => {
    if (!p) return
    currentIndex.value = 0 // 모달 열릴 때 첫 사진으로 초기화
    editMode.value = false
    editTitle.value = p.title || ''
    editContent.value = p.content || ''
    editingCommentId.value = null
    editingContent.value = ''
    commentInput.value = ''
  },
  { immediate: true },
)

function handleClose() { emit('close') }
async function onToggleLike() { if (!post.value) return; await ps.toggleLike(post.value.id) }
async function submit() { if (!post.value || !commentInput.value.trim()) return; await ps.submitComment(post.value.id, commentInput.value); commentInput.value = '' }
function startEdit(c) { editingCommentId.value = c.id; editingContent.value = c.content }
function cancelCommentEdit() { editingCommentId.value = null; editingContent.value = '' }
async function confirmEdit(commentId) { await ps.editComment(commentId, editingContent.value); cancelCommentEdit() }
async function onDeleteComment(commentId) { await ps.deleteComment(commentId) }
function enterEditMode() { editMode.value = true }
function cancelEdit() { editMode.value = false; editTitle.value = post.value?.title || ''; editContent.value = post.value?.content || '' }
async function saveEdit() { if (!post.value) return; await ps.updatePost(post.value.id, editTitle.value, editContent.value); editMode.value = false }
async function onDeletePost() { if (!post.value) return; await ps.deletePost(post.value.id) }
</script>

<style scoped lang="scss">
@use '@/assets/profile.scss' as *;

.ts-slider-container {
  position: relative;
  overflow: hidden;
  background: #000;
  display: flex;
  align-items: center;
}

.ts-slider-track {
  display: flex;
  width: 100%;
  height: 100%;
  transition: transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.ts-slide {
  min-width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  img {
    width: 100%;
    height: 100%;
    object-fit: contain; // 원본 비율 유지 (기호에 따라 cover로 변경 가능)
  }
}

.ts-nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(0, 0, 0, 0.3);
  color: white;
  border: none;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  cursor: pointer;
  z-index: 2;
  &:hover { background: rgba(0,0,0,0.6); }
  &.prev { left: 10px; }
  &.next { right: 10px; }
}

.ts-page-indicator {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.5);
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.ts-comments-box {
  max-height: 250px;
  overflow-y: auto;
}

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #d2691e; border-radius: 2px; }
</style>