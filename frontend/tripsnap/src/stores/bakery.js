// src/stores/bakery.js
import { defineStore } from 'pinia'
import { apiFetch, apiJson } from '@/utils/api.js'

export const useBakeryStore = defineStore('bakery', {
  state: () => ({
    // 모달 on/off
    modalOpen: false,
    // 현재 선택된 베이커리 상세 객체 (Django Bakery 직렬화 결과, 위도/경도 포함)
    modalBakery: null,
    // 모달 내 댓글 목록
    modalComments: [],
    // 로딩 상태들
    modalLoadingComments: false,
    modalSubmittingComment: false,
    modalTogglingLike: false,

    // 베이커리 상세 데이터 캐시 (id → detail)
    bakeryCache: {}, // { [id]: bakeryDetail }
  }),

  getters: {
    hasBakery(state) {
      return !!state.modalBakery
    },
  },

  actions: {
    /**
     * 베이커리 상세 정보 조회 (위도/경도 포함)
     * - 캐시가 있으면 캐시 사용
     * - forceRefresh = true 면 무조건 서버에서 새로 가져옴
     */
    async fetchBakeryDetail(bakeryId, { forceRefresh = false } = {}) {
      if (!bakeryId) return null

      // 캐시 사용
      if (!forceRefresh && this.bakeryCache[bakeryId]) {
        this.modalBakery = this.bakeryCache[bakeryId]
        return this.modalBakery
      }

      try {
        const data = await apiJson(`/chatbot/bakery/${bakeryId}/`)

        // 캐시 및 현재 모달용 데이터에 저장 (위도/경도 포함 풀 데이터)
        this.bakeryCache[bakeryId] = data
        this.modalBakery = data
        return data
      } catch (err) {
        console.error('베이커리 상세 불러오기 중 오류:', err)
        return null
      }
    },

    /**
     * 베이커리 모달 열기 (ID 기준)
     * - HomeView, ChatbotView 모두 이 메서드를 쓰는 것을 권장
     * - 내부에서 상세 조회 + 댓글 옵션 처리
     */
    async openModalById(bakeryId, options = {}) {
      if (!bakeryId) return

      const { loadComments = true, forceRefresh = false } = options

      // 상세 로드 (캐시 사용)
      const bakery = await this.fetchBakeryDetail(bakeryId, { forceRefresh })
      if (!bakery) return

      this.modalOpen = true
      this.modalComments = []

      if (loadComments) {
        await this.fetchComments(bakeryId)
      }
    },

    /**
     * 베이커리 모달 열기 (이미 bakery 객체가 있는 경우)
     * - 추천 리스트 등에서 일부 필드만 내려오는 경우가 있으므로,
     *   위도/경도 없으면 ID로 다시 상세 조회를 시도
     */
    async openModal(bakery, options = {}) {
      if (!bakery) {
        this.modalOpen = false
        this.modalBakery = null
        this.modalComments = []
        return
      }

      const { loadComments = false, forceRefresh = false } = options

      // ID가 없다면 그냥 해당 객체로만 모달 오픈
      if (!bakery.id) {
        this.modalBakery = bakery
        this.modalOpen = true
        this.modalComments = []
        return
      }

      // 캐시에 먼저 저장 (간단 정보라도)
      this.bakeryCache[bakery.id] = {
        ...(this.bakeryCache[bakery.id] || {}),
        ...bakery,
      }

      // 위도/경도 등 핵심 필드가 없으면 상세 다시 조회
      const needsDetail =
        forceRefresh ||
        !bakery.latitude ||
        !bakery.longitude ||
        !bakery.road_address

      if (needsDetail) {
        const detail = await this.fetchBakeryDetail(bakery.id, {
          forceRefresh,
        })
        if (!detail) {
          // 상세 실패 시, 최소한 기본 정보로라도 모달 오픈
          this.modalBakery = bakery
        }
      } else {
        this.modalBakery = bakery
      }

      this.modalOpen = true
      this.modalComments = []

      if (loadComments) {
        await this.fetchComments(bakery.id)
      }
    },

    /**
     * 모달 닫기
     * (캐시는 유지해서 재오픈 시 API 호출을 줄임)
     */
    closeModal() {
      this.modalOpen = false
      this.modalBakery = null
      this.modalComments = []
    },

    /**
     * 댓글 목록 조회
     * - ChatbotView 기준 엔드포인트: /chatbot/bakery/<id>/comments/
     */
    async fetchComments(bakeryId) {
      if (!bakeryId) return
      this.modalLoadingComments = true

      try {
        const data = await apiJson(`/chatbot/bakery/${bakeryId}/comments/`)

        // 배열 / {results: []} / {comments: []} 모두 대응
        if (Array.isArray(data)) {
          this.modalComments = data
        } else {
          this.modalComments =
            data.results || data.comments || []
        }
      } catch (err) {
        console.error('댓글 불러오기 중 오류:', err)
        this.modalComments = []
      } finally {
        this.modalLoadingComments = false
      }
    },

    /**
     * 좋아요 토글
     * - ChatbotView 기준 엔드포인트: /chatbot/bakery/<id>/like/
     */
    async toggleLike() {
      if (!this.modalBakery?.id) return

      this.modalTogglingLike = true
      try {
        const data = await apiJson(`/chatbot/bakery/${this.modalBakery.id}/like/`, {
          method: 'POST',
        })

        // 예: { is_liked: true, like_count: 10 } 형태라고 가정
        const updated = {
          ...this.modalBakery,
          is_liked:
            data.is_liked !== undefined
              ? data.is_liked
              : this.modalBakery.is_liked,
          like_count:
            data.like_count !== undefined
              ? data.like_count
              : this.modalBakery.like_count,
        }

        this.modalBakery = updated

        // 캐시에도 반영
        if (updated.id) {
          this.bakeryCache[updated.id] = updated
        }
      } catch (err) {
        console.error('좋아요 토글 중 오류:', err)
      } finally {
        this.modalTogglingLike = false
      }
    },

    /**
     * 댓글 작성
     * - ChatbotView 기준 엔드포인트:
     *   POST /chatbot/bakery/<id>/comments/create/
     */
    async submitComment(content) {
      if (!this.modalBakery?.id) return

      const text = (content || '').trim()
      if (!text) return

      this.modalSubmittingComment = true
      try {
        const data = await apiJson(
          `/chatbot/bakery/${this.modalBakery.id}/comments/create/`,
          {
            method: 'POST',
            body: JSON.stringify({ content: text }),
          }
        )

        // 예: { comment: {...} } or 바로 {...} 로 내려온다고 가정
        const newComment = data.comment || data

        if (newComment && newComment.id) {
          // 최신순 맨 위에 추가
          this.modalComments = [newComment, ...this.modalComments]

          // 모달의 comment_count 증가
          if (this.modalBakery) {
            const updated = {
              ...this.modalBakery,
              comment_count:
                (this.modalBakery.comment_count || 0) + 1,
            }
            this.modalBakery = updated

            // 캐시에도 반영
            if (updated.id) {
              this.bakeryCache[updated.id] = updated
            }
          }
        } else {
          // 응답 형식이 애매하면, 다시 전체 조회
          await this.fetchComments(this.modalBakery.id)
        }
      } catch (err) {
        console.error('댓글 작성 중 오류:', err)
      } finally {
        this.modalSubmittingComment = false
      }
    },
  },
})
