// src/stores/ui.js
import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', {
  state: () => ({
    globalLoading: false,
    toast: null, // { type: 'success'|'error', message: string }
  }),
  actions: {
    showLoading() {
      this.globalLoading = true
    },
    hideLoading() {
      this.globalLoading = false
    },
    showToast(type, message) {
      this.toast = { type, message }
      setTimeout(() => {
        this.toast = null
      }, 3000)
    },
  },
})
