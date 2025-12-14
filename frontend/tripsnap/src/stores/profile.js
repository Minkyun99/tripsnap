// src/stores/profile.js
import { defineStore } from 'pinia'
import { apiFetch, apiJson } from '../utils/api'

export const useProfileStore = defineStore('profile', {
  state: () => ({
    isLoading: false,
    error: null,

    // 공통 프로필 데이터
    targetUser: null, // { nickname, username, ... }
    profile: null, // { profile_img: url or null }
    posts: [],

    // counts
    followerCount: 0,
    followingCount: 0,
    isFollowing: false,

    // 모달 상태
    followModalOpen: false,
    followModalType: 'followers',
    followList: [],

    postModalOpen: false,
    activePost: null,
    modalComments: [],

    createPostModalOpen: false,

    imageModalOpen: false,

    // 검색
    lastSearchResultNickname: null,
  }),

  getters: {
    profileImgUrl: (s) => s.profile?.profile_img || '',
  },

  actions: {
    _setProfilePayload(payload) {
      // ✅ 백엔드 /users/api/profile/* 응답 구조에 맞춤
      this.profile = payload.profile || null
      this.posts = payload.posts || []
      // (targetUser는 더 이상 필요 없지만, 다른 코드가 참조한다면 유지용으로 세팅)
      this.targetUser = payload.profile
        ? { nickname: payload.profile.nickname, username: payload.profile.username }
        : null
      this.followerCount = payload.profile?.follower_count ?? 0
      this.followingCount = payload.profile?.following_count ?? 0
      this.isFollowing = payload.profile?.is_following ?? false
    },

    async loadMyProfile() {
      this.isLoading = true
      this.error = null
      try {
        const data = await apiJson('/users/api/profile/me/')
        this._setProfilePayload(data)
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.isLoading = false
      }
    },

    async loadProfileByNickname(nickname) {
      this.isLoading = true
      this.error = null
      try {
        const data = await apiJson(`/users/api/profile/${encodeURIComponent(nickname)}/`)
        this._setProfilePayload(data)
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.isLoading = false
      }
    },

    async searchProfile(query) {
      const q = (query || '').trim()
      if (!q) throw new Error('검색어를 입력해주세요.')

      // AJAX 응답(JSON) 받기 위해 헤더 추가 (views.py에서 분기)
      const res = await apiFetch(`/users/profile/search/?q=${encodeURIComponent(q)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) throw new Error(data?.error || '검색 중 오류가 발생했습니다.')
      if (!data?.found) throw new Error(data?.error || '사용자를 찾을 수 없습니다.')

      this.lastSearchResultNickname = data.nickname
      return data.nickname
    },

    async toggleFollow(targetNickname) {
      const res = await apiJson(`/users/follow/${encodeURIComponent(targetNickname)}/ajax/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })

      if (!res.success) throw new Error(res.error || '팔로우 처리 실패')
      this.isFollowing = !!res.is_following
      this.followerCount = res.follower_count ?? this.followerCount
    },

    async toggleLike(post) {
      const res = await apiJson(`/users/post/${post.id}/like-toggle/ajax/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })

      post.is_liked = !!res.is_liked
      post.like_count = res.like_count ?? post.like_count

      // 모달에 같은 게시글 열려있으면 동기화
      if (this.activePost && this.activePost.id === post.id) {
        this.activePost.is_liked = post.is_liked
        this.activePost.like_count = post.like_count
      }
    },

    async openPostModal(post) {
      this.activePost = { ...post }
      this.postModalOpen = true
      await this.loadComments(post.id)
    },

    closePostModal() {
      this.postModalOpen = false
      this.activePost = null
      this.modalComments = []
    },

    async loadComments(postId) {
      const data = await apiJson(`/users/post/${postId}/comments/ajax/`)
      this.modalComments = data.comments || []
    },

    async submitComment(postId, content) {
      const body = { content }
      const data = await apiJson(`/users/post/${postId}/comments/ajax/`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (!data.success) throw new Error(data.error || '댓글 등록 실패')

      // 새 댓글을 즉시 append
      this.modalComments.push(data.comment)
    },

    async editComment(commentId, content) {
      const data = await apiJson(`/users/comment/${commentId}/edit/ajax/`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      })
      if (!data.success) throw new Error(data.error || '댓글 수정 실패')

      const idx = this.modalComments.findIndex((c) => c.id === commentId)
      if (idx >= 0) this.modalComments[idx].content = content
    },

    async deleteComment(commentId) {
      const data = await apiJson(`/users/comment/${commentId}/delete/ajax/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      if (!data.success) throw new Error(data.error || '댓글 삭제 실패')

      this.modalComments = this.modalComments.filter((c) => c.id !== commentId)
    },

    async updatePost(postId, title, content) {
      const data = await apiJson(`/users/post/${postId}/update/ajax/`, {
        method: 'POST',
        body: JSON.stringify({ title, content }),
      })
      if (!data.success) throw new Error(data.error || '게시글 수정 실패')

      // 리스트 동기화
      const p = this.posts.find((x) => x.id === postId)
      if (p) {
        p.title = data.post.title
        p.content = data.post.content
      }
      if (this.activePost?.id === postId) {
        this.activePost.title = data.post.title
        this.activePost.content = data.post.content
      }
    },

    async deletePost(postId) {
      // redirect 응답(HTML)이라도 ok이면 성공 취급 후 refresh
      const res = await apiFetch(`/users/post/${postId}/delete/`, {
        method: 'POST',
        body: new URLSearchParams({}), // CSRF는 apiFetch가 헤더로 넣음
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      if (!res.ok) throw new Error('게시글 삭제에 실패했습니다.')
    },

    async createPost({ title, content, file }) {
      const fd = new FormData()
      fd.append('title', title || '')
      fd.append('content', content || '')
      if (file) fd.append('share_trip', file)

      const res = await apiFetch('/users/post/create/', {
        method: 'POST',
        body: fd,
      })
      if (!res.ok) throw new Error('게시글 작성에 실패했습니다.')
    },

    async uploadProfileImageBase64(base64Image) {
      const data = await apiJson('/users/upload-profile-image/', {
        method: 'POST',
        body: JSON.stringify({ image: base64Image }),
      })

      if (!data.success) throw new Error(data.error || '프로필 이미지 업로드 실패')
      // 캐시 무효화용 timestamp
      this.profile = this.profile || {}
      this.profile.profile_img = `${data.image_url}?t=${Date.now()}`
      return data.image_url
    },

    async openFollowModal(type, nickname) {
      this.followModalType = type
      this.followModalOpen = true
      this.followList = []

      const url =
        type === 'followers'
          ? `/users/profile/${encodeURIComponent(nickname)}/followers/ajax/`
          : `/users/profile/${encodeURIComponent(nickname)}/followings/ajax/`

      const data = await apiJson(url)
      this.followList = data.users || []
    },

    closeFollowModal() {
      this.followModalOpen = false
      this.followList = []
    },

    openImageModal() {
      this.imageModalOpen = true
    },
    closeImageModal() {
      this.imageModalOpen = false
    },

    openCreatePostModal() {
      this.createPostModalOpen = true
    },
    closeCreatePostModal() {
      this.createPostModalOpen = false
    },
  },
})
