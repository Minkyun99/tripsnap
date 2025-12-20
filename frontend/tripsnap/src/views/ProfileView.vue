<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useProfileStore } from '@/stores/profile'

import ProfileImageModal from '@/components/profile/ProfileImageModal.vue'
import CreatePostModal from '@/components/profile/CreatePostModal.vue'
import PostModal from '@/components/profile/PostModal.vue'

const emit = defineEmits(['close'])

const router = useRouter()
const ps = useProfileStore()
const { posts } = storeToRefs(ps)

const searchQ = ref('')

// 현재 슬라이드 인덱스
const currentIndex = ref(0)

// Pinia에서 현재 선택된 게시물 정보 가져오기
const post = computed(() => ps.currentPost)

function prevSlide() {
  if (currentIndex.value > 0) currentIndex.value--
}

function nextSlide() {
  if (currentIndex.value < (post.value.images?.length || 0) - 1) {
    currentIndex.value++
  }
}

onMounted(async () => {
  await ps.loadMyProfile()
})

// ✅ (추가) 페이지를 떠날 때 follow 모달이 다른 페이지에 “남아있지 않도록” 정리
onBeforeUnmount(() => {
  ps.closeFollowModal()
})

function goSettings() {
  router.push({ name: 'settings' }).catch(() => {})
}

async function onSearch() {
  const foundNick = await ps.searchProfile(searchQ.value)
  router.push({ name: 'profile-detail', params: { nickname: foundNick } }).catch(() => {})
}

function openPostModal(post) {
  ps.openPostModal(post)
}

// ✅ (수정) 템플릿에서 멀티라인 @click 제거용
function goProfileFromFollow(nickname) {
  ps.closeFollowModal()
  router.push({ name: 'profile-detail', params: { nickname } }).catch(() => {})
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

          <div class="ts-avatar-wrap">
            <div class="ts-avatar-core" role="button" @click="ps.openImageModal()">
              <img v-if="ps.profileImgUrl" :src="ps.profileImgUrl" alt="profile" />
              <div v-else class="ts-avatar-placeholder">🍞</div>
            </div>

            <button
              class="ts-avatar-edit"
              type="button"
              @click="ps.openImageModal()"
              aria-label="edit"
            >
              ✏️
            </button>
          </div>

          <div class="ts-profile-info">
            <h2 class="ts-profile-name">{{ ps.nickname }}</h2>
            <p class="ts-profile-username">@{{ ps.username }}</p>

            <div class="ts-counts">
              <button class="ts-count-btn" type="button" @click="ps.openFollowModal('followers')">
                <p class="ts-count-num">{{ ps.followerCount }}</p>
                <p class="ts-count-label">팔로워</p>
              </button>

              <button class="ts-count-btn" type="button" @click="ps.openFollowModal('followings')">
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

        <div class="ts-posts">
          <div class="ts-grid">
            <article
              v-for="post in posts"
              :key="post.id"
              class="ts-post-card"
              @click="openPostModal(post)"
            >
              <div class="ts-post-thumb">
                <img v-if="post.image" :src="post.image" alt="post image" />
                <div v-else class="ts-post-thumb--placeholder">📸</div>
              </div>

              <div class="ts-post-body">
                <h4 class="ts-post-title">{{ post.title }}</h4>
                <p class="ts-post-content">{{ post.content }}</p>

                <button
                  type="button"
                  class="ts-like-btn"
                  :class="{ 'ts-like-btn--on': post.is_liked }"
                  @click.stop="ps.toggleLike(post.id)"
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
              <!-- ✅ (수정) 멀티라인 @click 제거 -->
              <div class="ts-mini-name" @click="goProfileFromFollow(u.nickname)">
                {{ u.nickname }}
              </div>
              <div class="ts-mini-sub">@{{ u.username }}</div>
            </div>
          </div>

          <!-- ✅ (추가) 비공개 문구 -->
          <p v-if="ps.followListPrivateMessage" class="ts-muted">
            {{ ps.followListPrivateMessage }}
          </p>

          <p v-else-if="ps.followList.length === 0" class="ts-muted">아직 아무도 없습니다.</p>
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
