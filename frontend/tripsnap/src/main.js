// src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { apiFetch } from '@/utils/api'

import './assets/profile.scss'
import './assets/style.scss'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

/**
 * 앱 초기화 시 CSRF 토큰을 서버에서 받음
 * 크로스도메인 환경에서 쿠키를 설정하기 위해 credentials: 'include' 사용
 */
async function initCsrf() {
  try {
    // apiFetch를 사용하여 credentials 자동 설정
    const response = await apiFetch('/users/api/csrf/', {
      method: 'GET',
    })
    
    if (!response.ok) {
      console.warn(`CSRF 초기화 응답 상태: ${response.status}`)
    }
  } catch (err) {
    console.error('CSRF 초기화 실패:', err)
    // CSRF 초기화 실패해도 앱 시작은 계속함
  }
}

async function bootstrap() {
  await initCsrf()

  const app = createApp(App)

  const pinia = createPinia()
  app.use(pinia)
  app.use(router)
  app.mount('#app')
}

bootstrap()
