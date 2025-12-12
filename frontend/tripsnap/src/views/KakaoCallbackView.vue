<!-- src/views/KakaoCallbackView.vue -->
<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/users'

const router = useRouter()
const userStore = useUserStore()

onMounted(async () => {
  // Django가 세션/쿠키는 이미 설정한 상태라고 가정하고
  // 현재 유저 정보만 가져와서 스토어에 채운 뒤 홈으로 이동
  await userStore.fetchMe()
  router.push({ name: 'home' })
})
</script>

<template>
  <div>
    <p>카카오 로그인 처리 중입니다...</p>
  </div>
</template>
