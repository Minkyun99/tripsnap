// src/stores/chatbot.js
import { defineStore } from 'pinia'

export const useChatStore = defineStore('chatbot', {
  state: () => ({
    // 백엔드 Conversation.id
    conversationId: null,
    // 채팅 메시지 목록
    // 각 메시지: { id: number, role: 'user' | 'bot', text: string }
    messages: [],
  }),

  actions: {
    /**
     * 키워드 선택 → /chatbot/init/ 응답으로 받은 초기 대화 세팅
     * @param {string|number} conversationId
     * @param {Array<{role: string, content: string}>} initialMessages
     */
    setInitialConversation(conversationId, initialMessages) {
      this.conversationId = conversationId

      let idCounter = 1
      this.messages = (initialMessages || []).map((m) => ({
        id: idCounter++,
        role: m.role, // 'user' 또는 'bot' 형태로 들어온다고 가정
        text: m.content, // 내용
      }))
    },

    /**
     * 메시지 하나 추가
     * @param {'user'|'bot'} role
     * @param {string} text
     */
    appendMessage(role, text) {
      const nextId = (this.messages[this.messages.length - 1]?.id || 0) + 1
      this.messages.push({
        id: nextId,
        role,
        text,
      })
    },

    /**
     * 대화 리셋 (새 키워드 선택 시 등)
     */
    reset() {
      this.conversationId = null
      this.messages = []
    },
  },
})
