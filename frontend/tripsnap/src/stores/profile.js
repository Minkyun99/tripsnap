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
    // ✅ (수정) 403 같은 경우 “비공개 입니다.”를 표시하기 위한 메시지
    followListPrivateMessage: '',
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

      // ✅ (수정) urls.py 기준: /users/api/profile/search/?q=...
      const res = await apiFetch(`/users/api/profile/search/?q=${encodeURIComponent(q)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      const data = await res.json().catch(() => null)

      if (!res.ok) {
        throw new Error(data?.detail || data?.error || '검색 중 오류가 발생했습니다.')
      }

      // 서버 응답이 {"nickname": "..."} 형태라고 가정
      if (!data?.nickname) {
        throw new Error(data?.detail || '사용자를 찾을 수 없습니다.')
      }

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
      const data = await apiJson(`/users/post/${postId}/delete/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })

      // ✅ 즉시 프론트 상태 반영
      this.posts = this.posts.filter((p) => p.id !== postId)
      this.closePostModal()

      return data
    },

    async createPost({ title, content, images }) {
      const data = await apiJson('/users/post/create/', {
        method: 'POST',
        body: JSON.stringify({
          title,
          content,
          images, // ✅ Base64 문자열들의 배열
        }),
      })

      // 즉시 반영 (백엔드 응답 구조에 따라 data.post 확인)
      if (data.post) {
        this.posts.unshift(data.post)
      }
      return data
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

    // ✅ (수정) 403을 “에러 throw”로 만들지 않고, UI 메시지로 처리
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

      // 403이면 콘솔 에러 없이 “비공개” 처리
      if (res.status === 403) {
        const data = await res.json().catch(() => null)
        this.followList = []
        this.followListPrivateMessage = data?.detail || '비공개 입니다.'
        return
      }

      // 기타 에러도 메시지로만 처리(콘솔 에러/throw 최소화)
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        this.followList = []
        this.followListPrivateMessage = data?.detail || '팔로우 목록을 불러오지 못했습니다.'
        return
      }

      const data = await res.json().catch(() => ({}))
      // 백엔드가 200 + {private:true, detail:"비공개 입니다."} 형태로 바뀌어도 대응
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
