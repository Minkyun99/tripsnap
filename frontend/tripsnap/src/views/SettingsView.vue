<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiJson } from '@/utils/api'
import { getCsrfToken } from '@/utils/csrf'
import { useUserStore } from '@/stores/users'

const router = useRouter()
const userStore = useUserStore()

// ---------------------------
// 팔로우 공개 범위 (3단계)
// ---------------------------
// public: 모두 공개
// following_only: 내가 팔로우한 사람에게만 공개 (백엔드 허용 값에 맞춤)
// private: 완전 비공개
const followVisibility = ref('public')
const followVisibilityMsg = ref('')
const followVisibilityErr = ref('')

// ---------------------------
// 비밀번호 변경
// ---------------------------
const currentPassword = ref('')
const newPassword1 = ref('')
const newPassword2 = ref('')
const pwMsg = ref('')
const pwErr = ref('')
const pwLoading = ref(false)

// ---------------------------
// 회원 탈퇴
// ---------------------------
const deleteConfirm = ref('')
const delMsg = ref('')
const delErr = ref('')
const delLoading = ref(false)

// ✅ 초기 로드: 서버에서 현재 follow_visibility 조회해서 라디오에 반영
onMounted(async () => {
  await userStore.fetchMe().catch(() => {})

  followVisibilityMsg.value = ''
  followVisibilityErr.value = ''

  try {
    // ✅ 설정 전용 엔드포인트 사용 (값: public|following_only|private)
    const data = await userStore.fetchFollowVisibility()
    if (data?.follow_visibility) {
      followVisibility.value = data.follow_visibility
    }
  } catch (e) {
    // 설정 API가 아직 연결 안 되었을 때도 페이지는 동작해야 하므로, 에러만 표시
    followVisibilityErr.value = e?.message || '현재 설정을 불러오지 못했습니다.'
  }
})

async function saveFollowVisibility() {
  followVisibilityMsg.value = ''
  followVisibilityErr.value = ''

  try {
    // ✅ 설정 전용 저장 API 사용
    const data = await userStore.updateFollowVisibility(followVisibility.value)
    if (data?.follow_visibility) {
      followVisibility.value = data.follow_visibility // 서버가 저장한 값으로 동기화
    }
    followVisibilityMsg.value = '저장되었습니다.'
  } catch (e) {
    followVisibilityErr.value = e?.message || '저장에 실패했습니다.'
  }
}

async function changePassword() {
  pwMsg.value = ''
  pwErr.value = ''
  pwLoading.value = true

  try {
    if (!currentPassword.value || !newPassword1.value || !newPassword2.value) {
      throw new Error('모든 비밀번호 입력칸을 채워주세요.')
    }
    if (newPassword1.value !== newPassword2.value) {
      throw new Error('새 비밀번호가 서로 일치하지 않습니다.')
    }

    const csrftoken = getCsrfToken()

    await apiJson('/api/auth/password/change/', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrftoken },
      body: JSON.stringify({
        old_password: currentPassword.value,
        new_password1: newPassword1.value,
        new_password2: newPassword2.value,
      }),
    })

    pwMsg.value = '비밀번호가 변경되었습니다.'
    currentPassword.value = ''
    newPassword1.value = ''
    newPassword2.value = ''
  } catch (e) {
    pwErr.value = e?.message || '비밀번호 변경에 실패했습니다.'
  } finally {
    pwLoading.value = false
  }
}

async function deleteAccount() {
  delMsg.value = ''
  delErr.value = ''
  delLoading.value = true

  try {
    if (deleteConfirm.value.trim() !== '탈퇴') {
      throw new Error("확인을 위해 입력칸에 '탈퇴'를 입력해주세요.")
    }

    const csrftoken = getCsrfToken()

    // ✅ 기존에 사용 중인 엔드포인트 유지
    await apiJson('/users/delete/', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrftoken },
      body: JSON.stringify({}),
    })

    delMsg.value = '회원 탈퇴가 완료되었습니다.'
    await userStore.logout().catch(() => {})
    router.push({ name: 'home' }).catch(() => {})
  } catch (e) {
    delErr.value = e?.message || '회원 탈퇴에 실패했습니다.'
  } finally {
    delLoading.value = false
  }
}
</script>

