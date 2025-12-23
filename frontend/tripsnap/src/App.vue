<script setup>
import Banner from './components/Banner.vue'
import Footer from './components/Footer.vue';
</script>

<template>
  <div>
    <Banner />
    <router-view />
    <Footer />
  </div>
</template>
