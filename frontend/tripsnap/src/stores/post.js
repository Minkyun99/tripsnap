// src/stores/post.js
import { defineStore } from 'pinia'

const API_BASE = 'http://localhost:8000'

export const usePostStore = defineStore('post', {
  state: () => ({
    posts: [],            // 목록
    currentPost: null,    // 상세
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
        // TODO: Django에 /users/posts/api/ 같은 JSON 뷰를 하나 만들면 좋습니다.
        const res = await fetch(`${API_BASE}/users/posts/api/`, {
          credentials: 'include',
        })
        if (!res.ok) throw new Error('게시글 목록 조회 실패')
        const data = await res.json()
        this.posts = data.posts ?? data  // 백엔드 응답 형식에 맞게 조정
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
        // 예: /users/post/<id>/detail/api/
        const res = await fetch(`${API_BASE}/users/post/${postId}/detail/api/`, {
          credentials: 'include',
        })
        if (!res.ok) throw new Error('게시글 상세 조회 실패')
        const data = await res.json()
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
        // 기존에 있던 AJAX URL을 그대로 활용 가능:
        // /users/post/<post_id>/like-toggle/ajax/
        const res = await fetch(`${API_BASE}/users/post/${postId}/like-toggle/ajax/`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
        if (!res.ok) throw new Error('좋아요 토글 실패')
        const data = await res.json()
        // data: {is_liked, like_count} 형식 (현재 users/views.py 기반)
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
