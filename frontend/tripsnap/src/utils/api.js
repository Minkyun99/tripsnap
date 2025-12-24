// src/utils/api.js
import { getCsrfToken } from '@/utils/csrf'

// Use relative paths so the frontend talks to the same origin by default
// For production, set VITE_API_BASE if you need an absolute URL.
const API_BASE = import.meta.env.VITE_API_BASE || ''

function isFormData(body) {
  return typeof FormData !== 'undefined' && body instanceof FormData
}

/**
 * 크로스도메인 환경에서 CSRF 토큰을 안정적으로 읽음
 * 1. 쿠키에서 직접 읽기 시도
 * 2. 실패 시 Response Header (X-CSRFToken) 활용
 * @returns {string} CSRF 토큰 또는 빈 문자열
 */
export function getCsrfTokenSafe() {
  const token = getCsrfToken()
  
  if (token) {
    return token
  }
  
  // Fallback: meta 태그에서 읽기 (Django가 제공하는 경우)
  const metaToken = document.querySelector('meta[name="csrf-token"]')?.content
  if (metaToken) {
    return metaToken
  }
  
  console.warn('CSRF 토큰을 찾을 수 없습니다. 쿠키 설정을 확인하세요.')
  return ''
}

export async function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`

  const method = (options.method || 'GET').toUpperCase()
  const headers = new Headers(options.headers || {})

  // 모든 요청에 credentials: 'include' 적용 (세션 기반 인증)
  const finalOptions = {
    credentials: 'include',
    ...options,
  }

  // JSON 기본 Content-Type (FormData면 브라우저가 boundary 설정하도록 둠)
  if (finalOptions.body && !isFormData(finalOptions.body)) {
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  }

  // CSRF: Django는 POST, PUT, PATCH, DELETE에서 필수
  // 크로스도메인 환경에서 안정성 강화
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    if (!headers.has('X-CSRFToken')) {
      const csrfToken = getCsrfTokenSafe()
      if (csrfToken) {
        headers.set('X-CSRFToken', csrfToken)
      }
    }
  }

  finalOptions.headers = headers

  const res = await fetch(url, finalOptions)
  return res
}

export async function apiJson(path, options = {}) {
  const res = await apiFetch(path, options)
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }

  if (!res.ok) {
    const message = data?.error || data?.detail || data?.message || `요청 실패 (${res.status})`
    throw new Error(message)
  }

  return data
}
