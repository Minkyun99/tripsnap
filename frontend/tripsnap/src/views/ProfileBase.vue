<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiJson, apiFetch } from '../utils/api'

const router = useRouter()

/* ===== state ===== */
const isLoading = ref(false)
const error = ref('')

const me = ref(null)
const profile = ref({
  nickname: '',
  username: '',
  profile_img: '',
  follower_count: 0,
  following_count: 0,
})
const posts = ref([])

/* ===== modals ===== */
const imageModalOpen = ref(false)
const postCreateModalOpen = ref(false)
const postModalOpen = ref(false)
const followModalOpen = ref(false)
const followModalType = ref('followers')
const followList = ref([])

/* ===== image upload ===== */
const selectedProfileFile = ref(null)
const previewUrl = ref('')

/* ===== post create ===== */
const newTitle = ref('')
const newContent = ref('')
const newImage = ref(null)

/* ===== post modal ===== */
const activePost = ref(null)
const modalComments = ref([])
const commentInput = ref('')
const editMode = ref(false)
const editTitle = ref('')
const editContent = ref('')

const isOwner = computed(() => true) // ProfileView는 “본인” 고정

/* ===== init ===== */
onMounted(async () => {
  await loadMyProfile()
})

async function loadMyProfile() {
  isLoading.value = true
  error.value = ''
  try {
    const data = await apiJson('/api/users/me/profile/')
    me.value = data.me
    profile.value = data.profile
    posts.value = data.posts || []
  } catch (e) {
    error.value = e.message
  } finally {
    isLoading.value = false
  }
}

/* ===== settings ===== */
function goSettings() {
  // settings 라우트가 없다면 연결만 해두세요
  router.push({ name: 'settings' })
}

/* ===== follow list modal ===== */
async function openFollowModal(type) {
  followModalType.value = type
  followModalOpen.value = true
  followList.value = []

  try {
    const nickname = profile.value.nickname
    const url =
      type === 'followers'
        ? `/users/profile/${encodeURIComponent(nickname)}/followers/ajax/`
        : `/users/profile/${encodeURIComponent(nickname)}/followings/ajax/`

    const data = await apiJson(url)
    followList.value = data.users || []
  } catch (e) {
    followList.value = []
  }
}
function closeFollowModal() {
  followModalOpen.value = false
}

/* ===== like ===== */
async function toggleLike(post) {
  const data = await apiJson(`/users/post/${post.id}/like-toggle/ajax/`, { method: 'POST' })
  post.is_liked = data.is_liked
  post.like_count = data.like_count

  if (activePost.value && activePost.value.id === post.id) {
    activePost.value.is_liked = data.is_liked
    activePost.value.like_count = data.like_count
  }
}
async function toggleModalLike() {
  if (!activePost.value) return
  const data = await apiJson(`/users/post/${activePost.value.id}/like-toggle/ajax/`, {
    method: 'POST',
  })
  activePost.value.is_liked = data.is_liked
  activePost.value.like_count = data.like_count

  const p = posts.value.find((x) => x.id === activePost.value.id)
  if (p) {
    p.is_liked = data.is_liked
    p.like_count = data.like_count
  }
}

/* ===== post modal open/close ===== */
async function openPostModal(post) {
  activePost.value = JSON.parse(JSON.stringify(post))
  postModalOpen.value = true
  editMode.value = false
  editTitle.value = activePost.value.title
  editContent.value = activePost.value.content
  await loadComments(post.id)
}
function closePostModal() {
  postModalOpen.value = false
  activePost.value = null
  modalComments.value = []
  commentInput.value = ''
  editMode.value = false
}

