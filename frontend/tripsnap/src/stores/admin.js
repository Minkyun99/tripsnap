// src/stores/admin.js
import { defineStore } from 'pinia'
import { apiJson } from '@/utils/api'

export const useAdminStore = defineStore('admin', {
  state: () => ({
    buildingUserKeywords: false,
    lastUserKeywordsBuildMessage: '',
    lastUserKeywordsBuildAt: null,
  }),

  actions: {
    async buildUserKeywords() {
      if (this.buildingUserKeywords) {
        // 중복 클릭 방지
        return
      }

      this.buildingUserKeywords = true
      this.lastUserKeywordsBuildMessage = ''

      try {
        const data = await apiJson('/users/api/settings/build-user-keywords/', {
          method: 'POST',
        })

        this.lastUserKeywordsBuildMessage =
          data?.detail || '사용자 키워드 추출 작업이 실행되었습니다.'
        this.lastUserKeywordsBuildAt = data?.ran_at || null

        return data
      } catch (err) {
        const msg =
          err?.message || '사용자 키워드 추출 작업 실행에 실패했습니다.'
        this.lastUserKeywordsBuildMessage = msg
        throw new Error(msg)
      } finally {
        this.buildingUserKeywords = false
      }
    },
  },
})
