<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia' // ✅ 추가
import { useProfileStore } from '../stores/profile'

import ProfileImageModal from '../components/profile/ProfileImageModal.vue'
import CreatePostModal from '../components/profile/CreatePostModal.vue'
import PostModal from '../components/profile/PostModal.vue'

const router = useRouter()
const ps = useProfileStore()

const { posts, profile } = storeToRefs(ps)
const searchQ = ref('')

// 내 프로필이므로 isOwner는 항상 true
const isOwner = computed(() => true)
const nickname = computed(() => profile.value?.nickname || '')
const username = computed(() => profile.value?.username || '')
const profileImgUrl = computed(() => ps.profileImgUrl)

onMounted(async () => {
  await ps.loadMyProfile()
})

function goSettings() {
  // 실제 settings route가 있으면 name만 맞춰주세요.
  router.push({ name: 'settings' }).catch(() => {})
}

async function openFollowModal(type) {
  await ps.openFollowModal(type, profile.value?.nickname || '')
}

function goProfile(nick) {
  router.push({ name: 'profile-detail', params: { nickname: nick } })
}

async function onSearch() {
  const foundNick = await ps.searchProfile(searchQ.value)
  router.push({ name: 'profile-detail', params: { nickname: foundNick } })
}

function openPostModal(post) {
  ps.openPostModal(post) // store에 해당 action이 있어야 함
}

async function toggleLike(post) {
  await ps.toggleLike(post.id) // store에 해당 action이 있어야 함
}
</script>

<template>
  <main class="ts-profile-page">
    <div class="ts-shell ts-stack">
      <!-- 프로필 카드 -->
      <section class="ts-card pixel-corners">
        <div class="ts-profile-header">
          <button class="ts-settings-btn" type="button" @click="goSettings" aria-label="settings">
            ⚙️
          </button>

          <!-- avatar (잘림 문제 해결 구조) -->
          <div class="ts-avatar-wrap">
            <div class="ts-avatar-core" role="button" @click="ps.openImageModal()">
              <img v-if="profileImgUrl" :src="profileImgUrl" alt="profile" />
              <div v-else class="ts-avatar-placeholder">🍞</div>
            </div>

            <button
              class="ts-avatar-edit"
              type="button"
              @click="ps.openImageModal()"
              aria-label="edit-profile-image"
              title="프로필 사진 변경"
            >
              ✏️
            </button>
          </div>

          <div class="ts-profile-info">
            <h2 class="ts-profile-name">{{ nickname }}</h2>
            <p class="ts-profile-username">@{{ username }}</p>

            <div class="ts-counts">
              <button class="ts-count-btn" type="button" @click="openFollowModal('followers')">
                <p class="ts-count-num">{{ ps.followerCount }}</p>
                <p class="ts-count-label">팔로워</p>
              </button>

              <button class="ts-count-btn" type="button" @click="openFollowModal('followings')">
                <p class="ts-count-num">{{ ps.followingCount }}</p>
                <p class="ts-count-label">팔로잉</p>
              </button>
            </div>

            <div class="ts-owner-actions-inline">
              <button class="ts-btn ts-btn--pink" type="button" @click="ps.openCreatePostModal()">
                게시글 작성
              </button>
            </div>
          </div>
        </div>

        <!-- 검색 바(내 프로필 페이지에도 유지하고 싶다면) -->
        <div class="ts-search-wrap">
          <form class="ts-search-bar" @submit.prevent="onSearch">
            <label class="ts-search-label">다른 사람 프로필 검색</label>
            <input class="ts-input" v-model="searchQ" placeholder="닉네임 또는 이메일" />
            <button class="ts-btn ts-btn--pink" type="submit">검색</button>
          </form>
        </div>

        <!-- 게시글 그리드 -->
        <div class="ts-posts">
          <div class="ts-grid">
            <article
              v-for="post in posts"
              :key="post.id"
              class="ts-post-card"
              @click="openPostModal(post)"
            >
              <!-- 이미지 영역 -->
              <div class="ts-post-thumb">
                <img v-if="post.image" :src="post.image" alt="post image" />
                <div v-else class="ts-post-thumb--placeholder">📸</div>
              </div>

              <!-- 텍스트 영역 -->
              <div class="ts-post-body">
                <h4 class="ts-post-title">{{ post.title }}</h4>

                <p class="ts-post-content">
                  {{ post.content }}
                </p>

                <button
                  type="button"
                  class="ts-like-btn"
                  :class="{ 'ts-like-btn--on': post.is_liked }"
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

    <!-- 팔로워/팔로잉 모달 -->
    <div v-if="ps.followModalOpen" class="ts-overlay" @click.self="ps.closeFollowModal()">
      <div class="ts-mini-modal">
        <button class="ts-modal-close" type="button" @click="ps.closeFollowModal()">✕</button>
        <h3 class="ts-mini-title">
          {{ ps.followModalType === 'followers' ? '팔로워' : '팔로잉' }}
        </h3>

        <div class="ts-mini-list">
          <div v-for="u in ps.followList" :key="u.nickname" class="ts-mini-item">
            <div class="ts-mini-avatar">
              <img v-if="u.profile_img" :src="u.profile_img" />
              <span v-else>🍞</span>
            </div>
            <div style="flex: 1">
              <div class="ts-mini-name" @click="goProfile(u.nickname)">{{ u.nickname }}</div>
              <div class="ts-mini-sub">@{{ u.username }}</div>
            </div>
          </div>

          <p v-if="ps.followList.length === 0" class="ts-muted">아직 아무도 없습니다.</p>
        </div>
      </div>
    </div>

    <!-- 모달들 -->
    <ProfileImageModal v-if="ps.imageModalOpen" @close="ps.closeImageModal()" />
    <CreatePostModal v-if="ps.createPostModalOpen" @close="ps.closeCreatePostModal()" />
    <PostModal v-if="ps.postModalOpen" @close="ps.closePostModal()" />
  </main>
</template>

<style scoped lang="scss">
@use '@/assets/profile.scss' as *;
</style>
