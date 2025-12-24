// src/utils/csrf.js

/**
 * 쿠키에서 특정 이름의 값을 읽음
 * 크로스도메인 환경(SameSite=None)에서도 안정적으로 작동
 * @param {string} name 쿠키 이름
 * @returns {string|null} 쿠키 값 또는 null
 */
export function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) return parts.pop().split(';').shift()
  return null
}

/**
 * CSRF 토큰을 쿠키에서 읽음
 * @returns {string} CSRF 토큰 또는 빈 문자열
 */
export function getCsrfToken() {
  return getCookie('csrftoken') || ''
}

