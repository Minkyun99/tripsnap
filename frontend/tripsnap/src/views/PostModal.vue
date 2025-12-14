<template>
  <div class="ts-overlay" @click.self="emit('close')">
    <div class="ts-modal">
      <button class="ts-modal-close" type="button" @click="emit('close')">✕</button>

      <div class="ts-modal-grid">
        <!-- left -->
        <div class="ts-modal-media">
          <img v-if="post?.image" :src="post.image" alt="post" />
          <span v-else class="ts-placeholder">📸</span>
        </div>

        <!-- right -->
        <div class="ts-modal-body">
          <div>
            <!-- view mode -->
            <div v-if="!editMode">
              <h3 class="ts-modal-title">{{ post?.title }}</h3>
              <p class="ts-modal-writer">@{{ post?.writer_username }}</p>
              <p class="ts-modal-content">{{ post?.content }}</p>
            </div>

            <!-- edit mode -->
            <div v-else style="display: grid; gap: 0.5rem">
              <input class="ts-input" v-model="editTitle" placeholder="제목" />
              <textarea class="ts-textarea" v-model="editContent" rows="4" placeholder="내용" />
              <div style="display: flex; gap: 0.5rem">
                <button class="ts-btn ts-btn--pink" type="button" @click="submitEdit">
                  수정 저장
                </button>
                <button class="ts-btn ts-btn--white" type="button" @click="cancelEdit">취소</button>
              </div>
            </div>

            <!-- like -->
            <button
              class="ts-modal-like"
              :class="post?.is_liked ? 'ts-modal-like--on' : ''"
              type="button"
              @click="emit('toggle-like')"
              style="margin-top: 0.85rem"
            >
              <span>{{ post?.is_liked ? '❤️' : '🤍' }}</span>
              <span>{{ post?.like_count ?? 0 }}</span>
            </button>
          </div>

          <!-- comments -->
          <div>
            <p class="ts-comments-title">댓글</p>

            <div class="ts-comments-box">
              <div v-for="c in comments" :key="c.id">
                <div class="ts-comment-row">
                  <span class="ts-comment-writer" @click="emit('go-profile', c.writer_nickname)">
                    @{{ c.writer_nickname }}
                  </span>
                  <span class="ts-comment-text">{{ c.content }}</span>
                </div>
                <div class="ts-comment-time">{{ c.created_at }}</div>
              </div>

              <p v-if="comments.length === 0" style="color: #9ca3af; font-size: 0.85rem">
                아직 댓글이 없습니다. 첫 댓글을 남겨보세요!
              </p>
            </div>

            <div class="ts-comment-compose" style="margin-top: 0.75rem">
              <input
                class="ts-input"
                v-model="commentInput"
                placeholder="댓글을 입력하세요..."
                @keydown.enter.prevent="submitComment"
              />
              <button class="ts-btn ts-btn--pink" type="button" @click="submitComment">게시</button>
            </div>
          </div>

          <!-- owner actions -->
          <div v-if="post?.is_owner" class="ts-owner-actions">
            <button v-if="!editMode" class="ts-btn ts-btn--pink" type="button" @click="enterEdit">
              게시글 수정
            </button>
            <button class="ts-danger-link" type="button" @click="emit('delete')">
              게시글 삭제
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  post: { type: Object, default: null },
  comments: { type: Array, default: () => [] },
})

const emit = defineEmits([
  'close',
  'toggle-like',
  'submit-comment', // (content)
  'delete',
  'edit', // ({title, content})
  'go-profile', // (nickname)
])

const commentInput = ref('')

const editMode = ref(false)
const editTitle = ref('')
const editContent = ref('')

watch(
  () => props.post,
  (p) => {
    // 모달이 열릴 때마다 입력값 초기화
    commentInput.value = ''
    editMode.value = false
    editTitle.value = p?.title || ''
    editContent.value = p?.content || ''
  },
  { immediate: true },
)

function submitComment() {
  const content = commentInput.value.trim()
  if (!content) return
  emit('submit-comment', content)
  commentInput.value = ''
}

function enterEdit() {
  editMode.value = true
  editTitle.value = props.post?.title || ''
  editContent.value = props.post?.content || ''
}

function cancelEdit() {
  editMode.value = false
  editTitle.value = props.post?.title || ''
  editContent.value = props.post?.content || ''
}

function submitEdit() {
  const title = editTitle.value.trim()
  const content = editContent.value.trim()
  if (!title) return
  emit('edit', { title, content })
  editMode.value = false
}
</script>
