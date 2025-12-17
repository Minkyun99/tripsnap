// src/utils/api.js
import { getCsrfToken } from '@/utils/csrf'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function isFormData(body) {
  return typeof FormData !== 'undefined' && body instanceof FormData
}

export async function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`

  const method = (options.method || 'GET').toUpperCase()
  const headers = new Headers(options.headers || {})

  // Django 세션 기반이면 credentials 필수
  const finalOptions = {
    credentials: 'include',
    ...options,
  }

  // JSON 기본 Content-Type (FormData면 브라우저가 boundary 넣도록 둠)
  if (finalOptions.body && !isFormData(finalOptions.body)) {
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  }

  // CSRF: Django는 "unsafe method"에서 필요
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    if (!headers.has('X-CSRFToken')) headers.set('X-CSRFToken', getCsrfToken())
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
