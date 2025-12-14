// src/utils/api.js
import { getCsrfToken } from './csrf'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const method = (options.method || 'GET').toUpperCase()

  const headers = new Headers(options.headers || {})
  const isUnsafe = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  // JSON 바디일 때 기본 Content-Type
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  // 세션 기반이면 CSRF 필요
  if (isUnsafe && !headers.has('X-CSRFToken')) {
    const csrf = getCsrfToken()
    if (csrf) headers.set('X-CSRFToken', csrf)
  }

  const res = await fetch(url, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })

  return res
}

export async function apiJson(path, options = {}) {
  const res = await apiFetch(path, options)
  const ct = res.headers.get('content-type') || ''
  const data = ct.includes('application/json') ? await res.json() : null
  if (!res.ok) {
    const msg = data?.detail || data?.error || '요청 처리 중 오류가 발생했습니다.'
    throw new Error(msg)
  }
  return data
}
