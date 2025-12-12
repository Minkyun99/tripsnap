<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'

const router = useRouter()
const userStore = useUserStore()

const isAuthenticated = computed(() => userStore.isAuthenticated)
const user = computed(() => userStore.user)

// 표시용 닉네임
const displayName = computed(() => {
  const u = user.value
  if (!u) return ''
  return u.nickname || u.username || u.email || ''
})

// 나중에 API 연동 시 실제 값으로 교체 예정
const stats = ref({
  posts: 3,
  followers: 12,
  followings: 5,
})

// 게시글 리스트 (현재는 목업 데이터)
const posts = ref([
  {
    id: 1,
    bakeryName: '몽심 대흥점',
    location: '대전 중구',
    createdAt: '2025-12-10',
    content:
      '치즈가 듬뿍 들어간 크루아상이 정말 맛있었어요. 담백하면서도 고소해서 여행 첫날 아침으로 딱이었습니다.',
    likeCount: 24,
    commentCount: 5,
  },
  {
    id: 2,
    bakeryName: '성심당 본점',
    location: '대전 중구 은행동',
    createdAt: '2025-12-05',
    content: '튀김소보로는 언제 먹어도 실패가 없습니다. 줄이 길지만 기다릴 가치가 있어요.',
    likeCount: 103,
    commentCount: 12,
  },
  {
    id: 3,
    bakeryName: '어니언 앙성점',
    location: '서울 성동구',
    createdAt: '2025-11-30',
    content: '여행 마지막 날에 들른 카페 겸 베이커리. 포카치아와 커피 조합이 최고였습니다.',
    likeCount: 56,
    commentCount: 8,
  },
])

// 버튼 동작은 나중에 실제 기능 구현 시 교체
const goToPostCreate = () => {
  // TODO: 글 작성 화면으로 라우팅 (예: /post/create)
  alert('게시글 작성 기능은 추후 구현 예정입니다.')
}

const handleFollowToggle = () => {
  // TODO: 팔로우/언팔로우 API 연결
  alert('팔로우 기능은 추후 구현 예정입니다.')
}

const handleLikeClick = (postId) => {
  // TODO: 좋아요 토글 API 연결
  alert(`게시글 #${postId} 좋아요 기능은 추후 구현 예정입니다.`)
}

const handleCommentSubmit = (postId) => {
  // TODO: 댓글 작성 API 연결
  alert(`게시글 #${postId} 댓글 작성 기능은 추후 구현 예정입니다.`)
}

