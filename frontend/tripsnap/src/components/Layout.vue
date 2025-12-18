<!-- src/components/Layout.vue -->
<script setup>
import Banner from './Banner.vue'
import Footer from './Footer.vue'
</script>

<template>
  <div class="ts-layout">
    <Banner />

    <main class="ts-layout__main">
      <div class="ts-layout__container">
        <RouterView />
      </div>
    </main>

    <Footer />
  </div>
</template>

<style lang="scss" scoped>
.ts-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.ts-layout__main {
  flex: 1;
  padding: 2rem 1rem;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.ts-layout__container {
  width: 100%;
  max-width: 72rem; // 1152px
}
</style>
