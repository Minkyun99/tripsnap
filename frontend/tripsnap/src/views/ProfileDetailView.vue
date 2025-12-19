<script setup>
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useProfileStore } from '@/stores/profile'
import PostModal from '@/components/profile/PostModal.vue'

const route = useRoute()
const ps = useProfileStore()
const { posts } = storeToRefs(ps)

async function load() {
  const nickname = route.params.nickname
  if (!nickname) return
  await ps.loadProfileByNickname(nickname)
}

onMounted(load)
watch(() => route.params.nickname, load)

function openPostModal(post) {
  ps.openPostModal(post)
}

async function toggleFollow() {
  await ps.toggleFollow(ps.nickname)
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

    <PostModal v-if="ps.postModalOpen" @close="ps.closePostModal()" />
  </main>
</template>

<style scoped lang="scss">
@use '@/assets/profile.scss' as *;
</style>
