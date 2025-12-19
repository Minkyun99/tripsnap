// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import SignupView from '../views/SignupView.vue'
import KakaoCallbackView from '../views/KakaoCallbackView.vue'
import ProfileView from '../views/ProfileView.vue'
import ProfileDetailView from '../views/ProfileDetailView.vue'
import KeywordSelectionView from '../views/KeywordSelectionView.vue'
import ChatbotView from '../views/ChatbotView.vue'
import ProfileSearchView from '../views/ProfileSearchView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/signup', name: 'signup', component: SignupView },
    {
      path: '/auth/kakao/complete',
      name: 'kakao-complete',
      component: KakaoCallbackView,
    },
    { path: '/chatbot/keywords', name: 'chat_keywords', component: KeywordSelectionView },
    { path: '/chatbot', name: 'chatbot', component: ChatbotView },

    // ✅ 본인 프로필
    { path: '/profile', name: 'profile', component: ProfileView },

    // ✅ 다른 사람 프로필
    {
      path: '/profile/:nickname',
      name: 'profile-detail',
      component: ProfileDetailView,
      props: true,
    },

    // ✅ 프로필 검색 페이지 (배너 검색 버튼이 여기로 이동)
    { path: '/profile/search', name: 'profile-search', component: ProfileSearchView },

    {
      path: '/settings',
      name: 'settings',
      component: SettingsView,
    },
  ],
})

export default router
