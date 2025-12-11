<template>
    <div>
        
        <p>{{ someState }}</p>
        <button @click="storeName.someAction('payload')">Action 실행</button>
    </div>
</template>

<script setup>
import { useStoreName } from '../stores/storeFileName';
import { storeToRefs } from 'pinia';
import { ref, computed } from 'vue';

// 1. Store 인스턴스 가져오기
const storeName = useStoreName();

// 2. State만 비구조화 할당하여 반응성 유지
const { someState } = storeToRefs(storeName);

// 3. Getter 또는 Action은 직접 접근
// const someAction = storeName.someAction;

</script>

<style scoped></style>