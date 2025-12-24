// src/stores/post.js
import { defineStore } from 'pinia'
import { apiFetch, apiJson } from '@/utils/api'

export const usePostStore = defineStore('post', {
  state: () => ({
    posts: [], // 목록
    currentPost: null, // 상세
    isLoading: false,
    error: null,
  }),
  getters: {
    postCount: (state) => state.posts.length,
  },
  actions: {
    async fetchPosts() {
      this.isLoading = true
      this.error = null
      try {
        const data = await apiJson('/users/posts/api/')
        this.posts = data.posts ?? data // 백엔드 응답 형식에 맞게 조정
      } catch (err) {
        this.error = err.message ?? '오류 발생'
      } finally {
        this.isLoading = false
      }
    },

    async fetchPost(postId) {
      this.isLoading = true
      this.error = null
      try {
        const data = await apiJson(`/users/post/${postId}/detail/api/`)
        this.currentPost = data
      } catch (err) {
        this.error = err.message ?? '오류 발생'
        this.currentPost = null
      } finally {
        this.isLoading = false
      }
    },

    async toggleLike(postId) {
      try {
        const data = await apiJson(`/users/post/${postId}/like-toggle/ajax/`, {
          method: 'POST',
        })
        // data: {is_liked, like_count} 형식
        if (this.currentPost && this.currentPost.id === postId) {
          this.currentPost.is_liked = data.is_liked
          this.currentPost.like_count = data.like_count
        }
        // 목록에도 반영하고 싶다면 posts 배열에서도 찾아갱신
        const idx = this.posts.findIndex((p) => p.id === postId)
        if (idx !== -1) {
          this.posts[idx].is_liked = data.is_liked
          this.posts[idx].like_count = data.like_count
        }
      } catch (err) {
        this.error = err.message ?? '좋아요 처리 중 오류'
      }
    },

    clearCurrentPost() {
      this.currentPost = null
    },
  },
})