/* ===== comments ===== */
async function loadComments(postId) {
  const data = await apiJson(`/users/post/${postId}/comments/ajax/`)
  modalComments.value = data.comments || []
}
async function submitComment() {
  const text = commentInput.value.trim()
  if (!text || !activePost.value) return

  const data = await apiJson(`/users/post/${activePost.value.id}/comments/ajax/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: text }),
  })

  if (data?.comment) {
    modalComments.value.push(data.comment)
    commentInput.value = ''
  }
}

/* ===== create post modal ===== */
function openCreateModal() {
  postCreateModalOpen.value = true
  newTitle.value = ''
  newContent.value = ''
  newImage.value = null
}
function closeCreateModal() {
  postCreateModalOpen.value = false
  newTitle.value = ''
  newContent.value = ''
  newImage.value = null
}
function onPickPostFile(e) {
  newImage.value = e.target.files?.[0] || null
}

async function createPost() {
  const title = newTitle.value.trim()
  const content = newContent.value.trim()
  if (!title && !content && !newImage.value) return

  // ✅ 권장: JSON API로 생성 (Django 추가 API 참고)
  const fd = new FormData()
  fd.append('title', title)
  fd.append('content', content)
  if (newImage.value) fd.append('share_trip', newImage.value)

  isLoading.value = true
  try {
    const res = await apiFetch('/api/users/posts/', { method: 'POST', body: fd })
    const data = await res.json()
    posts.value.unshift(data.post)
    closeCreateModal()
  } catch (e) {
    error.value = e.message
  } finally {
    isLoading.value = false
  }
}

/* ===== edit/delete post (owner) ===== */
function enterEditMode() {
  editMode.value = true
}
function cancelEditMode() {
  editMode.value = false
  if (activePost.value) {
    editTitle.value = activePost.value.title
    editContent.value = activePost.value.content
  }
}

async function saveEditPost() {
  if (!activePost.value) return
  const title = editTitle.value.trim()
  const content = editContent.value.trim()
  if (!title) return

  const data = await apiJson(`/users/post/${activePost.value.id}/update/ajax/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, content }),
  })

  if (data?.success) {
    activePost.value.title = data.post.title
    activePost.value.content = data.post.content

    const p = posts.value.find((x) => x.id === activePost.value.id)
    if (p) {
      p.title = data.post.title
      p.content = data.post.content
    }
    editMode.value = false
  }
}

async function deletePost() {
  if (!activePost.value) return
  if (!confirm('게시글을 삭제하시겠습니까?')) return

  // ✅ 권장: JSON delete API (Django 추가 API 참고)
  await apiJson(`/api/users/posts/${activePost.value.id}/delete/`, { method: 'POST' })

  posts.value = posts.value.filter((p) => p.id !== activePost.value.id)
  closePostModal()
}

/* ===== profile image modal ===== */
function openImageModal() {
  imageModalOpen.value = true
  selectedProfileFile.value = null
  previewUrl.value = ''
}
function closeImageModal() {
  imageModalOpen.value = false
  selectedProfileFile.value = null
  previewUrl.value = ''
}
function onPickProfileImage(e) {
  const f = e.target.files?.[0]
  if (!f) return
  selectedProfileFile.value = f
  previewUrl.value = URL.createObjectURL(f)
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = reject
    r.readAsDataURL(file)
  })
}

async function uploadProfileImage() {
  if (!selectedProfileFile.value) return

  const base64 = await fileToBase64(selectedProfileFile.value)
  const data = await apiJson('/users/upload-profile-image/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: base64 }),
  })

  if (data?.success) {
    profile.value.profile_img = data.image_url
    closeImageModal()
  }
}
</script>

