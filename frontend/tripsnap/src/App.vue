<!-- src/App.vue -->
<script setup>
import Banner from '@/components/Banner.vue'
import Footer from '@/components/Footer.vue'
</script>

<template>
  <div class="ts-app">
    <!-- 상단 고정 배너 -->
    <Banner />

    <!-- 가운데 메인 컨텐츠 영역 -->
    <main class="ts-app__main">
      <div class="ts-app__content">
        <router-view />
      </div>
    </main>

    <!-- 하단 고정 푸터 -->
    <Footer />
  </div>
</template>