const goLogin = () => {
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="profile-page">
    <div class="profile-layout">
      <!-- 왼쪽: 프로필 카드 -->
      <aside class="profile-sidebar pixel-corners">
        <!-- 비로그인 상태 -->
        <div v-if="!isAuthenticated" class="profile-guest">
          <h2 class="profile-title">프로필을 보려면 로그인이 필요합니다</h2>
          <p class="profile-text">
            Tripsnap의 내 프로필, 팔로워, 게시글 기능을 사용하려면 먼저 로그인 해주세요.
          </p>
          <button type="button" class="btn-primary" @click="goLogin">로그인 하러 가기</button>
        </div>

        <!-- 로그인 상태 -->
        <div v-else class="profile-info">
          <div class="profile-avatar">
            <span class="profile-avatar-icon">🍞</span>
          </div>

          <h2 class="profile-name">
            {{ displayName }}
          </h2>

          <p class="profile-username">@{{ user?.username || 'user' }}</p>

          <div class="profile-stats">
            <div class="profile-stat">
              <span class="profile-stat-label">게시글</span>
              <span class="profile-stat-value">{{ stats.posts }}</span>
            </div>
            <div class="profile-stat">
              <span class="profile-stat-label">팔로워</span>
              <span class="profile-stat-value">{{ stats.followers }}</span>
            </div>
            <div class="profile-stat">
              <span class="profile-stat-label">팔로잉</span>
              <span class="profile-stat-value">{{ stats.followings }}</span>
            </div>
          </div>

          <div class="profile-actions">
            <button type="button" class="btn-primary" @click="goToPostCreate">게시글 작성</button>

            <button type="button" class="btn-outline" @click="handleFollowToggle">팔로우</button>
          </div>

          <p class="profile-hint">
            나중에 이 영역에서 프로필 수정, 프로필 이미지 변경, 자기소개 등도 관리할 수 있습니다.
          </p>
        </div>
      </aside>

      <!-- 오른쪽: 게시글 리스트 -->
      <section class="profile-main">
        <h3 class="posts-title">빵집 여행 기록</h3>

        <!-- 비로그인 상태 안내 -->
        <div v-if="!isAuthenticated" class="posts-empty pixel-corners">
          <p>로그인 후 내 게시글과 다른 사람의 프로필을 확인할 수 있습니다.</p>
        </div>

        <!-- 로그인 상태: 게시글 목록 -->
        <div v-else>
          <article v-for="post in posts" :key="post.id" class="post-card pixel-corners">
            <header class="post-header">
              <div class="post-header-left">
                <h4 class="post-bakery">
                  {{ post.bakeryName }}
                </h4>
                <p class="post-location">
                  {{ post.location }}
                </p>
              </div>
              <div class="post-meta">
                <span class="post-date">{{ post.createdAt }}</span>
              </div>
            </header>

            <p class="post-content">
              {{ post.content }}
            </p>

            <div class="post-actions">
              <button type="button" class="post-action-btn" @click="handleLikeClick(post.id)">
                ❤️ 좋아요
                <span class="post-count">{{ post.likeCount }}</span>
              </button>
              <button type="button" class="post-action-btn" @click="handleCommentSubmit(post.id)">
                💬 댓글
                <span class="post-count">{{ post.commentCount }}</span>
              </button>
            </div>

            <div class="post-comment-input">
              <input
                type="text"
                class="comment-field"
                placeholder="댓글을 입력해 주세요. (기능은 추후 구현)"
                @keyup.enter="handleCommentSubmit(post.id)"
              />
              <button type="button" class="btn-small" @click="handleCommentSubmit(post.id)">
                등록
              </button>
            </div>
          </article>

          <!-- 게시글이 없는 경우 -->
          <div v-if="posts.length === 0" class="posts-empty pixel-corners">
            <p>아직 작성된 게시글이 없습니다. 첫 빵집 여행 후 후기를 남겨보세요!</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped lang="scss">
$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;

.profile-page {
  min-height: calc(100vh - 160px);
  padding: 2.5rem 1rem;
  display: flex;
  justify-content: center;
}

.profile-layout {
  max-width: 72rem;
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 260px) minmax(0, 1fr);
  gap: 1.5rem;
}

/* 왼쪽 사이드바 */
.profile-sidebar {
  background: rgba(255, 255, 255, 0.96);
  border-radius: 1.25rem;
  border: 3px solid $ts-border-brown;
  padding: 1.75rem 1.5rem;
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.12);
}

.profile-guest {
  text-align: center;
}

.profile-title {
  font-size: 1.35rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 0.75rem;
}

.profile-text {
  font-size: 0.95rem;
  color: $ts-text-brown;
  margin-bottom: 1.2rem;
}

.profile-info {
  text-align: center;
}

.profile-avatar {
  width: 5rem;
  height: 5rem;
  border-radius: 999px;
  margin: 0 auto 1rem;
  border: 3px solid $ts-border-brown;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fffaf3;
}

.profile-avatar-icon {
  font-size: 2.5rem;
}

.profile-name {
  font-size: 1.5rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 0.25rem;
}

.profile-username {
  font-size: 0.9rem;
  color: $ts-text-brown;
  margin-bottom: 1.25rem;
}