<template>
  <main class="ts-profile-page">
    <div class="ts-shell ts-stack">
      <section class="ts-card pixel-corners">
        <div class="ts-profile-header">
          <button class="ts-settings-btn" type="button" @click="goSettings" aria-label="settings">
            ⚙️
          </button>

          <!-- avatar -->
          <div class="ts-avatar-wrap">
            <div class="ts-avatar" role="button" @click="openImageModal">
              <img v-if="profile.profile_img" :src="profile.profile_img" alt="profile" />
              <div v-else class="ts-avatar--placeholder">🍞</div>
            </div>

            <!-- ✅ 잘리지 않게: avatar 바깥으로 분리 -->
            <button
              class="ts-avatar-edit"
              type="button"
              @click="openImageModal"
              aria-label="edit-profile-image"
            >
              ✏️
            </button>
          </div>

          <div class="ts-profile-info">
            <h2 class="ts-profile-name">{{ profile.nickname }}</h2>
            <p class="ts-profile-username">@{{ profile.username }}</p>

            <div class="ts-counts">
              <button class="ts-count-btn" type="button" @click="openFollowModal('followers')">
                <p class="ts-count-num">{{ profile.follower_count }}</p>
                <p class="ts-count-label">팔로워</p>
              </button>

              <button class="ts-count-btn" type="button" @click="openFollowModal('followings')">
                <p class="ts-count-num">{{ profile.following_count }}</p>
                <p class="ts-count-label">팔로잉</p>
              </button>
            </div>

            <p v-if="error" class="ts-error">{{ error }}</p>
          </div>
        </div>

        <!-- posts -->
        <div class="ts-posts">
          <div class="ts-posts-head">
            <h3 class="ts-section-title">게시글</h3>
            <button class="ts-btn ts-btn--pink" type="button" @click="openCreateModal">
              게시글 작성
            </button>
          </div>

          <div class="ts-grid">
            <article
              v-for="post in posts"
              :key="post.id"
              class="ts-post-card"
              @click="openPostModal(post)"
            >
              <div class="ts-post-thumb">
                <img v-if="post.image" :src="post.image" alt="" />
                <span v-else>📸</span>
              </div>

              <div class="ts-post-body">
                <h4 class="ts-post-title">{{ post.title }}</h4>
                <p class="ts-post-content">{{ post.content }}</p>

                <button
                  type="button"
                  class="ts-like-btn"
                  :class="post.is_liked ? 'ts-like-btn--on' : ''"
                  @click.stop="toggleLike(post)"
                >
                  <span>{{ post.is_liked ? '❤️' : '🤍' }}</span>
                  <span>{{ post.like_count }}</span>
                </button>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>

    <!-- Follow modal -->
    <div v-if="followModalOpen" class="ts-overlay" @click.self="closeFollowModal">
      <div class="ts-mini-modal">
        <button class="ts-modal-close" type="button" @click="closeFollowModal">✕</button>
        <h3 class="ts-mini-title">{{ followModalType === 'followers' ? '팔로워' : '팔로잉' }}</h3>

        <div class="ts-mini-list">
          <div v-for="u in followList" :key="u.nickname" class="ts-mini-item">
            <div class="ts-mini-avatar">
              <img v-if="u.profile_img" :src="u.profile_img" alt="" />
              <span v-else>🍞</span>
            </div>
            <div style="flex: 1">
              <div class="ts-mini-name">{{ u.nickname }}</div>
              <div class="ts-mini-sub">@{{ u.username }}</div>
            </div>
          </div>

          <p v-if="followList.length === 0" class="ts-empty">아직 아무도 없습니다.</p>
        </div>
      </div>
    </div>

    <!-- Profile image modal -->
    <div v-if="imageModalOpen" class="ts-overlay" @click.self="closeImageModal">
      <div class="ts-image-modal pixel-corners">
        <h2 class="ts-image-title">프로필 이미지 변경</h2>

        <div class="ts-image-preview">
          <img v-if="previewUrl" :src="previewUrl" alt="" />
          <span v-else class="ts-image-emoji">🍞</span>
        </div>

        <input type="file" accept="image/*" class="ts-file" @change="onPickProfileImage" />

        <div class="ts-image-actions">
          <button
            class="ts-btn ts-btn--pink"
            type="button"
            :disabled="!selectedProfileFile"
            @click="uploadProfileImage"
          >
            업로드
          </button>
          <button class="ts-btn ts-btn--white" type="button" @click="closeImageModal">취소</button>
        </div>
      </div>
    </div>

    <!-- Create post modal -->
    <div v-if="postCreateModalOpen" class="ts-overlay" @click.self="closeCreateModal">
      <div class="ts-modal-sm pixel-corners">
        <h2 class="ts-modal-title">게시글 작성</h2>

        <input class="ts-input" v-model="newTitle" placeholder="제목 입력" />
        <textarea class="ts-textarea" v-model="newContent" rows="3" placeholder="내용 작성" />
        <input class="ts-input" type="file" @change="onPickPostFile" />

        <div class="ts-row-right">
          <button class="ts-btn ts-btn--pink" type="button" @click="createPost">
            게시글 올리기
          </button>
          <button class="ts-btn ts-btn--white" type="button" @click="closeCreateModal">취소</button>
        </div>
      </div>
    </div>

    <!-- Post modal -->
    <div v-if="postModalOpen" class="ts-overlay" @click.self="closePostModal">
      <div class="ts-modal">
        <button class="ts-modal-close" type="button" @click="closePostModal">✕</button>

        <div class="ts-modal-grid">
          <div class="ts-modal-media">
            <img v-if="activePost?.image" :src="activePost.image" alt="" />
            <span v-else class="ts-placeholder">📸</span>
          </div>

          <div class="ts-modal-body">
            <div v-if="activePost">
              <div v-if="!editMode">
                <h3 class="ts-modal-title2">{{ activePost.title }}</h3>
                <p class="ts-modal-writer">@{{ activePost.writer_username }}</p>
                <p class="ts-modal-content">{{ activePost.content }}</p>

                <button
                  class="ts-modal-like"
                  :class="activePost.is_liked ? 'ts-modal-like--on' : ''"
                  type="button"
                  @click="toggleModalLike"
                >
                  <span>{{ activePost.is_liked ? '❤️' : '🤍' }}</span>
                  <span>{{ activePost.like_count }}</span>
                </button>
              </div>

              <div v-else class="ts-edit-box">
                <input class="ts-input" v-model="editTitle" />
                <textarea class="ts-textarea" v-model="editContent" rows="4" />
                <div class="ts-row-right">
                  <button class="ts-btn ts-btn--pink" type="button" @click="saveEditPost">
                    수정 저장
                  </button>
                  <button class="ts-btn ts-btn--white" type="button" @click="cancelEditMode">
                    취소
                  </button>
                </div>
              </div>
            </div>

            <div>
              <p class="ts-comments-title">댓글</p>
              <div class="ts-comments-box">
                <div v-for="c in modalComments" :key="c.id">
                  <div class="ts-comment-row">
                    <span class="ts-comment-writer">@{{ c.writer_nickname }}</span>
                    <span class="ts-comment-text">{{ c.content }}</span>
                  </div>
                  <div class="ts-comment-time">{{ c.created_at }}</div>
                </div>

                <p v-if="modalComments.length === 0" class="ts-empty">
                  아직 댓글이 없습니다. 첫 댓글을 남겨보세요!
                </p>
              </div>

              <div class="ts-comment-compose">
                <input
                  class="ts-input"
                  v-model="commentInput"
                  placeholder="댓글을 입력하세요..."
                  @keydown.enter.prevent="submitComment"
                />
                <button class="ts-btn ts-btn--pink" type="button" @click="submitComment">
                  게시
                </button>
              </div>
            </div>

            <div class="ts-owner-actions">
              <button
                class="ts-btn ts-btn--pink"
                type="button"
                v-if="!editMode"
                @click="enterEditMode"
              >
                게시글 수정
              </button>
              <button class="ts-danger-link" type="button" @click="deletePost">게시글 삭제</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped lang="scss">
