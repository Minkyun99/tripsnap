<!-- src/components/Footer.vue -->
<script setup></script>

<template>
  <footer class="ts-footer pixel-corners">
    <p class="ts-footer__text-main">✨ 맛있는 빵집을 찾아 행복한 여행을 만들어요 ✨</p>
    <p class="ts-footer__text-sub">Made with 💖 by tripsnap</p>
  </footer>
</template>

<style lang="scss" scoped>
$ts-footer-bg: #ffe8cc;
$ts-border-brown: #d2691e;
$ts-text-brown: #8b4513;

.ts-footer {
  background-color: $ts-footer-bg;
  border-top: 4px solid $ts-border-brown;
  padding: 1rem;
  text-align: center;
}

.ts-footer__text-main {
  margin: 0;
  color: $ts-text-brown;
  font-weight: 600;
}

.ts-footer__text-sub {
  margin: 0.25rem 0 0;
  font-size: 0.75rem;
  color: $ts-border-brown;
  font-weight: 500;
}
</style>