<template>
  <main class="ts-settings-page">
    <div class="ts-shell">
      <section class="ts-card pixel-corners">
        <header class="ts-settings-header">
          <h2 class="ts-title">설정</h2>
          <p class="ts-subtitle">비밀번호 변경 및 계정/팔로우 공개 범위 설정</p>
        </header>

        <!-- 팔로우 공개 범위 -->
        <div class="ts-block">
          <h3 class="ts-block-title">팔로우 목록 공개 범위</h3>
          <p class="ts-muted">설정하지 않으면 기본값은 <b>모두 공개</b>입니다.</p>

          <div class="ts-radio-group">
            <label class="ts-radio">
              <input type="radio" value="public" v-model="followVisibility" />
              <span>모두 공개</span>
            </label>

            <label class="ts-radio">
              <!-- ✅ value를 followers -> following_only 로 변경 -->
              <input type="radio" value="following_only" v-model="followVisibility" />
              <span>팔로우한 사람에게만 공개</span>
            </label>

            <label class="ts-radio">
              <input type="radio" value="private" v-model="followVisibility" />
              <span>완전 비공개</span>
            </label>
          </div>

          <div class="ts-row">
            <button class="ts-btn ts-btn--pink" type="button" @click="saveFollowVisibility">
              저장
            </button>
            <span v-if="followVisibilityMsg" class="ts-ok">{{ followVisibilityMsg }}</span>
            <span v-if="followVisibilityErr" class="ts-err">{{ followVisibilityErr }}</span>
          </div>
        </div>

        <hr class="ts-divider" />

        <!-- 비밀번호 변경 -->
        <div class="ts-block">
          <h3 class="ts-block-title">비밀번호 변경</h3>

          <div v-if="pwErr" class="ts-alert ts-alert--err">{{ pwErr }}</div>
          <div v-if="pwMsg" class="ts-alert ts-alert--ok">{{ pwMsg }}</div>

          <div class="ts-form">
            <label class="ts-label">현재 비밀번호</label>
            <input
              class="ts-input"
              type="password"
              v-model="currentPassword"
              autocomplete="current-password"
            />

            <label class="ts-label">새 비밀번호</label>
            <input
              class="ts-input"
              type="password"
              v-model="newPassword1"
              autocomplete="new-password"
            />

            <label class="ts-label">새 비밀번호 확인</label>
            <input
              class="ts-input"
              type="password"
              v-model="newPassword2"
              autocomplete="new-password"
            />

            <button
              class="ts-btn ts-btn--pink"
              type="button"
              :disabled="pwLoading"
              @click="changePassword"
            >
              <span v-if="pwLoading">변경 중...</span>
              <span v-else>비밀번호 변경</span>
            </button>
          </div>
        </div>

        <hr class="ts-divider" />

        <!-- 회원 탈퇴 -->
        <div class="ts-block">
          <h3 class="ts-block-title ts-danger">회원 탈퇴</h3>
          <p class="ts-muted">
            탈퇴 시 계정은 삭제되며 복구가 어렵습니다. 계속하려면 아래 입력칸에 <b>탈퇴</b>라고
            입력하세요.
          </p>

          <div v-if="delErr" class="ts-alert ts-alert--err">{{ delErr }}</div>
          <div v-if="delMsg" class="ts-alert ts-alert--ok">{{ delMsg }}</div>

          <div class="ts-form">
            <input class="ts-input" v-model="deleteConfirm" placeholder="탈퇴" />
            <button
              class="ts-btn ts-btn--danger"
              type="button"
              :disabled="delLoading"
              @click="deleteAccount"
            >
              <span v-if="delLoading">처리 중...</span>
              <span v-else>회원 탈퇴</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped lang="scss">
.ts-settings-page {
  padding: 24px 0;
}
.ts-shell {
  max-width: 920px;
  margin: 0 auto;
  padding: 0 16px;
}
.ts-card {
  background: #fffdf8;
  border: 2px solid #ffd09b;
  border-radius: 14px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.06);
  padding: 18px 16px;
}
.ts-settings-header {
  margin-bottom: 14px;
}
.ts-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #8b4513;
}
.ts-subtitle {
  margin: 6px 0 0;
  color: #8b4513;
  opacity: 0.75;
  font-size: 13px;
}
.ts-block {
  padding: 10px 4px;
}
.ts-block-title {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 800;
  color: #8b4513;
}
.ts-muted {
  margin: 0 0 10px;
  font-size: 13px;
  opacity: 0.8;
  color: #6b3a14;
}
.ts-divider {
  border: none;
  border-top: 1px solid #f0d3a0;
  margin: 14px 0;
}
.ts-radio-group {
  display: grid;
  gap: 8px;
  margin: 10px 0 12px;
}
.ts-radio {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b3a14;
  font-weight: 700;
}
.ts-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ts-ok {
  color: #0c7a43;
  font-weight: 700;
  font-size: 13px;
}
.ts-err {
  color: #b00020;
  font-weight: 700;
  font-size: 13px;
}
.ts-alert {
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  margin-bottom: 10px;
}
.ts-alert--err {
  background: #ffe6e6;
  color: #b00020;
}
.ts-alert--ok {
  background: #e9fff1;
  color: #0c7a43;
}
.ts-form {
  display: grid;
  gap: 8px;
  max-width: 520px;
}
.ts-label {
  font-weight: 800;
  color: #8b4513;
  font-size: 13px;
}
.ts-input {
  padding: 10px 10px;
  border-radius: 10px;
  border: 1px solid #d9b38c;
  outline: none;
  background: #fff;
}
.ts-input:focus {
  border-color: #d2691e;
  box-shadow: 0 0 0 1px rgba(210, 105, 30, 0.2);
}
.ts-btn {
  padding: 10px 12px;
  border-radius: 12px;
  font-weight: 800;
  border: 2px solid #d2691e;
  cursor: pointer;
}
.ts-btn--pink {
  background: #d2691e;
  color: #fff;
}
.ts-btn--pink:hover {
  background: #8b4513;
  border-color: #8b4513;
}
.ts-btn--danger {
  background: #b00020;
  border-color: #b00020;
  color: #fff;
}
.ts-btn--danger:hover {
  filter: brightness(0.95);
}
.ts-btn:disabled {
  opacity: 0.7;
  cursor: default;
}
.ts-danger {
  color: #b00020;
}
</style>
