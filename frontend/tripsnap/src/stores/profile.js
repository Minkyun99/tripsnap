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

    searchUserResults: [],
    searchBakeryResults: [],

    myProfile: {
      nickname: '',
      username: '',
      profile_img: '',
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

    // 친구 자동완성 검색 상태
    searchQuery: '',
    searchSuggestions: [],
    searchIsLoading: false,
    searchError: null,
  }),

  getters: {
    nickname: (s) => s.profile?.nickname || '',
    username: (s) => s.profile?.username || '',
    profileImgUrl: (s) => s.profile?.profile_img || '',
    myProfileImgUrl: (s) => s.myProfile?.profile_img || '',
    followerCount: (s) => s.profile?.follower_count ?? 0,
    followingCount: (s) => s.profile?.following_count ?? 0,
    isOwner: (s) => !!s.profile?.is_owner,
    isFollowing: (s) => !!s.profile?.is_following,
  },

  actions: {
    // =====================================================
    // 내부 헬퍼
    // =====================================================
    _setProfilePayload(payload) {
      // payload = { profile: {...}, posts: [...] }
      this.profile = payload.profile || this.profile
      this.posts = Array.isArray(payload.posts) ? payload.posts : []
    },

    _setMyProfilePayload(payload) {
      if (!payload || !payload.profile) return
      this.myProfile = {
        ...(this.myProfile || {}),
        ...payload.profile,
      }
    },

    _updatePostInList(updated) {
      if (!updated) return
      const idx = this.posts.findIndex((p) => p.id === updated.id)
      if (idx !== -1) {
        this.posts[idx] = { ...this.posts[idx], ...updated }
      }
      if (this.activePost && this.activePost.id === updated.id) {
        this.activePost = { ...this.activePost, ...updated }
      }
    },

    _removePostFromList(postId) {
      this.posts = this.posts.filter((p) => p.id !== postId)
      if (this.activePost && this.activePost.id === postId) {
        this.closePostModal()
      }
    },

    // =====================================================
    // 프로필 로딩
    // =====================================================
    async loadMyProfile() {
      this.isLoading = true
      this.error = null
      try {
        const data = await apiJson('/users/api/profile/me/')
        // 화면에 “내 프로필 상세 페이지”를 띄울 때 쓰는 profile
        this._setProfilePayload(data)
        // ✅ 헤더/배너에서 항상 고정으로 사용할 myProfile
        this._setMyProfilePayload(data)
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
        // ✅ 여기서는 현재 화면용 profile / posts만 교체
        this._setProfilePayload(data)
        // this._setMyProfilePayload(...) 는 호출하지 않음
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.isLoading = false
      }
    },

    // =====================================================
    // 프로필 검색/자동완성
    // =====================================================
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

    // 자동완성용 API 호출
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

    // =====================================================
    // 팔로우
    // =====================================================
    async toggleFollow(targetNickname) {
      const data = await apiJson(`/users/follow/${encodeURIComponent(targetNickname)}/ajax/`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      if (!data.success) throw new Error(data.error || '팔로우 처리 실패')

      this.profile.is_following = !!data.is_following
      this.profile.follower_count = data.follower_count ?? this.profile.follower_count
    },

    // =====================================================
    // 게시글 좋아요
    // =====================================================
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

    // =====================================================
    // 게시글 모달 / 이미지 모달 / 작성 모달
    // =====================================================
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

    openImageModal() {
      this.imageModalOpen = true
    },

    closeImageModal() {
      this.imageModalOpen = false
    },

    openCreatePostModal() {
      this.createPostModalOpen = true
      // 새 글 작성 시에는 activePost를 비워두는 것이 자연스럽습니다.
      this.activePost = null
    },

    closeCreatePostModal() {
      this.createPostModalOpen = false
    },

    // =====================================================
    // 게시글 생성 / 수정 / 삭제
    // =====================================================
    /**
     * 게시글 생성
     * payload: { title, content, images }  // images: base64 문자열 배열
     */
    async createPost(payload) {
      const { title, content, images = [] } = payload || {}
      const t = (title || '').trim()
      const c = (content || '').trim()

      if (!t || !c) {
        throw new Error('제목과 내용을 모두 입력해주세요.')
      }

      const data = await apiJson('/users/post/create/', {
        method: 'POST',
        body: JSON.stringify({
          title: t,
          content: c,
          images,
        }),
      })

      if (!data || !data.post) {
        throw new Error(data?.error || '게시글 작성에 실패했습니다.')
      }

      const newPost = {
        ...data.post,
        is_owner: true, // 방금 작성한 글은 내 글
      }

      // 최신 글을 맨 앞에 추가
      this.posts = [newPost, ...this.posts]

      // 작성 모달 닫기
      this.closeCreatePostModal()

      return newPost
    },

    /**
     * 게시글 수정
     * - PostModal.vue: updatePost(postId, title, content)
     */
    // src/stores/profile.js

    async updatePost(postId, titleOrPayload, contentMaybe) {
      // ① 기존 게시글 찾기
      const existing = this.posts.find((p) => p.id === postId) || this.activePost

      // ② 인자 형태 구분
      // - updatePost(id, { title, content, images })
      // - updatePost(id, title, content)  둘 다 지원
      let title
      let content
      let images

      if (titleOrPayload && typeof titleOrPayload === 'object' && !Array.isArray(titleOrPayload)) {
        // 새 형태: payload 객체
        title = titleOrPayload.title
        content = titleOrPayload.content
        images = titleOrPayload.images
      } else {
        // 옛 형태: (id, title, content)
        title = titleOrPayload
        content = contentMaybe
      }

      const finalTitle = (
        title !== undefined && title !== null ? String(title) : existing?.title || ''
      ).trim()

      const finalContent = (
        content !== undefined && content !== null ? String(content) : existing?.content || ''
      ).trim()

      if (!finalTitle) {
        throw new Error('제목을 입력하세요.')
      }

      // ③ 요청 body 구성
      const body = {
        title: finalTitle,
        content: finalContent,
      }

      // images 배열이 넘어온 경우에만 포함
      if (Array.isArray(images)) {
        body.images = images
      }

      const res = await apiFetch(`/users/post/${postId}/update/ajax/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(body),
      })

      const data = await res.json().catch(() => null)

      if (!res.ok || !data?.success) {
        throw new Error(data?.error || '게시글 수정에 실패했습니다.')
      }

      // ④ 백엔드가 serializer로 내려준 전체 post 를 그대로 반영
      //    (image / images / like_count / is_liked / created_at 등 모두)
      const updated = data.post || {
        id: postId,
        title: finalTitle,
        content: finalContent,
      }

      this._updatePostInList(updated)
      return updated
    },

    /**
     * 게시글 삭제
     */
    async deletePost(postId) {
      const res = await apiFetch(`/users/post/${postId}/delete/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({}),
      })

      let data = null
      try {
        data = await res.json()
      } catch {
        // JSON 파싱 실패 시에도 일단 목록에서 제거
      }

      if (!res.ok || data?.success === false) {
        throw new Error(data?.error || '게시글 삭제에 실패했습니다.')
      }

      this._removePostFromList(postId)
    },

    // =====================================================
    // 댓글 목록 / 작성 / 수정 / 삭제
    // =====================================================
    async loadComments(postId) {
      const data = await apiJson(`/users/post/${postId}/comments/ajax/`)
      this.modalComments = data.comments || []
    },

    /**
     * 댓글 작성
     * 사용: ps.submitComment(postId, content)
     */
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
        } catch {
          // ignore
        }
        throw new Error(msg)
      }

      const data = await res.json()

      // 백엔드는 { success, comment: {...} } 한 건만 내려줌
      if (data.comment) {
        this.modalComments = [...this.modalComments, data.comment]
      } else if (data.comments) {
        this.modalComments = data.comments
      }
    },

    /**
     * 댓글 수정(내부 구현)
     * 사용: ps.updateComment(commentId, newContent)
     */
    async updateComment(commentId, newContent) {
      const c = (newContent || '').trim()
      if (!c) throw new Error('댓글 내용을 입력하세요.')

      const res = await apiFetch(`/users/comment/${commentId}/edit/ajax/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ content: c }),
      })

      const data = await res.json().catch(() => null)

      if (!res.ok || !data?.success) {
        throw new Error(data?.error || '댓글 수정에 실패했습니다.')
      }

      this.modalComments = this.modalComments.map((cm) =>
        cm.id === commentId
          ? {
              ...cm,
              content: data.content ?? c,
              updated_at: data.updated_at || cm.updated_at,
            }
          : cm,
      )
    },

    /**
     * (PostModal.vue 호환용) 댓글 수정 alias
     * 사용: ps.editComment(commentId, newContent)
     */
    async editComment(commentId, newContent) {
      return this.updateComment(commentId, newContent)
    },

    /**
     * 댓글 삭제
     * 사용: ps.deleteComment(commentId)
     */
    async deleteComment(commentId) {
      const res = await apiFetch(`/users/comment/${commentId}/delete/ajax/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({}),
      })

      const data = await res.json().catch(() => null)

      if (!res.ok || !data?.success) {
        throw new Error(data?.error || '댓글 삭제에 실패했습니다.')
      }

      this.modalComments = this.modalComments.filter((cm) => cm.id !== commentId)
    },

    // =====================================================
    // 프로필 이미지 업로드
    // =====================================================
    async uploadProfileImageBase64(base64Image) {
      const data = await apiJson('/users/upload-profile-image/', {
        method: 'POST',
        body: JSON.stringify({ image: base64Image }),
      })
      if (!data.success) throw new Error(data.error || '프로필 이미지 업로드 실패')

      const urlWithTs = `${data.image_url}?t=${Date.now()}`

      // 🔴 기존: this.profile.profile_img 만 변경
      // this.profile.profile_img = `${data.image_url}?t=${Date.now()}`

      // ✅ 수정: profile + myProfile 둘 다 갱신
      this.profile = {
        ...this.profile,
        profile_img: urlWithTs,
      }
      this.myProfile = {
        ...this.myProfile,
        profile_img: urlWithTs,
      }

      return data.image_url
    },

    // ✅ 프로필 이미지 기본값으로 초기화
    async resetProfileImage() {
      const data = await apiJson('/users/reset-profile-image/', {
        method: 'POST',
        body: JSON.stringify({}),
      })

      if (!data.success) {
        throw new Error(data.error || '프로필 이미지를 기본값으로 되돌리는 데 실패했습니다.')
      }

      // 🔴 기존: this.profile.profile_img = ''
      // ✅ 수정: 두 곳 다 비워서 아바타/모달 모두 기본 이미지로
      this.profile = {
        ...this.profile,
        profile_img: '',
      }
      this.myProfile = {
        ...this.myProfile,
        profile_img: '',
      }

      return true
    },
    // =====================================================
    // 팔로워/팔로잉 모달
    // =====================================================
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

    resetProfile() {
      this.profile = {
        nickname: '',
        username: '',
        profile_img: '',
        follower_count: 0,
        following_count: 0,
        is_owner: false,
        is_following: false,
      }
      this.posts = []
      this.postModalOpen = false
      this.activePost = null
      this.modalComments = []
      // 팔로우 모달은 상황에 따라 유지해도 되지만, 깔끔하게 비우고 싶으면 아래도 포함
      // this.followModalOpen = false
      // this.followList = []
      // this.followListPrivateMessage = ''
    },

    async searchUsersAndBakeries(query) {
      const q = (query || '').trim()
      if (!q) {
        this.searchUserResults = []
        this.searchBakeryResults = []
        return { users: [], bakeries: [] }
      }

      const res = await apiFetch(`/users/api/search/profile-bakery/?q=${encodeURIComponent(q)}`)
      const data = await res.json().catch(() => ({ users: [], bakeries: [] }))

      if (!res.ok) {
        // 필요시 에러 처리
        this.searchUserResults = []
        this.searchBakeryResults = []
        throw new Error(data.detail || '검색 중 오류가 발생했습니다.')
      }

      this.searchUserResults = data.users || []
      this.searchBakeryResults = data.bakeries || []
      return data
    },
  },
})
