import os
import importlib.util
from typing import List, Dict, Any

# repo 루트 및 모델 파일 위치
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_PATH = os.path.join(BASE_DIR, "chatbot-model", "bakery_rag_chatbot.py")


class BakeryRAGSystem:
    """
    기존 `BakeryRAGSystem` 인터페이스를 유지하는 어댑터.
    내부적으로 `BakeryExpertRAG`를 사용한다.
    """

    def __init__(self, *args, **kwargs):
        # 기존 데이터/벡터 DB 위치와 호환되도록 경로를 조정
        model_dir = os.path.join(BASE_DIR, "chatbot-model")

        # 우선순위: chatbot-model 내부의 튜닝된 파일들을 사용
        # dessert: prefer 'dessert_en.json', then 'dessert_reviews.json', else fallback to chatbot/dessert.json
        candidate_desserts = [
            os.path.join(model_dir, "dessert_en.json"),
            os.path.join(model_dir, "dessert_reviews.json"),
            os.path.join(BASE_DIR, "chatbot", "dessert.json"),
        ]
        dessert_path = next((p for p in candidate_desserts if os.path.exists(p)), candidate_desserts[-1])

        base_keywords = os.path.join(model_dir, "base_keywords.json")

        # vectordb: prefer tuned directory inside chatbot-model
        vectordb = os.path.join(model_dir, "bakery_vectordb_tuned")
        if not os.path.exists(vectordb):
            # fallback to legacy path at repo root
            vectordb = os.path.join(BASE_DIR, "bakery_vectordb")
        # BakeryExpertRAG 동적 로드 및 초기화 (의존성 없는 경우 에러를 던짐)
        try:
            # Ensure chatbot-model dir is on sys.path so imports like
            # `from schemas import ...` inside the module resolve to the
            # local chatbot-model/schemas.py
            model_dir = os.path.dirname(MODEL_PATH)
            import sys
            if model_dir not in sys.path:
                sys.path.insert(0, model_dir)

            spec = importlib.util.spec_from_file_location("bakery_rag_chatbot", MODEL_PATH)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            BakeryExpertRAG = getattr(mod, "BakeryExpertRAG")
            self._safe_get_rating = getattr(mod, "_safe_get_rating", None)

            self.rag = BakeryExpertRAG(
                dessert_path=dessert_path,
                base_keywords_path=base_keywords,
                vectordb_path=vectordb,
            )
        except Exception as e:
            # import 실패시 명확한 에러로 상위에서 처리하도록 던짐
            raise

        # collection.count() 호환 레이어
        class _Col:
            def __init__(self, outer):
                self._outer = outer

            def count(self):
                try:
                    # chroma collection에 count()가 있으면 사용
                    col = getattr(self._outer.rag, "bakery_collection", None)
                    if col is not None and hasattr(col, "count"):
                        return col.count()
                except Exception:
                    pass
                # fallback: 메모리상 로드된 bakeries 갯수
                try:
                    return len(self._outer.rag.bakeries)
                except Exception:
                    return 0

        self.collection = _Col(self)

    def load_and_index_bakeries(self, data_file: str = None, force_reindex: bool = False):
        # BakeryExpertRAG은 생성 시 데이터 파일을 로드합니다. 추가 인덱싱이 필요하면
        # 여기에서 구현할 수 있으나, 현재는 no-op으로 둡니다.
        return

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        # 내부의 벡터 검색 유틸을 사용
        try:
            cand = self.rag._vector_search_bakeries([query], top_k=top_k)
        except Exception:
            # 실패 시 전체 목록 반환
            try:
                return list(self.rag.bakeries)[:top_k]
            except Exception:
                return []

        results: List[Dict[str, Any]] = []
        for b in cand[:top_k]:
            r = {
                "place_name": b.get("name") or b.get("slug_en"),
                "name": b.get("name"),
                "district": b.get("district") or b.get("_district"),
                "address": b.get("road_address") or b.get("jibun_address") or b.get("address", ""),
                "phone": b.get("phone", ""),
                "url": b.get("url", ""),
            }
            # 평점 정보가 필요하면 _safe_get_rating을 사용
            try:
                if getattr(self, "_safe_get_rating", None):
                    r["rating"] = self._safe_get_rating(b)
                else:
                    r["rating"] = b.get("rating", "")
            except Exception:
                r["rating"] = b.get("rating", "")

            # 키워드 필드
            r["keywords"] = ", ".join(b.get("keywords", [])) if isinstance(b.get("keywords"), list) else b.get("keywords", "")

            results.append(r)

        return results

    def generate_llm_response(self, query: str, search_results: List[Dict], use_openai: bool = False) -> str:
        # BakeryExpertRAG의 answer_query를 사용 (내부적으로 LLM/템플릿 로직 포함)
        try:
            # answer_query 사용 시 내부적으로 검색도 수행할 수 있으므로, 간단히 호출
            return self.rag.answer_query(query)
        except Exception:
            # 폴백: 간단 템플릿 응답
            if not search_results:
                return "죄송합니다. 해당 조건에 맞는 빵집을 찾지 못했습니다."
            resp = f"{query}에 대한 추천 결과입니다:\n"
            for i, s in enumerate(search_results[:3], 1):
                resp += f"{i}. {s.get('place_name') or s.get('name')}\n"
            return resp
