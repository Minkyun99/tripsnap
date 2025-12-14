// src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

import './assets/profile.scss'
import './assets/style.scss'

const API_BASE = import.meta.env.VITE_API_KEY

async function initCsrf() {
  try {
    await fetch(`${API_BASE}/api/csrf`, {
      method: 'GET',
      credentials: 'include',
    })
  } catch (err) {
    console.error('CSRF 초기화 실패 : ', err)
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
