// src/stores/users.js
import { defineStore } from 'pinia'
import { getCsrfToken } from '@/utils/csrf'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null,
    isLoading: false,
    error: null,
    fieldErrors: {}, // ✅ 필드별 에러를 담아두면 화면에서 표시 가능
  }),

  getters: {
    isAuthenticated: (state) => !!state.user,
    email: (state) => state.user?.email ?? '',
    username: (state) => state.user?.username ?? '',
    nickname: (state) => state.user?.nickname ?? '',
  },

  actions: {
    _resetErrors() {
      this.error = null
      this.fieldErrors = {}
    },

    async _parseError(res, defaultMessage) {
      // dj-rest-auth/DRF는 보통 {field:[msg]} 또는 {detail:""} 형태
      let data = null
      try {
        data = await res.json()
      } catch {
        // ignore
      }

      if (data && typeof data === 'object') {
        // detail 우선
        if (data.detail) {
          this.error = data.detail
          throw new Error(this.error)
        }

        // field errors
        const fieldErrors = {}
        for (const [k, v] of Object.entries(data)) {
          if (Array.isArray(v) && v.length) fieldErrors[k] = v[0]
          else if (typeof v === 'string') fieldErrors[k] = v
        }
        this.fieldErrors = fieldErrors

        // 대표 메시지 구성
        const firstKey = Object.keys(fieldErrors)[0]
        const firstMsg = firstKey ? fieldErrors[firstKey] : defaultMessage
        this.error = firstMsg || defaultMessage
        throw new Error(this.error)
      }

      this.error = defaultMessage
      throw new Error(defaultMessage)
    },

    // ✅ 회원가입: email + password1 + password2 만 전송 (A안)
    async register({ email, password1, password2 }) {
      this.isLoading = true
      this._resetErrors()

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
          await this._parseError(res, '회원가입에 실패했습니다.')
        }

        // 가입 성공 -> 서버가 세션/JWT 쿠키 세팅했다고 가정 -> user 로드
        await this.fetchMe()
        if (!this.user) {
          // 성공했는데도 user가 null이면 로그인 상태가 아닌 것
          throw new Error('회원가입은 완료되었지만 로그인 상태를 확인할 수 없습니다.')
        }

        return true
      } finally {
        this.isLoading = false
      }
    },

    // 로그인: email + password
    async login({ email, password }) {
      this.isLoading = true
      this._resetErrors()

      try {
        const res = await fetch(`${API_BASE}/api/auth/login/`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ email, password }),
        })

        if (!res.ok) {
          await this._parseError(res, '로그인에 실패했습니다.')
        }

        await this.fetchMe()
        return !!this.user
      } finally {
        this.isLoading = false
      }
    },

    async fetchMe() {
      // 로그인 여부 확인은 초기 부팅 시 자주 호출되므로 에러로 다루지 않음
      try {
        const res = await fetch(`${API_BASE}/api/auth/user/`, {
          credentials: 'include',
        })

        if (res.status === 401 || res.status === 403) {
          this.user = null
          return
        }

        if (!res.ok) {
          this.user = null
          return
        }

        this.user = await res.json()
      } catch {
        this.user = null
      }
    },

    startKakaoLogin() {
      const next = encodeURIComponent('/auth/kakao/complete')
      window.location.href = `${API_BASE}/accounts/kakao/login/?next=${next}`
    },

    async logout() {
      this.isLoading = true
      this._resetErrors()

      try {
        await fetch(`${API_BASE}/api/auth/logout/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          credentials: 'include',
          body: JSON.stringify({}),
        })
      } finally {
        this.user = null
        this.isLoading = false
      }
    },
  },
})
