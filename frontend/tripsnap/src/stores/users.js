// src/stores/users.js
import { defineStore } from 'pinia'
import { getCsrfToken } from '@/utils/csrf.js'

const API_BASE = import.meta.env.VITE_API_BASE || ''

async function parseErrorMessage(res, fallbackMessage) {
  let message = fallbackMessage
  try {
    const data = await res.json()

    if (data?.detail) return data.detail

    const firstField = data && typeof data === 'object' ? Object.keys(data)[0] : null
    if (firstField) {
      const v = data[firstField]
      if (Array.isArray(v) && v.length > 0) return String(v[0])
      if (typeof v === 'string') return v
    }
  } catch {
    // ignore
  }
  return message
}

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
        const res = await fetch(`${API_BASE}/users/api/recommended-bakeries/`, {
          credentials: 'include',
        })

        if (res.status === 401 || res.status === 403) {
          // 비로그인 또는 권한 없음 → 추천 목록 비움
          this.recommendedBakeries = []
          return []
        }

        if (!res.ok) {
          const msg = await parseErrorMessage(res, '추천 빵집을 불러오지 못했습니다.')
          this.error = msg
          this.recommendedBakeries = []
          return []
        }

        const data = await res.json()
        const rawList = data.results || []

        const picked = this._pickRandomBakeries(rawList, maxCount)
        this.recommendedBakeries = picked
        return picked
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
        const res = await fetch(`${API_BASE}/api/auth/registration/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          credentials: 'include',
          body: JSON.stringify({ email, password1, password2 }),
        })

        if (!res.ok) {
          const msg = await parseErrorMessage(res, '회원가입에 실패했습니다.')
          throw new Error(msg)
        }

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
        const res = await fetch(`${API_BASE}/api/auth/login/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          credentials: 'include',
          body: JSON.stringify({ email, password }),
        })

        if (!res.ok) {
          const msg = await parseErrorMessage(res, '로그인에 실패했습니다.')
          this.user = null
          this.error = msg
          return false
        }

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
        const res = await fetch(`${API_BASE}/api/auth/user/`, {
          credentials: 'include',
        })

        if (res.status === 401 || res.status === 403) {
          this.user = null
          return null
        }

        if (!res.ok) {
          const msg = await parseErrorMessage(res, '유저 정보를 가져오는 중 오류가 발생했습니다.')
          throw new Error(msg)
        }

        const data = await res.json()
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
        const res = await fetch(`${API_BASE}/api/auth/password/change/`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ old_password, new_password1, new_password2 }),
        })

        if (!res.ok) {
          const msg = await parseErrorMessage(res, '비밀번호 변경에 실패했습니다.')
          throw new Error(msg)
        }

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
        const res = await fetch(`${API_BASE}/users/api/account/delete/`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({}),
        })

        if (!res.ok) {
          const msg = await parseErrorMessage(res, '회원 탈퇴에 실패했습니다.')
          throw new Error(msg)
        }

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
      const next = encodeURIComponent('/auth/kakao/complete')
      window.location.href = `${API_BASE}/accounts/kakao/login/?next=${next}`
    },

    async logout() {
      this.isLoading = true
      this.error = null

      try {
        const res = await fetch(`${API_BASE}/api/auth/logout/`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({}),
        })

        if (!res.ok) {
          const msg = await parseErrorMessage(res, '로그아웃에 실패했습니다.')
          console.warn('logout not ok:', msg)
        }
      } catch (err) {
        console.error('logout error:', err)
      } finally {
        this.user = null
        this.isLoading = false
      }
    },

    // ✅ 팔로우 목록 공개 범위 조회
    async fetchFollowVisibility() {
      const res = await fetch(`${API_BASE}/users/api/settings/follow-visibility/`, {
        credentials: 'include',
      })
      if (!res.ok) {
        const msg = await parseErrorMessage(res, '설정 정보를 불러오지 못했습니다.')
        throw new Error(msg)
      }
      return await res.json()
    },

    // ✅ 팔로우 목록 공개 범위 저장
    async updateFollowVisibility(value) {
      // ✅ 백엔드 허용 값에 맞춰 강제 정규화 (public|following_only|private)
      const normalized = value === 'followers' ? 'following_only' : value // 과거 값이 남아있을 경우 방어

      const allowed = new Set(['public', 'following_only', 'private'])
      if (!allowed.has(normalized)) {
        throw new Error('follow_visibility 값이 올바르지 않습니다.')
      }

      const res = await fetch(`${API_BASE}/users/api/settings/follow-visibility/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ follow_visibility: normalized }),
      })

      if (!res.ok) {
        const msg = await parseErrorMessage(res, '공개 범위 변경에 실패했습니다.')
        throw new Error(msg)
      }
      return await res.json()
    },
  },
})

// ✅ 일부 코드가 default import로 가져오는 경우도 있으니 안전장치
export default useUserStore
