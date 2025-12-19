// src/stores/profile.js
import { defineStore } from 'pinia'
import { apiFetch, apiJson } from '@/utils/api'

export const useProfileStore = defineStore('profile', {
  state: () => ({
    isLoading: false,
    error: null,

    // _profile_payload 기준
    profile: {
      nickname: '',
      username: '',
      profile_img: '',
      follower_count: 0,
      following_count: 0,
      is_owner: false,
      is_following: false,
    },

    posts: [],

    // 모달 상태
    postModalOpen: false,
    activePost: null,
    modalComments: [],

    createPostModalOpen: false,
    imageModalOpen: false,

    followModalOpen: false,
    followModalType: 'followers',
    followList: [],
  }),

  getters: {
    nickname: (s) => s.profile?.nickname || '',
    username: (s) => s.profile?.username || '',
    profileImgUrl: (s) => s.profile?.profile_img || '',
    followerCount: (s) => s.profile?.follower_count ?? 0,
    followingCount: (s) => s.profile?.following_count ?? 0,
    isOwner: (s) => !!s.profile?.is_owner,
    isFollowing: (s) => !!s.profile?.is_following,
  },

  actions: {
    _setProfilePayload(payload) {
      // payload = { profile: {...}, posts: [...] }
      this.profile = payload.profile || this.profile
      this.posts = Array.isArray(payload.posts) ? payload.posts : []
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

      // views.profile_search: AJAX면 JSON 반환
      const res = await apiFetch(`/users/profile/search/?q=${encodeURIComponent(q)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      const data = await res.json().catch(() => null)

      if (!res.ok) throw new Error(data?.error || '검색 중 오류가 발생했습니다.')
      if (!data?.found) throw new Error(data?.error || '사용자를 찾을 수 없습니다.')
      return data.nickname
    },

    async toggleFollow(targetNickname) {
      const data = await apiJson(`/users/follow/${encodeURIComponent(targetNickname)}/ajax/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      // { success, is_following, follower_count }
      if (!data.success) throw new Error(data.error || '팔로우 처리 실패')

      this.profile.is_following = !!data.is_following
      this.profile.follower_count = data.follower_count ?? this.profile.follower_count
    },

    async toggleLike(postId) {
      // /users/post/<id>/like-toggle/ajax/ -> { is_liked, like_count }
      const data = await apiJson(`/users/post/${postId}/like-toggle/ajax/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })

      const p = this.posts.find((x) => x.id === postId)
      if (p) {
        p.is_liked = !!data.is_liked
        p.like_count = data.like_count ?? p.like_count
      }

      if (this.activePost && this.activePost.id === postId) {
        this.activePost.is_liked = !!data.is_liked
        this.activePost.like_count = data.like_count ?? this.activePost.like_count
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
      const c = (content || '').trim()
      if (!c) throw new Error('댓글 내용을 입력하세요.')

      const data = await apiJson(`/users/post/${postId}/comments/ajax/`, {
        method: 'POST',
        body: JSON.stringify({ content: c }),
      })

      if (!data.success) throw new Error(data.error || '댓글 등록 실패')
      this.modalComments.push(data.comment)
    },

    async editComment(commentId, content) {
      const c = (content || '').trim()
      if (!c) throw new Error('댓글 내용을 입력하세요.')

      const data = await apiJson(`/users/comment/${commentId}/edit/ajax/`, {
        method: 'POST',
        body: JSON.stringify({ content: c }),
      })
      if (!data.success) throw new Error(data.error || '댓글 수정 실패')

      const idx = this.modalComments.findIndex((x) => x.id === commentId)
      if (idx >= 0) this.modalComments[idx].content = data.content
    },

    async deleteComment(commentId) {
      const data = await apiJson(`/users/comment/${commentId}/delete/ajax/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      if (!data.success) throw new Error(data.error || '댓글 삭제 실패')

      this.modalComments = this.modalComments.filter((x) => x.id !== commentId)
    },

    async updatePost(postId, title, content) {
      const t = (title || '').trim()
      if (!t) throw new Error('제목을 입력하세요.')

      const data = await apiJson(`/users/post/${postId}/update/ajax/`, {
        method: 'POST',
        body: JSON.stringify({ title: t, content: content || '' }),
      })
      if (!data.success) throw new Error(data.error || '게시글 수정 실패')

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
      // Django post_delete는 POST로 처리
      const res = await apiFetch(`/users/post/${postId}/delete/`, {
        method: 'POST',
        body: new URLSearchParams({}),
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      if (!res.ok) throw new Error('게시글 삭제에 실패했습니다.')

      // 프론트에서도 제거
      this.posts = this.posts.filter((x) => x.id !== postId)
      if (this.activePost?.id === postId) this.closePostModal()
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

      // 작성 후 프로필 reload
      await this.loadMyProfile()
    },

    async uploadProfileImageBase64(base64Image) {
      const data = await apiJson('/users/upload-profile-image/', {
        method: 'POST',
        body: JSON.stringify({ image: base64Image }),
      })
      if (!data.success) throw new Error(data.error || '프로필 이미지 업로드 실패')

      // 캐시 무효화용 timestamp
      this.profile.profile_img = `${data.image_url}?t=${Date.now()}`
      return data.image_url
    },

    async openFollowModal(type) {
      this.followModalType = type
      this.followModalOpen = true
      this.followList = []

      const nickname = this.profile.nickname
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