@use 'sass:color';

$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;
$ts-cream: #fff5e6;
$ts-cream-2: #ffe8cc;
$ts-pink: #ff69b4;
$ts-pink-hover: #ff1493;

.pixel-corners {
  border-radius: 1.25rem;
}

.ts-profile-page {
  padding: 1.5rem;
}
.ts-shell {
  max-width: 64rem;
  margin: 0 auto;
}
.ts-stack {
  display: grid;
  gap: 1.25rem;
}

.ts-card {
  background: rgba(255, 255, 255, 0.92);
  border: 4px solid $ts-border-brown;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
  overflow: hidden;
}

.ts-profile-header {
  position: relative;
  padding: 2rem;
  border-bottom: 4px solid $ts-border-brown;
  background: linear-gradient(90deg, $ts-pink 0%, #ffb6c1 100%);
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 1.5rem;
  align-items: center;
}
@media (max-width: 768px) {
  .ts-profile-header {
    grid-template-columns: 1fr;
    justify-items: center;
    text-align: center;
  }
}

.ts-settings-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 38px;
  height: 38px;
  border-radius: 999px;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  color: $ts-border-brown;
  cursor: pointer;
  display: grid;
  place-items: center;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
}

.ts-avatar-wrap {
  position: relative;
  width: 128px;
  height: 128px;
  justify-self: start;
}
@media (max-width: 768px) {
  .ts-avatar-wrap {
    justify-self: center;
  }
}

.ts-avatar {
  width: 128px;
  height: 128px;
  border-radius: 999px;
  overflow: hidden; /* 이미지 원형 유지 */
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.2);
  border: 4px solid #fff;
  background: #fff;
  cursor: pointer;
  display: grid;
  place-items: center;
}
.ts-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ts-avatar--placeholder {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center; /* ✅ 식빵 완전 중앙 */
  font-size: 3.2rem;
  line-height: 1;
}