.profile-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.profile-stat {
  background: #fff7ec;
  border-radius: 0.75rem;
  padding: 0.5rem 0.4rem;
}

.profile-stat-label {
  display: block;
  font-size: 0.8rem;
  color: $ts-text-brown;
}

.profile-stat-value {
  display: block;
  font-size: 1.1rem;
  font-weight: 700;
  color: $ts-border-brown;
}

.profile-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-bottom: 0.75rem;
}

.profile-hint {
  font-size: 0.8rem;
  color: $ts-text-brown;
  margin-top: 0.25rem;
}

/* 오른쪽 메인 영역 */
.profile-main {
  background: rgba(255, 255, 255, 0.96);
  border-radius: 1.25rem;
  border: 3px solid $ts-border-brown;
  padding: 1.75rem 1.5rem;
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.12);
}

.posts-title {
  font-size: 1.3rem;
  font-weight: 700;
  color: $ts-border-brown;
  margin-bottom: 1.25rem;
}

.posts-empty {
  margin-top: 0.5rem;
  padding: 1.5rem;
  border-radius: 0.9rem;
  border: 2px dashed rgba(139, 69, 19, 0.4);
  text-align: center;
  font-size: 0.9rem;
  color: $ts-text-brown;
}

/* 게시글 카드 */
.post-card {
  background: #fffdf8;
  border-radius: 1rem;
  border: 2px solid rgba(210, 105, 30, 0.4);
  padding: 1.25rem 1.1rem;
  margin-bottom: 1rem;
}

.post-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
}

.post-header-left {
  min-width: 0;
}

.post-bakery {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: $ts-border-brown;
}

.post-location {
  margin: 0.1rem 0 0;
  font-size: 0.8rem;
  color: $ts-text-brown;
}

.post-meta {
  font-size: 0.8rem;
  color: #777;
  white-space: nowrap;
}

.post-date {
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  background: #fff7ec;
}

.post-content {
  margin: 0.4rem 0 0.8rem;
  font-size: 0.9rem;
  color: #333;
  line-height: 1.5;
}

/* 게시글 하단 액션 */
.post-actions {
  display: flex;
  gap: 0.6rem;
  margin-bottom: 0.7rem;
}

.post-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.85rem;
  padding: 0.35rem 0.8rem;
  border-radius: 999px;
  border: 1px solid rgba(210, 105, 30, 0.5);
  background: #fff;
  cursor: pointer;
}

.post-count {
  font-weight: 600;
  color: $ts-border-brown;
}

/* 댓글 입력 */
.post-comment-input {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.2rem;
}

.comment-field {
  flex: 1;
  font-size: 0.85rem;
  padding: 0.45rem 0.55rem;
  border-radius: 0.6rem;
  border: 1px solid rgba(210, 105, 30, 0.4);
}

.comment-field:focus {
  outline: none;
  border-color: $ts-border-brown;
}

/* 버튼 공통 스타일 */
.btn-primary {
  padding: 0.6rem 1.4rem;
  font-size: 0.9rem;
  font-weight: 700;
  color: #fff;
  background-color: $ts-border-brown;
  border-radius: 999px;
  border: 2px solid $ts-border-brown;
  cursor: pointer;
}

.btn-outline {
  padding: 0.55rem 1.3rem;
  font-size: 0.9rem;
  font-weight: 700;
  color: $ts-border-brown;
  background-color: #fffdf8;
  border-radius: 999px;
  border: 2px solid $ts-border-brown;
  cursor: pointer;
}

.btn-small {
  padding: 0.35rem 0.8rem;
  font-size: 0.8rem;
  font-weight: 600;
  border-radius: 0.6rem;
  border: 1px solid $ts-border-brown;
  background-color: #fffdf8;
  cursor: pointer;
}

/* 반응형 */
@media (max-width: 768px) {
  .profile-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .profile-page {
    padding-top: 1.5rem;
  }
}
</style>
