// src/stores/profile.js
import { defineStore } from 'pinia'
import { apiFetch, apiJson } from '@/utils/api'
import { getCsrfToken } from '@/utils/csrf'

const API_BASE = import.meta.env.VITE_API_BASE || ''

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
    // 403 같은 경우 “비공개 입니다.”를 표시하기 위한 메시지
    followListPrivateMessage: '',

    // ✅ 친구 자동완성 검색 상태
    searchQuery: '',
    searchSuggestions: [],
    searchIsLoading: false,
    searchError: null,
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

    // 기존 단일 검색 API (엔터 눌렀을 때 등에서 사용 가능)
    async searchProfile(query) {
      const q = (query || '').trim()
      if (!q) throw new Error('검색어를 입력해주세요.')

      const res = await apiFetch(`/users/api/profile/search/?q=${encodeURIComponent(q)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      const data = await res.json().catch(() => null)

      if (!res.ok) {
        throw new Error(data?.detail || data?.error || '검색 중 오류가 발생했습니다.')
      }

      if (!data?.nickname) {
        throw new Error(data?.detail || '사용자를 찾을 수 없습니다.')
      }

      return data.nickname
    },

    // ✅ 자동완성용 API 호출
    async suggestProfiles(query) {
      const q = (query || '').trim()
      this.searchQuery = q
      this.searchError = null

      if (!q) {
        this.searchSuggestions = []
        return []
      }

      this.searchIsLoading = true
      try {
        const res = await apiFetch(`/users/api/profile/suggest/?q=${encodeURIComponent(q)}`, {
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
        const data = await res.json().catch(() => ({ results: [] }))

        if (!res.ok) {
          const msg = data?.detail || data?.error || '검색 중 오류가 발생했습니다.'
          this.searchError = msg
          this.searchSuggestions = []
          return []
        }

        const results = Array.isArray(data.results) ? data.results.slice(0, 5) : []
        this.searchSuggestions = results
        return results
      } catch (e) {
        this.searchError = e.message || '검색 중 오류가 발생했습니다.'
        this.searchSuggestions = []
        return []
      } finally {
        this.searchIsLoading = false
      }
    },

    async toggleFollow(targetNickname) {
      const data = await apiJson(`/users/follow/${encodeURIComponent(targetNickname)}/ajax/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      if (!data.success) throw new Error(data.error || '팔로우 처리 실패')

      this.profile.is_following = !!data.is_following
      this.profile.follower_count = data.follower_count ?? this.profile.follower_count
    },

    async toggleLike(postId) {
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

      const res = await apiFetch(`/users/post/${postId}/comments/ajax/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ content: c }),
      })

      if (!res.ok) {
        let msg = '댓글 등록 실패'
        try {
          const data = await res.json()
          msg = data?.error || msg
        } catch {}
        throw new Error(msg)
      }

      const data = await res.json()
      this.modalComments = data.comments || []
    },

    async uploadProfileImageBase64(base64Image) {
      const data = await apiJson('/users/upload-profile-image/', {
        method: 'POST',
        body: JSON.stringify({ image: base64Image }),
      })
      if (!data.success) throw new Error(data.error || '프로필 이미지 업로드 실패')

      this.profile.profile_img = `${data.image_url}?t=${Date.now()}`
      return data.image_url
    },

    // 팔로워/팔로잉 모달
    async openFollowModal(type, targetNickname = null) {
      const nick = targetNickname || this.profile?.nickname
      if (!nick) return

      this.followModalType = type
      this.followModalOpen = true
      this.followList = []
      this.followListPrivateMessage = ''

      const url =
        type === 'followers'
          ? `/users/profile/${encodeURIComponent(nick)}/followers/ajax/`
          : `/users/profile/${encodeURIComponent(nick)}/followings/ajax/`

      const res = await apiFetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })

      if (res.status === 403) {
        const data = await res.json().catch(() => null)
        this.followList = []
        this.followListPrivateMessage = data?.detail || '비공개 입니다.'
        return
      }

      if (!res.ok) {
        const data = await res.json().catch(() => null)
        this.followList = []
        this.followListPrivateMessage = data?.detail || '팔로우 목록을 불러오지 못했습니다.'
        return
      }

      const data = await res.json().catch(() => ({}))
      if (data?.private) {
        this.followList = []
        this.followListPrivateMessage = data?.detail || '비공개 입니다.'
        return
      }

      this.followList = data.users || []
    },

    closeFollowModal() {
      this.followModalOpen = false
      this.followList = []
      this.followListPrivateMessage = ''
    },
  },
})