.ts-avatar-edit {
  position: absolute;
  right: -6px; /* ✅ 원 밖으로 빼서 잘림 방지 */
  bottom: -6px; /* ✅ 원 밖으로 빼서 잘림 방지 */
  width: 42px;
  height: 42px;
  border-radius: 999px;
  background: $ts-pink;
  color: #fff;
  border: 2px solid #fff;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
  display: grid;
  place-items: center;
}

.ts-profile-info {
  color: #fff;
}
.ts-profile-name {
  margin: 0;
  font-size: 2.25rem;
  font-weight: 900;
  line-height: 1.15;
}
.ts-profile-username {
  margin: 0.35rem 0 0.9rem;
  font-size: 1.05rem;
  opacity: 0.85;
}

.ts-counts {
  display: flex;
  gap: 1.25rem;
  flex-wrap: wrap;
}
@media (max-width: 768px) {
  .ts-counts {
    justify-content: center;
  }
}

.ts-count-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: #fff;
}
.ts-count-num {
  margin: 0;
  font-size: 1.6rem;
  font-weight: 900;
  text-decoration: underline;
}
.ts-count-label {
  margin: 0.15rem 0 0;
  font-size: 0.85rem;
  opacity: 0.85;
}

.ts-error {
  margin-top: 0.75rem;
  color: #fff;
  font-weight: 900;
}

.ts-posts {
  padding: 2rem;
}
.ts-posts-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.ts-section-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 900;
  color: $ts-border-brown;
}

.ts-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}
@media (min-width: 640px) {
  .ts-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (min-width: 1024px) {
  .ts-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.ts-post-card {
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.14);
  border-radius: 0.95rem;
  overflow: hidden;
  cursor: pointer;
  transition:
    transform 0.08s ease,
    box-shadow 0.2s ease;
}
.ts-post-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.12);
}

.ts-post-thumb {
  width: 100%;
  height: 192px;
  background: $ts-cream-2;
  display: grid;
  place-items: center;
  font-size: 2.6rem;
}
.ts-post-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ts-post-body {
  padding: 1rem;
}
.ts-post-title {
  margin: 0;
  font-weight: 900;
  color: $ts-border-brown;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ts-post-content {
  margin: 0.5rem 0 0.75rem;
  font-size: 0.9rem;
  color: $ts-text-brown;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ts-like-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  border: 1px solid $ts-pink;
  background: #fff;
  color: $ts-pink;
  cursor: pointer;
}
.ts-like-btn--on {
  background: $ts-pink;
  border-color: $ts-pink;
  color: #fff;
}

.ts-btn {
  padding: 0.65rem 1rem;
  border-radius: 0.7rem;
  font-weight: 900;
  border: 2px solid $ts-border-brown;
  cursor: pointer;
}
.ts-btn--pink {
  background: $ts-pink;
  color: #fff;
}
.ts-btn--pink:hover {
  background: $ts-pink-hover;
}
.ts-btn--white {
  background: #fff;
  color: $ts-text-brown;
}

.ts-input {
  width: 100%;
  padding: 0.65rem 0.85rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(0, 0, 0, 0.18);
  background: #fff;
}
.ts-textarea {
  width: 100%;
  min-height: 76px;
  resize: vertical;
  padding: 0.7rem 0.85rem;
  border-radius: 0.7rem;
  border: 1px solid rgba(0, 0, 0, 0.18);
}

.ts-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  padding: 1rem;
  display: grid;
  place-items: center;
  z-index: 50;
}

.ts-mini-modal {
  width: 100%;
  max-width: 22rem;
  background: #fff;
  border-radius: 1.25rem;
  padding: 1.25rem;
  position: relative;
}
.ts-mini-title {
  margin: 0 0 0.9rem;
  color: $ts-border-brown;
  font-weight: 900;
  font-size: 1.2rem;
}
.ts-mini-list {
  max-height: 320px;
  overflow-y: auto;
  display: grid;
  gap: 0.75rem;
}
.ts-mini-item {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.ts-mini-avatar {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  overflow: hidden;
  background: $ts-cream-2;
  display: grid;
  place-items: center;
  border: 1px solid rgba(0, 0, 0, 0.15);
}
.ts-mini-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ts-mini-name {
  font-weight: 900;
  color: $ts-border-brown;
}
.ts-mini-sub {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.1rem;
}

.ts-modal-close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: none;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  cursor: pointer;
  display: grid;
  place-items: center;
}

