# bakery_rag_chatbot.py (상단 부분)

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from schemas import DateTimeConstraint, LocationFilter
from location_module import (
    annotate_admin_areas,
    extract_location_from_query,
    filter_bakeries_by_location,
    haversine,
)
from time_module import (
    build_business_hours_index,
    is_available_in_period,
    is_open_at,
    parse_date_time_from_query,
)
from ranking_module import (
    build_review_stats_cache,
    compute_popularity_score,
    detect_flagship_tour_intent,
    extract_menu_keywords,
    generate_search_queries,
) 

from ranking_utils import rank_bakeries  # ✅ 최종 랭킹은 여기 함수만 사용




class BakeryExpertRAG:
    def __init__(
        self,
        dessert_path: str = "dessert_en.json",
        base_keywords_path: str = "base_keywords.json",
        vectordb_path: str = "./bakery_vectordb_tuned",
    ):
        print("============================================================")
        print("🍞 빵집 추천 전문가 RAG 시스템 (모듈 분리 + Upstage LLM 재랭킹)")
        print("============================================================\n")


        self.dessert_path = dessert_path
        self.base_keywords_path = base_keywords_path
        self.vectordb_path = vectordb_path

        # ---------- 데이터 로드 ----------
        with open(self.dessert_path, "r", encoding="utf-8") as f:
            self.bakeries: List[Dict[str, Any]] = json.load(f)
        print(f"📂 빵집 마스터 데이터 로드: {len(self.bakeries)}개 매장")

        with open(self.base_keywords_path, "r", encoding="utf-8") as f:
            self.base_keywords = json.load(f)
        self.menu_keywords_set = set(self.base_keywords.get("menu", []))
        print(
            f"📚 base_keywords.json 로드 완료: 메뉴 {len(self.base_keywords.get('menu', []))}개, "
            f"맛 {len(self.base_keywords.get('taste', []))}개, "
            f"식감 {len(self.base_keywords.get('texture', []))}개, "
            f"토핑 {len(self.base_keywords.get('topping', []))}개, "
            f"매장 {len(self.base_keywords.get('store', []))}개"
        )

        # ---------- 행정구역 메타데이터 ----------
        annotate_admin_areas(self.bakeries)
        print("📍 행정구역(구/동) 메타데이터 구축 완료")

        # ---------- 영업시간 인덱스 ----------
        self.business_hours_index = build_business_hours_index(self.bakeries)
        print(
            f"🕒 요일별 영업시간 인덱스 구축 완료: "
            f"{len(self.business_hours_index)}개 매장에 영업시간 정보 존재"
        )

        # ---------- 리뷰 통계 캐시 ----------
        self.review_stats_cache = build_review_stats_cache(self.bakeries)
        print(
            f"📊 리뷰 키워드 통계 캐시 완료: {len(self.review_stats_cache)}개 매장에서 키워드 등장"
        )

        # ---------- slug/name → bakery 매핑 ----------
        self.bakery_by_slug: Dict[str, Dict[str, Any]] = {}
        self.bakery_by_name: Dict[str, Dict[str, Any]] = {}
        for b in self.bakeries:
            slug = b.get("slug_en") or b.get("name")
            if slug:
                self.bakery_by_slug[slug] = b
            name = b.get("name")
            if name:
                self.bakery_by_name[name] = b

        # ---------- 벡터 DB (Chroma + HF 임베딩) ----------
        print("📦 임베딩 모델 로드 중: jhgan/ko-sroberta-multitask")
        self.embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )

        print(f"💾 벡터 DB 초기화: {os.path.abspath(self.vectordb_path)}")
        self.chroma_client = chromadb.PersistentClient(path=self.vectordb_path)
        self.bakery_collection = self.chroma_client.get_or_create_collection(
            name="bakery_collection",
            embedding_function=self.embedding_fn,
        )
        print("✅ 빵집 컬렉션 연결: bakery_collection")

        try:
            self.review_collection = self.chroma_client.get_collection(
                name="review_collection"
            )
            print("✅ 리뷰 키워드 컬렉션 연결: review_collection")
        except Exception:
            self.review_collection = None
            print("⚠️ review_collection 조회 실패 – 빵집 컬렉션만 사용합니다.")

        # ---------- Upstage LLM (재랭킹용) ----------
        self.llm_client = None
        api_key = os.getenv("UPSTAGE_API_KEY", "")
        if api_key:
            try:
                self.llm_client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.upstage.ai/v1",
                )
                print("🧠 Upstage LLM(solar-pro-2) 클라이언트 초기화 완료 (재랭킹용)")
            except Exception as e:
                print(f"⚠️ Upstage LLM 클라이언트 초기화 실패: {e}")
        else:
            print("⚠️ UPSTAGE_API_KEY 환경 변수가 없어 LLM 재랭킹을 비활성화합니다.")

        print("✅ 시스템 초기화 완료!\n")

        # 플래그십 빵집 리스트 (빵지순례/대표 코스용)
        self.known_flagship_names = [
            "성심당",
            "성심당 본점",
            "몽심",
            "몽심 대흥점",
            "몽심 도안점",
            "콜드버터",
            "콜드버터베이커리",
            "콜드버터베이크샵",
            "그린베이커리",
            "이런날",
        ]

    # ==============================
    #  벡터 검색
    # ==============================

    def _vector_search_bakeries(
        self,
        queries: List[str],
        top_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        bakery_collection에서 여러 쿼리로 검색한 뒤,
        slug_en 기준으로 union한 후보 집합을 만든다.
        """
        if self.bakery_collection is None:
            return list(self.bakeries)

        slug_scores: Dict[str, float] = {}
        for q in queries:
            try:
                res = self.bakery_collection.query(
                    query_texts=[q],
                    n_results=top_k,
                )
            except Exception as e:
                print(f"⚠️ 벡터 검색 중 오류 발생('{q}') → 전체 데이터로 fallback: {e}")
                return list(self.bakeries)

            ids_list = res.get("ids", [[]])[0]
            dists = res.get("distances", [[]])[0] if "distances" in res else [0.0] * len(
                ids_list
            )

            for doc_id, dist in zip(ids_list, dists):
                slug = doc_id
                if isinstance(slug, list):
                    slug = slug[0]
                if not isinstance(slug, str):
                    continue
                score = -float(dist) if dist is not None else 0.0
                if slug in slug_scores:
                    slug_scores[slug] = max(slug_scores[slug], score)
                else:
                    slug_scores[slug] = score

        candidates: List[Dict[str, Any]] = []
        for slug in slug_scores.keys():
            b = self.bakery_by_slug.get(slug)
            if b is not None:
                candidates.append(b)

        if not candidates:
            return list(self.bakeries)

        return candidates

    # ==============================
    #  LLM 재랭킹
    # ==============================

    def _rerank_with_llm(
        self,
        user_query: str,
        ranked: List[Tuple[Dict[str, Any], float]],
        max_items: int = 10,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Upstage solar-pro-2로 상위 후보를 한 번 더 재정렬한다.
        """
        if self.llm_client is None:
            return ranked
        if not ranked:
            return ranked

        top_slice = ranked[:max_items]

        items_desc = []
        for idx, (bakery, score) in enumerate(top_slice, start=1):
            name = bakery.get("name") or bakery.get("slug_en") or f"bakery-{idx}"
            district = bakery.get("district") or bakery.get("_district") or ""
            rating = _safe_get_rating(bakery)
            kd = bakery.get("keyword_details") or {}
            final_kw = kd.get("final_keywords") or []
            items_desc.append(
                f"{idx}. 이름: {name}, 지역: {district}, 평점: {rating}, 대표 키워드: {', '.join(final_kw[:8])}"
            )

        system_prompt = (
            "당신은 빵집 추천을 재정렬하는 전문가입니다. "
            "사용자의 질문과 아래 빵집 목록을 보고, 질문과 가장 잘 맞는 순서대로 나열해 주세요. "
            "출력은 선택한 번호를 쉼표로 구분한 형태(예: '2,1,3,5,4')만 반환하세요. "
            "다른 설명, 불필요한 텍스트는 절대 쓰지 마세요."
        )

        user_prompt = (
            f"질문: {user_query}\n\n"
            "후보 빵집 목록:\n" + "\n".join(items_desc) + "\n\n"
            "질문과 가장 잘 맞는 순서대로 번호만 나열해 주세요."
        )

        try:
            resp = self.llm_client.chat.completions.create(
                model="solar-pro-2",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=64,
            )
            text = resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ LLM 재랭킹 호출 실패, 내부 스코어 사용: {e}")
            return ranked

        order: List[int] = []
        for token in text.replace(" ", "").split(","):
            if not token:
                continue
            try:
                n = int(token)
                if 1 <= n <= len(top_slice):
                    order.append(n)
            except ValueError:
                continue

        if not order:
            return ranked

        idx_to_item = {i + 1: item for i, item in enumerate(top_slice)}
        new_top: List[Tuple[Dict[str, Any], float]] = []
        added = set()
        for n in order:
            if n in idx_to_item and n not in added:
                new_top.append(idx_to_item[n])
                added.add(n)
        for i in range(1, len(top_slice) + 1):
            if i not in added:
                new_top.append(idx_to_item[i])

        tail = ranked[len(top_slice):]
        return new_top + tail

    # ==============================
    #  메인 질의 처리
    # ==============================

    def answer_query(self, query: str) -> str:
        print("============================================================")
        print(f"🔍 '{query}'")
        print("============================================================")

        # 1) 날짜/시간 파싱
        constraint: DateTimeConstraint = parse_date_time_from_query(query)
        if constraint.has_date_range:
            print(
                f"   📅 방문 기간 인식: {constraint.start_date} ~ {constraint.end_date}"
            )
        if constraint.start_time or constraint.end_time:
            st = (
                constraint.start_time.strftime("%H:%M")
                if constraint.start_time
                else "제한 없음"
            )
            et = (
                constraint.end_time.strftime("%H:%M")
                if constraint.end_time
                else "제한 없음"
            )
            print(f"   🕒 방문 시간대 인식: {st} ~ {et}")
        elif constraint.use_now_if_missing:
            print("   🕒 시간 언급 없음 → 현재 시각 기준 '영업 중' 매장만 추천")

        # 2) 위치 파싱
        loc_filter, loc_logs = extract_location_from_query(query)
        for line in loc_logs:
            print(line)

        # 3) 메뉴 키워드
        menu_keywords = extract_menu_keywords(query, self.menu_keywords_set)
        if menu_keywords:
            print(f"   🍞 메뉴 키워드 인식: {menu_keywords}")
        else:
            print("   ℹ️ 메뉴 키워드를 명확히 찾지 못했습니다. 디저트/빵집 중심으로 검색합니다.")

        # 4) 빵지순례/대표 코스 의도 탐지
        intent_flags = detect_flagship_tour_intent(query, menu_keywords)
        if intent_flags["is_flagship_tour"]:
            print("   🧭 의도: '대전 대표 빵집' 또는 '빵지순례 코스' 추천 모드")

        # 5) 벡터 검색용 서브 쿼리 생성
        queries = generate_search_queries(query, menu_keywords, loc_filter, intent_flags)
        print("   🔍 벡터 검색용 생성 쿼리:")
        for q in queries:
            print(f"      - {q}")

        # 6) 벡터 검색
        raw_candidates = self._vector_search_bakeries(queries, top_k=60)
        print(f"   🔎 벡터 검색 기반 1차 후보: {len(raw_candidates)}개")

        # 7) 위치 필터
        loc_filtered = filter_bakeries_by_location(raw_candidates, loc_filter)
        print(f"   📍 위치/범위 필터 후 후보: {len(loc_filtered)}개")

        # 8) 시간/영업 필터
                # 8) 시간/영업 + 네이버 임시휴무 필터
        final_candidates: List[Dict[str, Any]] = []
        last_close_map: Dict[str, datetime.time] = {}

        # 임시휴무 체크 대상 날짜 결정
        # - 현재 시각 기준 질의: 오늘 날짜
        # - 날짜 범위 질의: start_date ~ end_date 중 '해당 날짜에 전부 휴무인 경우'만 제외하는 로직으로도 확장 가능
        #   여기서는 단순화를 위해,
        #   - use_now_if_missing: 오늘 날짜만 임시휴무면 제외
        #   - 날짜 범위: start_date 기준으로 임시휴무면 제외 (필요시 더 정교하게 변경 가능)
        from datetime import date as _date

        if constraint.use_now_if_missing:
            target_check_date = datetime.now().date()
        else:
            target_check_date = constraint.start_date or datetime.now().date()

        def _is_temp_closed(bakery) -> bool:
            url = bakery.get("url") or ""
            if not url:
                return False
            try:
                return is_temporarily_closed_by_naver(url, target_check_date)
            except Exception as e:
                print(f"⚠️ 네이버 임시휴무 체크 중 오류 발생({url}): {e}")
                return False

        if constraint.use_now_if_missing:
            now = datetime.now()
            before = len(loc_filtered)
            for b in loc_filtered:
                # 1) 임시휴무면 바로 제외
                if _is_temp_closed(b):
                    continue
                # 2) 정규 영업시간 기준으로 '현재 영업 중'인지 체크
                if is_open_at(b, now, self.business_hours_index):
                    final_candidates.append(b)
            print(
                f"   🕒 현재 영업 중 + 임시휴무 필터 적용 전 {before}개 → 후 {len(final_candidates)}개"
            )
        else:
            before = len(loc_filtered)
            for b in loc_filtered:
                # 1) 임시휴무면 제외 (여기서는 start_date 기준으로 판단)
                if _is_temp_closed(b):
                    continue

                # 2) 기존 기간/시간 로직
                ok, last_close = is_available_in_period(b, constraint, self.business_hours_index)
                if ok:
                    final_candidates.append(b)
                    if last_close:
                        name = b.get("name") or b.get("slug_en") or ""
                        last_close_map[name] = last_close
            print(f"   🕒 방문 기간/시간 + 임시휴무 필터 적용 전 {before}개 → 후 {len(final_candidates)}개")

        if not final_candidates:
            return "조건에 맞는 영업 중인 빵집을 찾지 못했습니다. 날짜/시간 또는 지역 범위를 조금 넓혀서 다시 요청해 주세요."

        # 9) 메뉴/플래그십/리뷰 기반 스코어링
        ranked = rank_bakeries(
            candidates=final_candidates,
            menu_keywords=menu_keywords,
            intent_flags=intent_flags,
            review_stats_cache=self.review_stats_cache,
            known_flagship_names=self.known_flagship_names,
            top_k=10,
        )

        # 10) (옵션) LLM 재랭킹
        try:
            ranked = self._rerank_with_llm(query, ranked)
        except Exception as e:
            print(f"⚠️ LLM 재랭킹 중 오류 발생, 내부 스코어 순서 사용: {e}")

        top_n = ranked[:10]

        # 11) 답변 구성
        lines: List[str] = []
        lines.append("안녕하세요, 30년간 제빵 현장에서 일해온 빵집 전문가입니다.\n")
        lines.append("요청하신 조건에 맞춰 아래 빵집들을 추천드립니다.\n")

        for idx, (bakery, score) in enumerate(top_n, start=1):
            name = bakery.get("name") or bakery.get("slug_en") or "이름 미상"
            district = bakery.get("district") or bakery.get("_district") or "-"
            road_addr = bakery.get("road_address") or "-"
            rating_info = bakery.get("rating") or {}
            rating = (
                rating_info.get("naver_rate")
                or rating_info.get("kakao_rate")
                or "정보 없음"
            )

            total_reviews, _ = (
                self.review_stats_cache.get(name)
                if name in self.review_stats_cache
                else (0, {})
            )
            pop_score = compute_popularity_score(bakery, self.review_stats_cache)

            lines.append("==================================================")
            lines.append(f"🥖 추천 {idx}: {name}")
            lines.append("==================================================")
            lines.append(
                f"⭐ 통합 평점(추정): {rating}점 / 리뷰 규모: {total_reviews:,}건 수준 "
                f"(인기도 점수: {pop_score:.2f})"
            )
            lines.append(f"📍 위치: {district}")
            lines.append(f"📡 도로명 주소: {road_addr}")

            # point 기반일 때 거리
            if (
                isinstance(loc_filter, LocationFilter)
                and loc_filter.kind == "point"
                and loc_filter.lat is not None
                and loc_filter.lon is not None
            ):
                try:
                    lat = float(bakery.get("latitude", 0) or 0)
                    lon = float(bakery.get("longitude", 0) or 0)
                    if lat and lon:
                        dist = haversine(loc_filter.lat, loc_filter.lon, lat, lon)
                        lines.append(f"📏 기준 위치로부터 거리: 약 {dist:.2f}km")
                except Exception:
                    pass

            # 기간 질의 + 라스트오더 안내
            if constraint.has_date_range and constraint.end_date and constraint.end_time:
                bname = name
                if bname in last_close_map:
                    last_t = last_close_map[bname]
                    if last_t < constraint.end_time:
                        lines.append(
                            f"⚠️ 참고: {constraint.end_date} 기준 라스트오더/마감 시간은 "
                            f"{last_t.strftime('%H:%M')}라, 요청하신 종료 시각({constraint.end_time.strftime('%H:%M')})보다 조금 이른 편입니다."
                        )

            # 리뷰 키워드
            rk = bakery.get("review_keywords") or []
            top_rk = rk[:5]
            if top_rk:
                desc = []
                for r in top_rk:
                    kw = r.get("keyword")
                    c = r.get("count")
                    desc.append(f"{kw} {c}회")
                lines.append("\n✨ 이 집의 특징(리뷰 키워드 상위):")
                lines.append("   - " + ", ".join(desc))

            # 대표 메뉴/키워드
            kd = bakery.get("keyword_details") or {}
            final_kw = kd.get("final_keywords") or []
            if final_kw:
                show = final_kw[:8]
                lines.append("\n   - 대표 메뉴/키워드: " + ", ".join(show))

            lines.append("\n👨‍🍳 전문가 코멘트:")
            if intent_flags["is_flagship_tour"]:
                lines.append(
                    "   대전에서 이름이 잘 알려진 빵집 중 하나로, 빵지순례 코스에 넣기 좋은 매장입니다. "
                    "리뷰 규모와 평점을 함께 고려했을 때, 대전 빵덕후라면 한 번쯤 들러보시는 것을 추천드립니다."
                )
            else:
                if menu_keywords:
                    lines.append(
                        "   리뷰상으로 해당 메뉴와 디저트 전반에 대한 만족도가 높아, "
                        "요청하신 메뉴/취향 위주로 드시기에 잘 맞는 매장입니다."
                    )
                else:
                    lines.append(
                        "   전반적인 리뷰 키워드와 평점을 고려했을 때, "
                        "디저트/빵 자체에 대한 만족도가 높은 편이라 무난하게 방문하기 좋은 선택지입니다."
                    )

            lines.append("")

        lines.append(
            "💡 다른 빵 종류나 맛/식감, 웨이팅 조건, 방문 시간/기간, 동네/역 이름을 바꿔서 다시 찾아보고 싶으시면 편하게 말씀해 주세요."
        )

        return "\n".join(lines)

    # ==============================
    #  인터랙티브 모드
    # ==============================

    def interactive(self):
        print("============================================================")
        print("💬 빵집 추천 전문가와 대화하기")
        print("   (위치 + 리뷰빈도 + 영업시간 + 라스트오더 + 빵지순례 코스 + 벡터DB + Upstage LLM)")
        print("============================================================\n")
        print("안녕하세요! 30년 제빵 경력의 빵집 전문가입니다.")
        print("원하시는 빵 종류, 맛/식감, 분위기, 동네/역 이름, 여행 기간, 방문 시간 등을 자유롭게 말씀해 주세요.")
        print("예)")
        print("  - '대전역 근처 휘낭시에 맛집 추천해줘'")
        print("  - '2025.12.25 ~ 2025.12.26 21:00까지 대전 대표 빵집 빵지순례 코스 추천해줘'\n")
        print("(종료: quit / exit / 종료)\n")

        while True:
            q = input("🤔 질문: ").strip()
            if q.lower() in ["quit", "exit"] or q in ["종료"]:
                print("종료합니다.")
                break
            if not q:
                continue
            answer = self.answer_query(q)
            print()
            print(answer)
            print()


def _safe_get_rating(bakery: Dict[str, Any]) -> float:
    rating_info = bakery.get("rating") or {}
    raw = rating_info.get("naver_rate") or rating_info.get("kakao_rate")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except Exception:
        try:
            return float(str(raw).replace(",", ""))
        except Exception:
            return 0.0


if __name__ == "__main__":
    rag = BakeryExpertRAG()
    rag.interactive()
