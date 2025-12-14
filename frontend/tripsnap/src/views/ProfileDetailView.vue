<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProfileStore } from '../stores/profile'
import PostModal from '../components/profile/PostModal.vue'

const route = useRoute()
const router = useRouter()
const ps = useProfileStore()

const searchQ = ref('')

const targetNick = computed(() => route.params.nickname)
const nickname = computed(() => ps.targetUser?.nickname || '')
const username = computed(() => ps.targetUser?.username || '')

const isOwner = computed(() => false)

onMounted(async () => {
  await ps.loadProfileByNickname(targetNick.value)
})

async function toggleFollow() {
  await ps.toggleFollow(nickname.value)
}

function goProfile(nick) {
  router.push({ name: 'profile-detail', params: { nickname: nick } })
}

async function onSearch() {
  const foundNick = await ps.searchProfile(searchQ.value)
  router.push({ name: 'profile-detail', params: { nickname: foundNick } })
}
</script>

<template>
  <main class="ts-profile-page">
    <div class="ts-shell ts-stack">
      <section class="ts-card pixel-corners">
        <div class="ts-profile-header">
          <div class="ts-avatar-wrap">
            <div class="ts-avatar-core">
              <img v-if="ps.profileImgUrl" :src="ps.profileImgUrl" alt="profile" />
              <div v-else class="ts-avatar-placeholder">🍞</div>
            </div>
          </div>

          <div class="ts-profile-info">
            <h2 class="ts-profile-name">{{ nickname }}</h2>
            <p class="ts-profile-username">@{{ username }}</p>

            <div class="ts-counts">
              <button
                class="ts-count-btn"
                type="button"
                @click="ps.openFollowModal('followers', nickname)"
              >
                <p class="ts-count-num">{{ ps.followerCount }}</p>
                <p class="ts-count-label">팔로워</p>
              </button>

              <button
                class="ts-count-btn"
                type="button"
                @click="ps.openFollowModal('followings', nickname)"
              >
                <p class="ts-count-num">{{ ps.followingCount }}</p>
                <p class="ts-count-label">팔로잉</p>
              </button>
            </div>

            <button
              type="button"
              class="ts-follow-btn"
              :class="ps.isFollowing ? 'ts-follow-btn--on' : 'ts-follow-btn--off'"
              @click="toggleFollow"
            >
              {{ ps.isFollowing ? '✔ 팔로잉' : '+ 팔로우' }}
            </button>
          </div>
        </div>

        <div class="ts-search-wrap">
          <form class="ts-search-bar" @submit.prevent="onSearch">
            <label class="ts-search-label">다른 사람 프로필 검색</label>
            <input class="ts-input" v-model="searchQ" placeholder="닉네임 또는 이메일" />
            <button class="ts-btn ts-btn--pink" type="submit">검색</button>
          </form>
        </div>

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

    <!-- follow modal -->
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

    <PostModal v-if="ps.postModalOpen" @close="ps.closePostModal()" />
  </main>
</template>

<style scoped lang="scss">
@use '@/assets/profile.scss' as *;
</style>
