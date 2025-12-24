// src/stores/users.js
import { defineStore } from 'pinia'
import { apiJson } from '@/utils/api.js'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null, // { email, username, nickname, ... }
    isLoading: false,
    error: null,

    // ✅ 홈에서 사용할 추천 빵집 상태
    recommendedBakeries: [],
    isLoadingRecommendedBakeries: false,
  }),

  getters: {
    isAuthenticated: (state) => !!state.user,
    email: (state) => state.user?.email ?? '',
    username: (state) => state.user?.username ?? '',
    nickname: (state) => state.user?.nickname ?? '',
  },

  actions: {
    // 내부 유틸: 리스트를 셔플해서 최대 maxCount개만 반환
    _pickRandomBakeries(list, maxCount = 5) {
      if (!Array.isArray(list)) return []

      const shuffled = [...list].sort(() => Math.random() - 0.5)
      if (shuffled.length <= maxCount) return shuffled
      return shuffled.slice(0, maxCount)
    },

    // ✅ 홈 화면용 추천 빵집 로드 (새로고침마다 랜덤 조합)
    async fetchRecommendedBakeries({ maxCount = 5 } = {}) {
      this.isLoadingRecommendedBakeries = true

      try {
        try {
          const data = await apiJson('/users/api/recommended-bakeries/')
          const rawList = data.results || []

          const picked = this._pickRandomBakeries(rawList, maxCount)
          this.recommendedBakeries = picked
          return picked
        } catch (err) {
          // 비로그인 또는 권한 없음 → 추천 목록 비움
          if (err.message?.includes('401') || err.message?.includes('403')) {
            this.recommendedBakeries = []
            return []
          }
          throw err
        }
      } catch (err) {
        console.error('fetchRecommendedBakeries error:', err)
        this.error = err?.message ?? '추천 빵집을 불러오는 중 오류가 발생했습니다.'
        this.recommendedBakeries = []
        return []
      } finally {
        this.isLoadingRecommendedBakeries = false
      }
    },

    async register({ email, password1, password2 }) {
      this.isLoading = true
      this.error = null

      try {
        await apiJson('/api/auth/registration/', {
          method: 'POST',
          body: JSON.stringify({ email, password1, password2 }),
        })

        await this.fetchMe()
        return true
      } catch (err) {
        this.user = null
        this.error = err?.message ?? '회원가입 중 오류가 발생했습니다.'
        throw err
      } finally {
        this.isLoading = false
      }
    },

    async login({ email, password }) {
      this.isLoading = true
      this.error = null

      try {
        await apiJson('/api/auth/login/', {
          method: 'POST',
          body: JSON.stringify({ email, password }),
        })

        await this.fetchMe()
        return true
      } catch (err) {
        this.user = null
        this.error = err?.message ?? '서버와 연결할 수 없습니다.'
        return false
      } finally {
        this.isLoading = false
      }
    },

    async fetchMe() {
      this.isLoading = true
      this.error = null

      try {
        const data = await apiJson('/api/auth/user/')
        this.user = data
        return data
      } catch (err) {
        this.user = null
        this.error = err?.message ?? '유저 정보를 가져오는 중 오류가 발생했습니다.'
        return null
      } finally {
        this.isLoading = false
      }
    },

    async changePassword({ old_password, new_password1, new_password2 }) {
      this.isLoading = true
      this.error = null

      try {
        await apiJson('/api/auth/password/change/', {
          method: 'POST',
          body: JSON.stringify({ old_password, new_password1, new_password2 }),
        })

        return true
      } catch (err) {
        this.error = err?.message ?? '비밀번호 변경 중 오류가 발생했습니다.'
        throw err
      } finally {
        this.isLoading = false
      }
    },

    async deleteAccount() {
      this.isLoading = true
      this.error = null

      try {
        await apiJson('/users/api/account/delete/', {
          method: 'POST',
          body: JSON.stringify({}),
        })

        this.user = null
        return true
      } catch (err) {
        this.error = err?.message ?? '회원 탈퇴 중 오류가 발생했습니다.'
        throw err
      } finally {
        this.isLoading = false
      }
    },

    startKakaoLogin() {
      // ✅ process=login 파라미터 추가로 Django 중간 템플릿 건너뛰기
      // 바로 카카오 OAuth 페이지로 리다이렉트됩니다
      window.location.href = '/accounts/kakao/login/?process=login'
    },

    async logout() {
      this.isLoading = true
      this.error = null

      try {
        await apiJson('/api/auth/logout/', {
          method: 'POST',
          body: JSON.stringify({}),
        })
      } catch (err) {
        console.error('logout error:', err)
      } finally {
        this.user = null
        this.isLoading = false
      }
    },

    // ✅ 팔로우 목록 공개 범위 조회
    async fetchFollowVisibility() {
      try {
        return await apiJson('/users/api/settings/follow-visibility/')
      } catch (err) {
        throw new Error(err?.message ?? '설정 정보를 불러오지 못했습니다.')
      }
    },

    // ✅ 팔로우 목록 공개 범위 저장
    async updateFollowVisibility(value) {
      // ✅ 백엔드 허용 값에 맞춰 강제 정규화 (public|following_only|private)
      const normalized = value === 'followers' ? 'following_only' : value // 과거 값이 남아있을 경우 방어

      const allowed = new Set(['public', 'following_only', 'private'])
      if (!allowed.has(normalized)) {
        throw new Error('follow_visibility 값이 올바르지 않습니다.')
      }

      return await apiJson('/users/api/settings/follow-visibility/', {
        method: 'POST',
        body: JSON.stringify({ follow_visibility: normalized }),
      })
    },
  },
})

// ✅ 일부 코드가 default import로 가져오는 경우도 있으니 안전장치
export default useUserStore