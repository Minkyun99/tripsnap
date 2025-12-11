// src/stores/chatbot.js
import { defineStore } from 'pinia'

const API_BASE = 'http://localhost:8000'

export const useChatbotStore = defineStore('chatbot', {
  state: () => ({
    messages: [],        // { role: 'user'|'bot'|'system', text: string }
    conversationId: null,
    isLoading: false,
    error: null,
    lastResults: [],     // RAG 결과 리스트 등
  }),
  actions: {
    reset() {
      this.messages = []
      this.conversationId = null
      this.lastResults = []
      this.error = null
    },

    addMessage(role, text) {
      this.messages.push({ role, text })
    },

    async sendMessage({ text, trigger = true }) {
      if (!text?.trim()) return

      // 1) 사용자 메시지를 먼저 로컬에 추가
      this.addMessage('user', text)

      this.isLoading = true
      this.error = null
      try {
        const payload = {
          message: text,
          trigger,                         // '추천' 강제 트리거 플래그
          conversation_id: this.conversationId,
        }

        const res = await fetch(`${API_BASE}/chatbot/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(payload),
        })
        if (!res.ok) {
          // 401이면 로그인 필요
          if (res.status === 401) {
            throw new Error('로그인이 필요합니다.')
          }
          throw new Error('챗봇 응답 실패')
        }
        const data = await res.json()

        // views.chat 기준:
        // - 추천을 호출 안 하면: { "saved": True }
        // - 호출하면: { "llm_response": "...", "results": [...] }

        if (data.llm_response) {
          this.addMessage('bot', data.llm_response)
        }
        if (data.results) {
          this.lastResults = data.results
        }

        // conversation_id를 응답에 추가하셨다면 여기서 같이 관리 가능
        if (data.conversation_id) {
          this.conversationId = data.conversation_id
        }
      } catch (err) {
        this.error = err.message ?? '챗봇 통신 중 오류'
      } finally {
        this.isLoading = false
      }
    },
  },
})
