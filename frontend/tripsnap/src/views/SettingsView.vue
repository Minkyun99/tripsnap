<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiJson } from '@/utils/api'
import { getCsrfToken } from '@/utils/csrf'
import { useUserStore } from '@/stores/users'
import { useAdminStore } from '@/stores/admin'

const router = useRouter()
const userStore = useUserStore()
const adminStore = useAdminStore()

// ---------------------------
// 관리자 여부 (이메일 기준)
// ---------------------------
const isAdmin = computed(() => {
  const u = userStore.user
  return !!u && u.email === 'tripsnap@tripsnap.com'
})

// ---------------------------
// 팔로우 공개 범위 (3단계)
// ---------------------------
// public: 모두 공개
// following_only: 내가 팔로우한 사람에게만 공개
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

// ---------------------------
// 사용자 키워드 재빌드
// ---------------------------
const keywordBuildMsg = ref('')
const keywordBuildErr = ref('')
const keywordBuildLoading = ref(false)

// ✅ 초기 로드: 서버에서 현재 follow_visibility 조회해서 라디오에 반영
onMounted(async () => {
  await userStore.fetchMe().catch(() => {})

  followVisibilityMsg.value = ''
  followVisibilityErr.value = ''

  try {
    const data = await userStore.fetchFollowVisibility()
    if (data?.follow_visibility) {
      followVisibility.value = data.follow_visibility
    }
  } catch (e) {
    followVisibilityErr.value = e?.message || '현재 설정을 불러오지 못했습니다.'
  }
})

// ---------------------------
// 팔로우 공개 범위 저장
// ---------------------------
async function saveFollowVisibility() {
  followVisibilityMsg.value = ''
  followVisibilityErr.value = ''

  try {
    const data = await apiJson('/users/api/settings/follow-visibility/', {
      method: 'POST',
      body: JSON.stringify({
        follow_visibility: followVisibility.value,
      }),
    })

    followVisibilityMsg.value =
      data?.detail || '팔로우 공개 범위가 저장되었습니다.'
  } catch (e) {
    followVisibilityErr.value =
      e?.message || '팔로우 공개 범위 저장에 실패했습니다.'
  }
}

// ---------------------------
// 비밀번호 변경
// ---------------------------
async function changePassword() {
  pwMsg.value = ''
  pwErr.value = ''
  pwLoading.value = true

  try {
    await apiJson('/api/auth/password/change/', {
      method: 'POST',
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

// ---------------------------
// 회원 탈퇴
// ---------------------------
async function deleteAccount() {
  delMsg.value = ''
  delErr.value = ''
  delLoading.value = true

  try {
    if (deleteConfirm.value.trim() !== '탈퇴') {
      throw new Error("확인을 위해 입력칸에 '탈퇴'를 입력해주세요.")
    }

    const csrftoken = getCsrfToken()

    await apiJson('/users/delete/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrftoken,
      },
    })

    delMsg.value = '회원 탈퇴가 완료되었습니다.'
    await userStore.logout()
    router.push({ name: 'home' })
  } catch (e) {
    delErr.value = e?.message || '회원 탈퇴에 실패했습니다.'
  } finally {
    delLoading.value = false
  }
}

// ---------------------------
// 사용자 키워드 추출 버튼 동작 (관리자 전용)
// ---------------------------
async function onClickBuildUserKeywords() {
  keywordBuildMsg.value = ''
  keywordBuildErr.value = ''
  keywordBuildLoading.value = true

  try {
    const data = await adminStore.buildUserKeywords()
    keywordBuildMsg.value =
      data?.detail || '사용자 키워드 추출 작업이 실행되었습니다.'
  } catch (e) {
    keywordBuildErr.value =
      e?.message || '사용자 키워드 추출 작업 실행에 실패했습니다.'
  } finally {
    keywordBuildLoading.value = false
  }
}

function goBackToMyProfile() {
  router.push({ name: 'profile' })
}
</script>

<template>
  <main class="ts-settings-page">
    <div class="ts-shell">
      <!-- 뒤로가기 버튼 -->
      <button
        class="ts-back-btn"
        type="button"
        @click="goBackToMyProfile"
      >
        👈 내 프로필로
      </button>

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
              <input
                type="radio"
                value="following_only"
                v-model="followVisibility"
              />
              <span>팔로우한 사람에게만 공개</span>
            </label>

            <label class="ts-radio">
              <input type="radio" value="private" v-model="followVisibility" />
              <span>완전 비공개</span>
            </label>
          </div>

          <div class="ts-row">
            <button
              class="ts-btn ts-btn--pink"
              type="button"
              @click="saveFollowVisibility"
            >
              저장
            </button>
            <span v-if="followVisibilityMsg" class="ts-ok">
              {{ followVisibilityMsg }}
            </span>
            <span v-if="followVisibilityErr" class="ts-err">
              {{ followVisibilityErr }}
            </span>
          </div>
        </div>

        <hr class="ts-divider" />

        <!-- ✅ 관리자 전용: 사용자 키워드 계산 -->
        <div
          v-if="isAdmin"
          class="ts-block"
        >
          <h3 class="ts-block-title">사용자 키워드 계산</h3>
          <p class="ts-muted">
            모든 사용자의 DB 데이터를 기반으로, 추천에 사용할 사용자 키워드를 다시 계산합니다.
          </p>

          <div
            v-if="keywordBuildErr"
            class="ts-alert ts-alert--err"
          >
            {{ keywordBuildErr }}
          </div>
          <div
            v-if="keywordBuildMsg"
            class="ts-alert ts-alert--ok"
          >
            {{ keywordBuildMsg }}
          </div>

          <div class="ts-row">
            <button
              class="ts-btn ts-btn--pink"
              type="button"
              :disabled="keywordBuildLoading"
              @click="onClickBuildUserKeywords"
            >
              <span v-if="keywordBuildLoading">계산 중...</span>
              <span v-else>키워드 계산하기</span>
            </button>
          </div>
        </div>

        <hr
          v-if="isAdmin"
          class="ts-divider"
        />

        <!-- 비밀번호 변경 -->
        <div class="ts-block">
          <h3 class="ts-block-title">비밀번호 변경</h3>

          <div
            v-if="pwErr"
            class="ts-alert ts-alert--err"
          >
            {{ pwErr }}
          </div>
          <div
            v-if="pwMsg"
            class="ts-alert ts-alert--ok"
          >
            {{ pwMsg }}
          </div>

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

          <div
            v-if="delErr"
            class="ts-alert ts-alert--err"
          >
            {{ delErr }}
          </div>
          <div
            v-if="delMsg"
            class="ts-alert ts-alert--ok"
          >
            {{ delMsg }}
          </div>

          <div class="ts-form">
            <input
              class="ts-input"
              v-model="deleteConfirm"
              placeholder="탈퇴"
            />
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

<style lang="scss" scoped>
@import '@/assets/styles/users/settings.scss';
</style>
