// src/stores/users.js
import { defineStore } from 'pinia'
import { getCsrfToken } from '@/utils/csrf'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null, // { email, username, nickname, ... }
    isLoading: false,
    error: null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.user,
    email: (state) => state.user?.email ?? '',
    username: (state) => state.user?.username ?? '',
    nickname: (state) => state.user?.nickname ?? '',
  },

  actions: {
    // 공통 에러 파싱 헬퍼
    async _handleErrorResponse(res, defaultMessage) {
      let message = defaultMessage
      try {
        const data = await res.json()
        const firstField = Object.keys(data)[0]
        const firstMsg = (Array.isArray(data[firstField]) && data[firstField][0]) || data.detail
        if (firstMsg) message = firstMsg
      } catch {
        // ignore json parse error
      }
      throw new Error(message)
    },

    // 회원가입: 이메일 + 비밀번호만 사용
    async register({ email, password1, password2 }) {
      this.isLoading = true
      this.error = null

      try {
        const res = await fetch(`${API_BASE}/api/auth/registration/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
          credentials: 'include',
          body: JSON.stringify({ email, password1, password2 }),
        })

        if (!res.ok) {
          await this._handleErrorResponse(res, '회원가입에 실패했습니다.')
        }

        // 가입 후 자동 로그인 세션이 잡힌다고 가정
        await this.fetchMe()
      } catch (err) {
        this.user = null
        this.error = err.message ?? '회원가입 중 오류가 발생했습니다.'
        throw err
      } finally {
        this.isLoading = false
      }
    },

    // 로그인: 이메일 + 비밀번호
    async login({ email, password }) {
      this.isLoading = true
      this.error = null

      try {
        const res = await fetch(`${API_BASE}/api/auth/login/`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })

        if (!res.ok) {
          const data = await res.json().catch(() => null)
          this.error = data?.detail || '로그인에 실패했습니다.'
          return false
        }

        // 로그인 성공 → user 정보 자동 로드
        await this.fetchMe()
        return true
      } catch (err) {
        this.error = '서버와 연결할 수 없습니다.'
        return false
      } finally {
        this.isLoading = false
      }
    },

    // 현재 로그인 유저 정보 가져오기
    async fetchMe() {
      this.isLoading = true
      this.error = null

      try {
        const res = await fetch(`${API_BASE}/api/auth/user/`, {
          credentials: 'include',
        })

        // 🔵 로그인 안 된 상태 (401/403)는 에러로 보지 않고 user만 비움
        if (res.status === 401 || res.status === 403) {
          this.user = null
          return
        }

        // 그 외 에러 (500 등)는 에러로 처리
        if (!res.ok) {
          let message = '유저 정보를 가져오는 중 오류가 발생했습니다.'
          try {
            const data = await res.json()
            if (data.detail) message = data.detail
          } catch {
            // ignore
          }
          throw new Error(message)
        }

        // ✅ 정상 응답 (200)
        const data = await res.json()
        this.user = data
      } catch (err) {
        // 서버 진짜 에러만 여기로 들어옴
        this.user = null
        this.error = err.message ?? '유저 정보를 가져오는 중 오류가 발생했습니다.'
      } finally {
        this.isLoading = false
      }
    },

    // 카카오 로그인/회원가입 시작
    startKakaoLogin() {
      const next = encodeURIComponent('/auth/kakao/complete')
      window.location.href = `${API_BASE}/accounts/kakao/login/?next=${next}`
    },

    async logout() {
      this.loading = true
      this.error = null

      try {
        const csrftoken = getCsrfToken()

        // dj-rest-auth 기본 로그아웃 엔드포인트
        const res = await fetch(`${API_BASE}/api/auth/logout/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
          },
          credentials: 'include',
          body: JSON.stringify({}), // 일부 백엔드는 빈 body를 요구하기도 함
        })

        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          console.warn('logout not ok:', data)
          // 실패하더라도 프론트 상태는 일단 정리
        }
      } catch (err) {
        console.error('logout error:', err)
        // 네트워크 오류여도 일단 프론트 상태는 초기화
      } finally {
        // ✅ 프론트 상태 정리
        this.user = null
        this.loading = false
      }
    },
  },
})