.ts-image-modal {
  width: 100%;
  max-width: 28rem;
  background: #fff;
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  padding: 1.75rem;
  box-shadow: 0 26px 70px rgba(0, 0, 0, 0.22);
}
.ts-image-title {
  margin: 0 0 1rem;
  text-align: center;
  color: $ts-border-brown;
  font-weight: 900;
  font-size: 1.45rem;
}
.ts-image-preview {
  width: 192px;
  height: 192px;
  margin: 0 auto;
  border-radius: 999px;
  overflow: hidden;
  border: 4px solid $ts-border-brown;
  background: $ts-cream-2;
  display: grid;
  place-items: center;
}
.ts-image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ts-image-emoji {
  font-size: 3rem;
}
.ts-file {
  width: 100%;
  margin-top: 0.9rem;
}
.ts-image-actions {
  margin-top: 1rem;
  display: flex;
  gap: 0.75rem;
  justify-content: center;
}

.ts-modal-sm {
  width: 100%;
  max-width: 34rem;
  background: #fff;
  border-radius: 1.25rem;
  border: 4px solid $ts-border-brown;
  padding: 1.25rem;
  display: grid;
  gap: 0.75rem;
}
.ts-modal-title {
  margin: 0 0 0.25rem;
  color: $ts-border-brown;
  font-weight: 900;
  font-size: 1.3rem;
}
.ts-row-right {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.ts-modal {
  width: 100%;
  max-width: 56rem;
  background: #fff;
  border-radius: 1.25rem;
  overflow: hidden;
  position: relative;
  box-shadow: 0 26px 70px rgba(0, 0, 0, 0.22);
}
.ts-modal-grid {
  display: grid;
  grid-template-columns: 1fr;
}
@media (min-width: 1024px) {
  .ts-modal-grid {
    grid-template-columns: 1fr 1fr;
  }
}
.ts-modal-media {
  background: #000;
  display: grid;
  place-items: center;
  min-height: 320px;
}
.ts-modal-media img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.ts-placeholder {
  font-size: 3.2rem;
  color: #fff;
  user-select: none;
}

.ts-modal-body {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.ts-modal-title2 {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 900;
  color: $ts-border-brown;
}
.ts-modal-writer {
  margin: 0.2rem 0 0;
  font-size: 0.9rem;
  color: #6b7280;
}
.ts-modal-content {
  margin: 0.75rem 0 0;
  color: #6b4f2a;
  white-space: pre-wrap;
  line-height: 1.6;
}

.ts-modal-like {
  margin-top: 0.9rem;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.05rem;
  padding: 0.5rem 0.85rem;
  border-radius: 999px;
  border: 2px solid $ts-pink;
  background: #fff;
  color: $ts-pink;
  cursor: pointer;
}
.ts-modal-like--on {
  background: $ts-pink;
  color: #fff;
}

.ts-comments-title {
  font-weight: 900;
  color: $ts-border-brown;
  margin: 0;
}
.ts-comments-box {
  max-height: 170px;
  overflow-y: auto;
  display: grid;
  gap: 0.55rem;
  font-size: 0.9rem;
}
.ts-comment-row {
  display: flex;
  gap: 0.5rem;
}
.ts-comment-writer {
  font-weight: 900;
  color: $ts-border-brown;
}
.ts-comment-text {
  color: #6b4f2a;
  word-break: break-word;
}
.ts-comment-time {
  font-size: 0.75rem;
  color: #9ca3af;
}

.ts-comment-compose {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
@media (max-width: 640px) {
  .ts-comment-compose {
    flex-direction: column;
    align-items: stretch;
  }
}

.ts-owner-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.ts-danger-link {
  border: none;
  background: transparent;
  color: #dc2626;
  font-weight: 900;
  cursor: pointer;
}

.ts-empty {
  color: #9ca3af;
  font-size: 0.85rem;
  margin-top: 0.5rem;
}
</style>
