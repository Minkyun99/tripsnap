<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useProfileStore } from '@/stores/profile'
import { useUserStore } from '@/stores/users'

import PostModal from '@/components/profile/PostModal.vue'

const router = useRouter()
const route = useRoute()

const ps = useProfileStore()
const userStore = useUserStore()

const { posts } = storeToRefs(ps)

// 현재 URL의 nickname 파라미터
const nicknameParam = computed(() => String(route.params.nickname || ''))

// ✅ 내가 보고 있는 프로필이 “내 것인지”
const isOwner = computed(() => {
  const me = userStore.user
  const myNickname = me?.nickname || ''
  return !!me && !!nicknameParam.value && myNickname === nicknameParam.value
})

// ---------------------------
// 프로필/게시글 로딩 함수
// ---------------------------
async function fetchProfile() {
  const nick = nicknameParam.value
  if (!nick) return

  // 내 정보 동기화 (로그인 안돼 있거나 expired된 경우 대비)
  await userStore.fetchMe().catch(() => {})

  // 닉네임 기준 프로필+게시글 로드
  await ps.loadProfileByNickname(nick)
}

// ---------------------------
// 초기 로드
// ---------------------------
onMounted(async () => {
  await fetchProfile()
})

// ---------------------------
// 닉네임이 바뀔 때마다 새로 로딩
//  - 팔로우/팔로잉 목록에서 다른 유저 클릭
//  - 다른 사람 팔로우 목록에서 내 아이디 클릭 등
// ---------------------------
watch(
  () => route.params.nickname,
  async (newNick, oldNick) => {
    if (!newNick || newNick === oldNick) return

    // 프로필 주인이 바뀌는 상황이므로 모달들 정리
    ps.closePostModal()
    ps.closeFollowModal()

    await fetchProfile()
  }
)

// ---------------------------
// 페이지 이동 시 모달 정리
// ---------------------------
onBeforeUnmount(() => {
  ps.closeFollowModal()
  ps.closePostModal()
})

// ---------------------------
// 헤더 버튼 동작
// ---------------------------
function onHeaderButtonClick() {
  if (isOwner.value) {
    // ⚙️ → 설정
    router.push({ name: 'settings' }).catch(() => {})
  } else {
    // 🏠 → 내 프로필 (전용 페이지)
    router.push({ name: 'profile' }).catch(() => {})
  }
}

// ---------------------------
// 게시글 모달
// ---------------------------
function openPostModal(post) {
  ps.openPostModal(post)
}

// ---------------------------
// 팔로우 모달에서 프로필 이동
// ---------------------------
function goProfileFromFollow(nickname) {
  ps.closeFollowModal()

  const me = userStore.user
  const myNickname = me?.nickname || ''

  // ✅ 클릭한 닉네임이 "나"라면 → 내 전용 프로필 페이지(/profile)로 이동
  if (myNickname && nickname === myNickname) {
    router.push({ name: 'profile' }).catch(() => {})
  } else {
    // 그 외에는 기존대로 디테일 페이지(/profile/:nickname)
    router.push({ name: 'profile-detail', params: { nickname } }).catch(() => {})
  }
}
</script>

<template>
  <main class="ts-profile-page">
    <div class="ts-shell ts-stack">
      <section class="ts-card pixel-corners">
        <!-- =========================
             프로필 헤더
        ========================== -->
        <div class="ts-profile-header">
          <!-- ✅ 설정 / 홈 버튼 -->
          <button
            class="ts-settings-btn"
            type="button"
            @click="onHeaderButtonClick"
            :aria-label="isOwner ? 'settings' : 'my-profile'"
          >
            {{ isOwner ? '⚙️' : '🏠' }}
          </button>

          <!-- 아바타 -->
          <div class="ts-avatar-wrap">
            <div class="ts-avatar-core">
              <img v-if="ps.profileImgUrl" :src="ps.profileImgUrl" alt="profile" />
              <div v-else class="ts-avatar-placeholder">🍞</div>
            </div>
          </div>

          <!-- 정보 -->
          <div class="ts-profile-info">
            <h2 class="ts-profile-name">{{ ps.nickname }}</h2>
            <p class="ts-profile-username">@{{ ps.username }}</p>

            <!-- 팔로워 / 팔로잉 -->
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

            <!-- 팔로우 버튼 -->
            <div class="ts-owner-actions-inline">
              <button
                v-if="!isOwner"
                class="ts-btn ts-btn--pink"
                type="button"
                @click="ps.toggleFollow(nicknameParam)"
              >
                {{ ps.isFollowing ? '언팔로우' : '팔로우' }}
              </button>
            </div>
          </div>
        </div>

        <!-- =========================
             게시글 목록
        ========================== -->
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

    <!-- =========================
         팔로워 / 팔로잉 모달
    ========================== -->
    <div v-if="ps.followModalOpen" class="ts-overlay" @click.self="ps.closeFollowModal()">
      <div class="ts-mini-modal">
        <button class="ts-modal-close" type="button" @click="ps.closeFollowModal()">✕</button>

        <h3 class="ts-mini-title">
          {{ ps.followModalType === 'followers' ? '팔로워' : '팔로잉' }}
        </h3>

        <div class="ts-mini-list">
          <!-- ✅ 비공개 메시지 -->
          <p v-if="ps.followListPrivateMessage" class="ts-muted">
            {{ ps.followListPrivateMessage }}
          </p>

          <!-- 목록 -->
          <div v-for="u in ps.followList" :key="u.nickname" class="ts-mini-item">
            <div class="ts-mini-avatar">
              <img v-if="u.profile_img" :src="u.profile_img" />
              <span v-else>🍞</span>
            </div>

            <div style="flex: 1">
              <div class="ts-mini-name" @click="goProfileFromFollow(u.nickname)">
                {{ u.nickname }}
              </div>
              <div class="ts-mini-sub">@{{ u.username }}</div>
            </div>
          </div>

          <p v-if="!ps.followListPrivateMessage && ps.followList.length === 0" class="ts-muted">
            아직 아무도 없습니다.
          </p>
        </div>
      </div>
    </div>

    <!-- 게시글 모달 -->
    <PostModal v-if="ps.postModalOpen" @close="ps.closePostModal()" />
  </main>
</template>

<style scoped lang="scss">
@use '@/assets/styles/users/profile.scss';
</style>
