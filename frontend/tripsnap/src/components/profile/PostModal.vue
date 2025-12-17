<template>
  <div class="ts-overlay" @click.self="handleClose">
    <div class="ts-modal">
      <button class="ts-modal-close" type="button" @click="handleClose">✕</button>

      <div class="ts-modal-grid">
        <!-- left: image -->
        <div class="ts-modal-media">
          <img v-if="post?.image" :src="post.image" alt="post image" />
          <span v-else class="ts-placeholder">📸</span>
        </div>

        <!-- right: body -->
        <div class="ts-modal-body">
          <div>
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

          <!-- owner actions (내 게시글일 때만) -->
          <div v-if="post?.is_owner" class="ts-owner-actions">
            <button class="ts-btn ts-btn--pink" type="button" @click="enterEditMode">
              게시글 수정
            </button>
            <button class="ts-danger-link" type="button" @click="onDeletePost">게시글 삭제</button>
          </div>

          <!-- edit mode -->
          <div v-if="editMode" class="ts-edit-box">
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

          <!-- comments -->
          <div>
            <p class="ts-comments-title">댓글</p>

            <div class="ts-comments-box">
              <div v-for="c in comments" :key="c.id" class="ts-comment-item">
                <div class="ts-comment-row">
                  <span class="ts-comment-writer">@{{ c.writer_nickname }}</span>

                  <!-- comment content / edit -->
                  <div class="ts-comment-body">
                    <template v-if="editingCommentId === c.id">
                      <input class="ts-input ts-input--sm" v-model="editingContent" />
                    </template>
                    <template v-else>
                      <span class="ts-comment-text">{{ c.content }}</span>
                    </template>
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

              <p v-if="comments.length === 0" class="ts-muted">
                아직 댓글이 없습니다. 첫 댓글을 남겨보세요!
              </p>
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

const commentInput = ref('')

// 게시글 편집 모드
const editMode = ref(false)
const editTitle = ref('')
const editContent = ref('')

// 댓글 편집 모드
const editingCommentId = ref(null)
const editingContent = ref('')

watch(
  () => post.value,
  (p) => {
    if (!p) return
    editMode.value = false
    editTitle.value = p.title || ''
    editContent.value = p.content || ''
    editingCommentId.value = null
    editingContent.value = ''
    commentInput.value = ''
  },
  { immediate: true },
)

function handleClose() {
  emit('close')
}

async function onToggleLike() {
  if (!post.value) return
  await ps.toggleLike(post.value.id)
}

async function submit() {
  if (!post.value) return
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
}

async function saveEdit() {
  if (!post.value) return
  await ps.updatePost(post.value.id, editTitle.value, editContent.value)
  editMode.value = false
}

async function onDeletePost() {
  if (!post.value) return
  await ps.deletePost(post.value.id)
}
</script>

<style scoped lang="scss">
@use '@/assets/profile.scss' as *;
</style>
