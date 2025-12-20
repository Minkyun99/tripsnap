# bakery_rag_chatbot.py

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

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
    KOREAN_WEEKDAY_MAP,
)
from ranking_module import (
    build_review_stats_cache,
    compute_popularity_score,
    detect_flagship_tour_intent,
    extract_menu_keywords,
    generate_search_queries,
)
from ranking_utils import rank_bakeries

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class BakeryExpertRAG:
    def __init__(
        self,
        dessert_path: str = "dessert_en.json",
        base_keywords_path: str = "base_keywords.json",
        vectordb_path: str = "./bakery_vectordb_tuned",
    ):
        print("============================================================")
        print("🍞 빵집 추천 전문가 RAG 시스템 (영업시간/동선/대기시간 반영)")
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
            f"📚 base_keywords.json 로드 완료: "
            f"메뉴 {len(self.base_keywords.get('menu', []))}개 / "
            f"맛 {len(self.base_keywords.get('taste', []))}개 / "
            f"식감 {len(self.base_keywords.get('texture', []))}개 / "
            f"토핑 {len(self.base_keywords.get('topping', []))}개 / "
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
            f"📊 리뷰 키워드 통계 캐시 완료: "
            f"{len(self.review_stats_cache)}개 매장에서 키워드 등장"
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

        # ---------- LLM (선택: 재랭킹/지식 모드) ----------
        self.llm_client = None
        api_key = os.getenv("UPSTAGE_API_KEY", "up_eF6eMmmYAQTpSHqAaRNSJ5wJ9Sm1B").strip()
        if api_key and OpenAI is not None:
            try:
                self.llm_client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.upstage.ai/v1",
                )
                self.llm_rerank_model = "solar-mini-250422"
                self.llm_knowledge_model = "solar-pro-2"
                print("🧠 Upstage LLM 클라이언트 초기화 완료 (재랭킹/지식 모드)")
            except Exception as e:
                print(f"⚠️ Upstage LLM 클라이언트 초기화 실패: {e}")
        else:
            print("⚠️ UPSTAGE_API_KEY 미설정 또는 openai 패키지 미설치로 LLM 재랭킹 비활성화")

        print("✅ 시스템 초기화 완료!\n")

        # 플래그십/유명 리스트 (현재 미사용)
        self.known_flagship_names: List[str] = []

        # 빵 구매에 걸리는 평균 시간 (분) – 코스 타임라인 계산용
        self.avg_purchase_minutes: float = 15.0

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
    #  (선택) LLM 재랭킹
    # ==============================

    def _rerank_with_llm(
        self,
        user_query: str,
        ranked: List[Tuple[Dict[str, Any], float]],
        max_items: int = 10,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Upstage solar-mini-250422로 상위 후보를 한 번 더 재정렬한다.
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
            """
            당신은 '빵집 추천 전문가'이자 30년 경력의 제과·제빵 전문가입니다.

            당신에게는 다음과 같은 입력이 주어집니다.

            1) 사용자 질문 (user_query)
            2) 시스템이 1차 필터링 및 점수 계산을 마친 빵집 후보 리스트 (candidates)

            당신의 역할은:
            - 사용자의 메뉴/맛/식감/날짜/시간/이동수단 의도를 해석하고,
            - candidates 내에서만 순서를 재조정하며,
            - 메뉴 언급 강도, 맛/식감 키워드, 평점/리뷰수, 카페/커피 비중, 브랜드 중복 등을 고려해
              사용자 의도에 더 잘 맞게 재정렬하는 것입니다.

            존재하지 않는 매장을 새로 만들지 말고, 항상 candidates 안에서만 선택/재배치 하십시오.
            한국어로 자연스럽게, 전문적인 어조로 응답하되, 여기서는 순서만 반환합니다.
        """
        )

        user_prompt = (
            f"질문: {user_query}\n\n"
            "후보 빵집 목록:\n" + "\n".join(items_desc) + "\n\n"
            "질문과 가장 잘 맞는 순서대로 번호만 나열해 주세요. 예: 3,1,2,5,4"
        )

        try:
            resp = self.llm_client.chat.completions.create(
                model=self.llm_rerank_model,
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

        tail = ranked[len(top_slice) :]
        return new_top + tail

    # ==============================
    #  이동 수단/동선 + "지금" 인식
    # ==============================

    def _infer_travel_mode(self, query: str) -> str:
        """
        질의에서 이동 수단(도보/대중교통/자차)을 단순 추론.
        기본값은 '대중교통(transit)'.
        """
        q = query.lower()

        if any(k in query for k in ["도보", "걸어서", "걷기", "걷고"]):
            return "walk"
        if any(k in query for k in ["대중교통", "버스", "지하철", "전철"]):
            return "transit"
        if any(k in query for k in ["자차", "차로", "운전", "드라이브", "자가용", "렌트카", "렌터카"]):
            return "car"

        if "on foot" in q or "walk" in q:
            return "walk"
        if any(k in q for k in ["subway", "metro", "bus", "public transit"]):
            return "transit"
        if any(k in q for k in ["by car", "drive", "driving"]):
            return "car"

        return "transit"

    def _max_leg_distance_km(self, travel_mode: str) -> float:
        """
        이동 수단별 최대 이동 시간 제약을 km로 변환.
        - 도보: 20분, 4km/h → 약 1.3km
        - 대중교통: 30분, 20km/h → 약 10km
        - 자차: 30분, 30km/h → 약 15km
        """
        if travel_mode == "walk":
            speed_kmh = 4.0
            max_min = 20
        elif travel_mode == "car":
            speed_kmh = 30.0
            max_min = 30
        else:  # transit
            speed_kmh = 20.0
            max_min = 30
        return speed_kmh * max_min / 60.0

    def _estimate_travel_time_minutes(self, dist_km: float, travel_mode: str) -> float:
        if dist_km <= 0:
            return 0.0
        if travel_mode == "walk":
            speed_kmh = 4.0
        elif travel_mode == "car":
            speed_kmh = 30.0
        else:  # transit
            speed_kmh = 20.0
        return dist_km / speed_kmh * 60.0

    def _has_now_intent(self, query: str) -> bool:
        """
        '지금', '바로', '당장' 등의 표현이 있어
        '현재 시점 기준으로 가기 좋은 빵집' 의도로 보이는지 판별.
        """
        text = query.replace(" ", "")
        keywords = ["지금", "바로", "당장", "지금바로", "바로가", "지금갈", "지금당장", "현재"]
        return any(k in text for k in keywords)

    def _mode_label(self, travel_mode: str) -> str:
        """
        이동 수단 코드 → 한국어 라벨
        """
        return {
            "walk": "도보",
            "transit": "대중교통",
            "car": "자차",
        }.get(travel_mode, "대중교통")

    def _get_leg_display_mode(self, dist_km: float, travel_mode: str) -> str:
        """
        한 구간(leg)의 실제 이동 모드 결정.

        - 사용자가 '대중교통' 또는 '자차'를 선택했더라도,
          직선거리 기준 도보 20분(약 1.3km) 이내면 'walk'로 간주해서
          도보 이동으로 안내한다.
        - 그 외에는 사용자가 선택한 모드를 그대로 쓴다.
        """
        walk_threshold = self._max_leg_distance_km("walk")  # 1.3km (도보 20분 기준)

        if travel_mode in ("transit", "car") and dist_km <= walk_threshold:
            return "walk"
        return travel_mode

    # ==============================
    #  대기시간/오픈시간 헬퍼 (주말/공휴일/리뷰수 가중)
    # ==============================

    def _is_public_holiday(self, date_obj) -> bool:
        """
        간단한 양력 공휴일만 반영.
        (설/추석 등 음력 공휴일은 여기에서 제외)
        """
        fixed_holidays = {
            (1, 1),   # 신정
            (3, 1),   # 3.1절
            (5, 5),   # 어린이날
            (6, 6),   # 현충일
            (8, 15),  # 광복절
            (10, 3),  # 개천절
            (10, 9),  # 한글날
            (12, 25), # 크리스마스
        }
        return (date_obj.month, date_obj.day) in fixed_holidays

    def _get_expected_wait_minutes(
        self,
        bakery: Dict[str, Any],
        constraint: DateTimeConstraint,
    ) -> float:
        """
        dessert_en.json의 waiting_prediction을 사용해
        평균 예상 대기시간(분)을 추정한 뒤,
        - 주말(토/일)에는 약 20% 가중
        - 공휴일(크리스마스 포함)에는 추가로 약 30% 가중
        - 리뷰 수가 많을수록 (500/1000/2000건 이상) 약간씩 추가 가중
        을 적용한다.

        단, waiting_prediction 에서 어떤 형태로든 평균 대기시간을
        얻지 못하는 경우(=0분인 경우)에는 가중을 적용하지 않는다.
        """
        wp = bakery.get("waiting_prediction") or {}
        preds = wp.get("predictions") or {}
        overall = wp.get("overall_stats") or {}

        name = bakery.get("name") or bakery.get("slug_en") or ""

        ref_date: Optional[datetime.date] = None
        ref_time: Optional[datetime.time] = None

        # 실제 날짜/시간 정보가 있는 경우
        if constraint.has_date_range and constraint.start_date:
            ref_date = constraint.start_date
            ref_time = constraint.start_time or constraint.end_time
        # '지금/바로' 기반 질의인 경우 – 오늘 날짜/시간 기준
        elif constraint.use_now_if_missing:
            now = datetime.now()
            ref_date = now.date()
            ref_time = now.time()

        weekday_name: Optional[str] = None
        if ref_date is not None:
            wd_idx = ref_date.weekday()
            weekday_name = KOREAN_WEEKDAY_MAP.get(wd_idx)

        time_band: Optional[str] = None
        if ref_time is not None:
            h = ref_time.hour
            if 10 <= h < 15:
                time_band = "lunch"
            elif 17 <= h < 21:
                time_band = "dinner"

        base_wait: float = 0.0

        # 1) 가능한 경우: 요일 + 시간대별 예측
        if weekday_name and weekday_name in preds:
            day_pred = preds[weekday_name] or {}
            by_time = day_pred.get("by_time") or {}
            if time_band and time_band in by_time:
                band = by_time[time_band] or {}
                if "predicted_wait_minutes" in band:
                    try:
                        base_wait = float(band["predicted_wait_minutes"])
                    except Exception:
                        base_wait = 0.0
            # 요일 전체 예측
            if base_wait <= 0 and "predicted_wait_minutes" in day_pred:
                try:
                    base_wait = float(day_pred["predicted_wait_minutes"])
                except Exception:
                    base_wait = 0.0

        # 2) overall 평균
        if base_wait <= 0 and "average_minutes" in overall:
            try:
                base_wait = float(overall["average_minutes"])
            except Exception:
                base_wait = 0.0

        # 대기시간 정보를 전혀 얻지 못한 경우, 가중치 없이 0으로 반환
        if base_wait <= 0:
            return 0.0

        factor = 1.0

        # (1) 주말/공휴일 가중 – 실제 날짜 정보가 있는 경우에만
        if ref_date is not None:
            weekday_idx = ref_date.weekday()  # 0=월, 5=토, 6=일
            if weekday_idx >= 5:   # 토/일
                factor *= 1.2
            if self._is_public_holiday(ref_date):
                factor *= 1.3

        # (2) 리뷰 수가 많을수록 인기 매장으로 보고 추가 가중
        total_reviews, _ = self.review_stats_cache.get(name, (0, {}))
        if total_reviews >= 2000:
            factor *= 1.3
        elif total_reviews >= 1000:
            factor *= 1.2
        elif total_reviews >= 500:
            factor *= 1.1

        return base_wait * factor

    def _get_earliest_open_minutes(self, bakery: Dict[str, Any]) -> Optional[int]:
        """
        business_hours_index 에서 '가장 이른 오픈 시간'을 분 단위로 추출.
        (날짜 정보가 없이, 하루 코스를 짤 때 사용)
        """
        name = bakery.get("name") or bakery.get("slug_en") or ""
        if not name:
            return None
        weekly = self.business_hours_index.get(name)
        if not weekly:
            return None

        earliest: Optional[int] = None
        for wd in range(7):
            day_info = weekly.get(wd)
            if not day_info:
                continue
            open_t = day_info.get("open")
            if not open_t:
                continue
            minutes = open_t.hour * 60 + open_t.minute
            if earliest is None or minutes < earliest:
                earliest = minutes

        return earliest

    # ==============================
    #  동선 최적화 (타임라인 반영)
    # ==============================

    def _order_bakeries_by_route(
        self,
        ranked: List[Tuple[Dict[str, Any], float]],
        loc_filter: LocationFilter,
        travel_mode: str,
        constraint: DateTimeConstraint,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        1차 랭킹된 리스트를 이동 동선/이동시간/대기시간/오픈시간을 고려해 순서 재구성.

        - '지금/바로' 등 현재 시점 기반 질문:
            → 단순히 구간별 이동시간 + (대략적인) 평균 웨이팅 최소가 되도록 Greedy
        - 날짜/시간이 전혀 없고, '지금' 언급도 없는 일반 질문:
            → 각 매장의 '가장 이른 오픈 시간'을 기준으로
              하루 코스를 짤 때 사용
        """
        if not ranked:
            return ranked

        max_leg_km = self._max_leg_distance_km(travel_mode)

        def _get_coord(b: Dict[str, Any]) -> Optional[Tuple[float, float]]:
            try:
                lat = float(b.get("latitude", 0) or 0)
                lon = float(b.get("longitude", 0) or 0)
            except Exception:
                return None
            if lat == 0 and lon == 0:
                return None
            return lat, lon

        items = []
        for idx, (b, score) in enumerate(ranked):
            items.append(
                {
                    "bakery": b,
                    "score": score,
                    "coord": _get_coord(b),
                    "orig_idx": idx,
                    "earliest_open_min": self._get_earliest_open_minutes(b),
                }
            )

        # 현재 시점 기반 질의인지 여부
        is_now_mode = constraint.use_now_if_missing

        # 타임라인 모드:
        # - 날짜 범위 없음
        # - 시작/종료 시간 없음
        # - use_now_if_missing=False (→ '지금' 의도가 아님)
        is_timeline_mode = (
            not constraint.has_date_range
            and constraint.start_time is None
            and constraint.end_time is None
            and not constraint.use_now_if_missing
        )

        # 출발 기준 좌표 (point 기반 위치 필터일 때)
        origin_coord: Optional[Tuple[float, float]] = None
        if (
            isinstance(loc_filter, LocationFilter)
            and loc_filter.kind == "point"
            and loc_filter.lat is not None
            and loc_filter.lon is not None
        ):
            origin_coord = (loc_filter.lat, loc_filter.lon)

        # ---------- 시작 매장 선택 ----------
        start_item: Optional[Dict[str, Any]] = None

        if is_timeline_mode:
            # 하루 코스: "가장 이른 오픈 시간"을 가진 매장을 출발점으로
            best_item = None
            best_open = None
            for it in items:
                eo = it["earliest_open_min"]
                if eo is None:
                    continue
                if best_open is None or eo < best_open:
                    best_open = eo
                    best_item = it
            start_item = best_item

        if start_item is None:
            # 일반 모드: 출발지가 있으면 "가까운" 매장 선택, 없으면 그냥 1등
            if origin_coord is not None:
                best = None
                best_dist = float("inf")
                for it in items:
                    if it["coord"] is None:
                        continue
                    dist = haversine(
                        origin_coord[0],
                        origin_coord[1],
                        it["coord"][0],
                        it["coord"][1],
                    )
                    if dist < best_dist:
                        best = it
                        best_dist = dist
                start_item = best
            else:
                for it in items:
                    if it["coord"] is not None:
                        start_item = it
                        break

        if start_item is None:
            # 좌표 정보 거의 없으면 경로 최적화 불가 → 기존 순서 유지
            return ranked

        route: List[Dict[str, Any]] = []
        used = set()

        route.append(start_item)
        used.add(start_item["orig_idx"])

        # 타임라인 현재 시각(분) – timeline 모드에서만 사용
        current_time_min: Optional[float] = None
        if is_timeline_mode:
            eo = start_item.get("earliest_open_min")
            current_time_min = float(eo if eo is not None else 600.0)  # 기본 10:00

        while len(used) < len(items):
            last = route[-1]
            last_coord = last["coord"]
            if last_coord is None:
                break

            best_next = None
            best_cost = float("inf")

            for it in items:
                if it["orig_idx"] in used:
                    continue
                coord = it["coord"]
                if coord is None:
                    continue

                dist_km = haversine(
                    last_coord[0],
                    last_coord[1],
                    coord[0],
                    coord[1],
                )
                # 구간 최대 이동 거리 초과 → 제외
                if dist_km > max_leg_km:
                    continue

                # ✅ 실제 이동 모드(도보/대중교통/자차)를 거리 기반으로 다시 결정
                leg_mode = self._get_leg_display_mode(dist_km, travel_mode)
                travel_min = self._estimate_travel_time_minutes(dist_km, leg_mode)

                # 여기서는 날짜/주말/공휴일 가중 없이 "대략적인 평균값"만 사용하기 위해
                # use_now_if_missing=False 로 넘긴다.
                approx_wait = self._get_expected_wait_minutes(
                    it["bakery"],
                    DateTimeConstraint(
                        has_date_range=False,
                        start_date=None,
                        end_date=None,
                        start_time=None,
                        end_time=None,
                        use_now_if_missing=False,
                    ),
                )

                if is_timeline_mode and current_time_min is not None:
                    eo = it["earliest_open_min"]
                    open_min = float(eo if eo is not None else 600.0)
                    arrival_min = current_time_min + travel_min
                    open_wait = max(0.0, open_min - arrival_min)
                    cost = travel_min + open_wait + approx_wait + self.avg_purchase_minutes
                else:
                    cost = travel_min + approx_wait

                if cost < best_cost:
                    best_cost = cost
                    best_next = it

            if best_next is None:
                break

            # 타임라인 모드일 때는 current_time_min 업데이트
            if is_timeline_mode and current_time_min is not None:
                eo = best_next.get("earliest_open_min")
                open_min = float(eo if eo is not None else 600.0)
                dist_km = haversine(
                    last_coord[0],
                    last_coord[1],
                    best_next["coord"][0],
                    best_next["coord"][1],
                )
                leg_mode = self._get_leg_display_mode(dist_km, travel_mode)
                travel_min = self._estimate_travel_time_minutes(dist_km, leg_mode)
                arrival_min = current_time_min + travel_min
                open_wait = max(0.0, open_min - arrival_min)
                approx_wait = self._get_expected_wait_minutes(
                    best_next["bakery"],
                    DateTimeConstraint(
                        has_date_range=False,
                        start_date=None,
                        end_date=None,
                        start_time=None,
                        end_time=None,
                        use_now_if_missing=False,
                    ),
                )
                current_time_min = (
                    arrival_min + open_wait + approx_wait + self.avg_purchase_minutes
                )

            route.append(best_next)
            used.add(best_next["orig_idx"])

        remaining = [it for it in items if it["orig_idx"] not in used]
        remaining_sorted = sorted(remaining, key=lambda x: x["orig_idx"])

        final_items = route + remaining_sorted
        return [(it["bakery"], it["score"]) for it in final_items]

    # ==============================
    #  메인 질의 처리
    # ==============================

    def answer_query(self, query: str) -> str:
        print("============================================================")
        print(f"🔍 '{query}'")
        print("============================================================")

        # 0) 질문 타입 판별: 추천 vs 지식 Q&A
        q_type = self._infer_query_type(query)
        if q_type == "knowledge":
            # 빵집 추천이 아니라, 빵/디저트 지식 설명 모드로 처리
            return self._answer_knowledge_query_with_llm(query)

        # 0) 이동 수단 인식
        travel_mode = self._infer_travel_mode(query)
        mode_label = self._mode_label(travel_mode)
        print(f"   🚶 이동 수단 인식: {mode_label} 기준 동선 최적화")

        # 1) 날짜/시간 파싱
        constraint: DateTimeConstraint = parse_date_time_from_query(query)
        now_intent = self._has_now_intent(query)

        # '크리스마스/성탄절' 자연어를 명시 날짜로 인식
        if (
            not constraint.has_date_range
            and any(k in query for k in ["크리스마스", "성탄절"])
        ):
            from datetime import date as _date

            today = datetime.now().date()
            year = today.year
            christmas = _date(year, 12, 25)
            if today > christmas:
                christmas = _date(year + 1, 12, 25)

            constraint.has_date_range = True
            constraint.start_date = christmas
            constraint.end_date = christmas
            # 날짜가 명시됐으므로 '지금 영업 중' 필터는 쓰지 않음
            constraint.use_now_if_missing = False

            print(
                f"   📅 '크리스마스' 언급 감지 → {christmas} 하루 방문으로 인식합니다."
            )

        # '지금/바로' 기반 now 모드 결정
        # - 날짜/시간 언급이 전혀 없을 때만 now 모드 가능
        if (
            not constraint.has_date_range
            and constraint.start_time is None
            and constraint.end_time is None
        ):
            if now_intent:
                constraint.use_now_if_missing = True
                print("   🕒 '지금/바로' 의도 인식 → 현재 시각 기준 '영업 중' 매장만 추천합니다.")
            else:
                constraint.use_now_if_missing = False
                print(
                    "   🕒 명시된 시간/날짜/지금 언급 없음 → 전반적인 영업시간을 기준으로 "
                    "하루 코스를 구성합니다."
                )
        else:
            # 날짜나 시간이 명시된 경우에는 '지금 영업 중' 필터를 사용하지 않음
            if constraint.has_date_range or constraint.start_time or constraint.end_time:
                constraint.use_now_if_missing = False

        # 로그 출력
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
            now = datetime.now()
            print(
                f"   🕒 현재 시각({now.strftime('%Y-%m-%d %H:%M')}) 기준으로 "
                "영업 중인 매장만 추천합니다."
            )

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

        # 4) 빵지순례/대표 코스 의도
        intent_flags = detect_flagship_tour_intent(query, menu_keywords)
        if intent_flags.get("is_flagship_tour"):
            print("   🧭 의도: '대표 빵집' 또는 '빵지순례 코스' 추천 모드")

        # 5) 벡터 검색용 쿼리 생성
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
        final_candidates: List[Dict[str, Any]] = []
        last_close_map: Dict[str, datetime.time] = {}

        # now 필터는 "날짜가 없는 + 지금/바로" 질의에서만 사용
        use_now_filter = constraint.use_now_if_missing and not constraint.has_date_range

        if use_now_filter:
            # '지금/바로' 모드 – 현재 영업 중인 매장만
            now = datetime.now()
            before = len(loc_filtered)
            for b in loc_filtered:
                if is_open_at(b, now, self.business_hours_index):
                    final_candidates.append(b)
            print(
                f"   🕒 현재 영업 중 필터 적용 전 {before}개 → 후 {len(final_candidates)}개"
            )
        else:
            # 날짜/시간 제약이 있다면 그 기간 중 영업하는 매장만,
            # 제약이 없다면 전반적인 영업 패턴 기준으로 필터
            before = len(loc_filtered)
            for b in loc_filtered:
                ok, last_close = is_available_in_period(
                    b, constraint, self.business_hours_index
                )
                if ok:
                    final_candidates.append(b)
                    if constraint.has_date_range and last_close:
                        name = b.get("name") or b.get("slug_en") or ""
                        last_close_map[name] = last_close
            print(
                f"   🕒 방문 기간/시간 필터 적용 전 {before}개 → 후 {len(final_candidates)}개"
            )

        if not final_candidates:
            return (
                "조건에 맞는 영업 중인 빵집을 찾지 못했습니다. "
                "날짜/시간 또는 지역 범위를 조금 넓혀서 다시 요청해 주세요."
            )

        # 9) 메뉴/리뷰/의도 기반 스코어링 + 브랜드 중복 제어
        ranked = rank_bakeries(
            candidates=final_candidates,
            menu_keywords=menu_keywords,
            intent_flags=intent_flags,
            review_stats_cache=self.review_stats_cache,
            known_flagship_names=self.known_flagship_names,
            top_k=10,
        )

        # 10) (선택) LLM 재랭킹
        try:
            ranked = self._rerank_with_llm(query, ranked)
        except Exception as e:
            print(f"⚠️ LLM 재랭킹 중 오류 발생, 내부 스코어 순서 사용: {e}")

        # 11) 이동 수단/동선을 고려한 순서 재구성
        ranked = self._order_bakeries_by_route(
            ranked, loc_filter, travel_mode, constraint
        )

        # 도보의 경우: 출발지 기준 20분(1.3km) 초과 매장은 제외
        if (
            travel_mode == "walk"
            and isinstance(loc_filter, LocationFilter)
            and loc_filter.kind == "point"
            and loc_filter.lat is not None
            and loc_filter.lon is not None
        ):
            walk_threshold = self._max_leg_distance_km("walk")
            origin_lat = loc_filter.lat
            origin_lon = loc_filter.lon
            filtered_ranked = []
            for bakery, score in ranked:
                try:
                    lat_val = float(bakery.get("latitude", 0) or 0)
                    lon_val = float(bakery.get("longitude", 0) or 0)
                except Exception:
                    continue
                if not lat_val or not lon_val:
                    continue
                dist0 = haversine(origin_lat, origin_lon, lat_val, lon_val)
                if dist0 <= walk_threshold:
                    filtered_ranked.append((bakery, score))
            ranked = filtered_ranked

        top_n = ranked[:10]

        if not top_n:
            return (
                "도보 이동 기준 20분 이내에서 추천할 수 있는 빵집을 찾지 못했습니다. "
                "조금 더 넓은 범위(대중교통/자차 이동)로 다시 요청해 주세요."
            )

        # 12) 답변 구성
        lines: List[str] = []
        lines.append("안녕하세요, 30년간 제빵 현장에서 일해온 빵집 전문가입니다.\n")

        if constraint.use_now_if_missing:
            lines.append(
                f"요청하신 조건에 맞춰, 지금({datetime.now().strftime('%Y-%m-%d %H:%M')}) "
                f"기준으로 바로 가기 좋은 빵집들을 ({mode_label} 이동 기준 동선 포함) 추천드립니다.\n"
            )
        elif constraint.has_date_range or constraint.start_time or constraint.end_time:
            lines.append(
                f"요청하신 방문 기간/시간을 고려해서 ({mode_label} 이동 기준 동선 포함) "
                "아래와 같이 코스를 구성했습니다.\n"
            )
        else:
            lines.append(
                f"명시된 시간은 없으셔서, 전반적인 영업시간(오픈 시간)과 이동/대기시간을 고려해 "
                f"하루 동안 돌기 좋은 코스로 ({mode_label} 기준) 추천드립니다.\n"
            )

        origin_lat: Optional[float] = None
        origin_lon: Optional[float] = None
        if (
            isinstance(loc_filter, LocationFilter)
            and loc_filter.kind == "point"
            and loc_filter.lat is not None
            and loc_filter.lon is not None
        ):
            origin_lat = loc_filter.lat
            origin_lon = loc_filter.lon

        prev_lat = origin_lat
        prev_lon = origin_lon

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

            lat_val = None
            lon_val = None
            try:
                lat_val = float(bakery.get("latitude", 0) or 0)
                lon_val = float(bakery.get("longitude", 0) or 0)
            except Exception:
                lat_val = lon_val = None

            if lat_val and lon_val:
                # 출발지 → 첫 매장
                if origin_lat is not None and origin_lon is not None and idx == 1:
                    dist0 = haversine(origin_lat, origin_lon, lat_val, lon_val)
                    leg_mode0 = self._get_leg_display_mode(dist0, travel_mode)
                    leg_label0 = self._mode_label(leg_mode0)
                    travel0 = self._estimate_travel_time_minutes(dist0, leg_mode0)
                    lines.append(
                        f"🚩 출발지 → 이 매장까지: 약 {dist0:.2f}km / 예상 {travel0:.0f}분 ({leg_label0})"
                    )
                # 이전 추천 매장 → 현재 매장
                elif prev_lat is not None and prev_lon is not None:
                    dist_p = haversine(prev_lat, prev_lon, lat_val, lon_val)
                    leg_mode_p = self._get_leg_display_mode(dist_p, travel_mode)
                    leg_label_p = self._mode_label(leg_mode_p)
                    travel_p = self._estimate_travel_time_minutes(dist_p, leg_mode_p)
                    lines.append(
                        f"➡ 이전 추천 매장 → 여기까지: 약 {dist_p:.2f}km / 예상 {travel_p:.0f}분 ({leg_label_p})"
                    )

            if lat_val and lon_val:
                prev_lat, prev_lon = lat_val, lon_val

            # 종료 시각 + 라스트오더 안내 (날짜/시간 질의일 때만)
            if constraint.has_date_range and constraint.end_date and constraint.end_time:
                if name in last_close_map:
                    last_t = last_close_map[name]
                    if last_t < constraint.end_time:
                        lines.append(
                            f"⚠️ 참고: {constraint.end_date} 기준 라스트오더/마감 시간은 "
                            f"{last_t.strftime('%H:%M')}라, 요청하신 종료 시각"
                            f"({constraint.end_time.strftime('%H:%M')})보다 조금 이른 편입니다."
                        )

            wait_min = self._get_expected_wait_minutes(bakery, constraint)
            if wait_min > 0.5:
                lines.append(f"⏱ 평균 예상 대기시간(주말/공휴일/인기도 반영): 약 {wait_min:.0f}분 기준")

            rk = bakery.get("review_keywords") or []
            top_rk = rk[:5]
            if top_rk:
                desc = []
                for r in top_rk:
                    kw = r.get("keyword")
                    c = r.get("count")
                    desc.append(f"\"{kw}\" {c}회")
                lines.append("\n✨ 이 집의 특징(리뷰 키워드 상위):")
                lines.append("   - " + ", ".join(desc))

            kd = bakery.get("keyword_details") or {}
            final_kw = kd.get("final_keywords") or []
            if final_kw:
                show = final_kw[:8]
                lines.append("\n   - 대표 메뉴/키워드: " + ", ".join(show))

            lines.append("\n👨‍🍳 전문가 코멘트:")
            if intent_flags.get("is_flagship_tour"):
                lines.append(
                    "   일정 수준 이상의 리뷰 수와 인기도를 가진 매장으로, "
                    "빵지순례 코스로 묶어서 방문하기 좋은 집입니다."
                )
            else:
                if menu_keywords:
                    lines.append(
                        "   리뷰상으로 요청하신 메뉴/취향과의 궁합이 좋아, "
                        "원하시는 빵/디저트를 중심으로 즐기기에 적합한 매장입니다."
                    )
                else:
                    lines.append(
                        "   전체적인 평점과 리뷰 키워드를 봤을 때, "
                        "빵과 디저트 자체 만족도가 높아 무난히 방문하시기 좋은 곳입니다."
                    )

            lines.append("")

        lines.append(
            "💡 다른 빵 종류나 맛/식감, 웨이팅 조건, 방문 시간/기간, 동네/역 이름, "
            "이동 수단(도보/대중교통/자차)을 바꿔서 다시 찾아보고 싶으시면 편하게 말씀해 주세요."
        )

        return "\n".join(lines)

    # ==============================
    #  인터랙티브 모드
    # ==============================

    def interactive(self):
        print("============================================================")
        print("💬 빵집 추천 전문가와 대화하기")
        print("   (위치 + 리뷰빈도 + 영업시간 + 동선 + 대기시간 + 벡터DB)")
        print("============================================================\n")
        print("안녕하세요! 30년 제빵 경력의 빵집 전문가입니다.")
        print("원하시는 빵 종류, 맛/식감, 분위기, 동네/역 이름, 여행 기간, 방문 시간, 이동 수단 등을 자유롭게 말씀해 주세요.")
        print("예)")
        print("  - '대전역 근처 휘낭시에 맛집 추천해줘'")
        print("  - '지금 바로 대전역 근처에서 갈 수 있는 빵집 추천해줘'")
        print("  - '시간 상관 없이 대전 대표 빵집 하루 코스 짜줘'")
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

    # =======================================================
    # 빵 관련 지식 모드
    # =======================================================

    def _answer_knowledge_query_with_llm(self, query: str) -> str:
        """
        빵/디저트에 대한 이론·역사·종류·제법 질문에 대해
        LLM이 제과·제빵 전문가로 답변하는 경로.
        dessert_en.json 데이터나 랭킹 모듈은 사용하지 않는다.
        """
        if self.llm_client is None:
            # LLM 미설정 시 안전 메시지
            return (
                "현재 빵 이론 설명용 LLM이 설정되어 있지 않습니다. "
                "환경 설정 후 다시 시도해 주세요."
            )

        system_prompt = (
            "당신은 30년 경력의 제과·제빵 전문가이자 빵/디저트 역사 연구자입니다. "
            "사용자는 빵집 추천이 아니라, 빵과 디저트 자체에 대한 지식과 이해를 원합니다. "
            "항상 다음 원칙을 지키세요.\n"
            "1) 질문이 '어떤 종류가 있나요?', '차이점이 뭐예요?', '왜 이렇게 만드나요?' 같은 형태라면, "
            "빵/디저트의 종류, 스타일, 유래, 역사, 제법(반죽/발효/굽기) 등을 체계적으로 설명합니다.\n"
            "2) 포르투갈식 에그타르트, 홍콩식 에그타르트, 파이 도우 vs 쿠키 도우, "
            "버터 양이나 설탕 비율, 반죽 접기 횟수 등 기술적인 디테일도 적절히 포함합니다.\n"
            "3) 사용자가 특정 지역(예: 대전, 유성구)을 말하더라도, "
            "지식 질문일 때는 굳이 매장 추천을 하지 않아도 됩니다. "
            "필요하다면 '이런 스타일의 가게를 찾아보라' 정도의 일반적인 힌트만 주세요.\n"
            "4) 한국어로, 과장되지 않지만 전문적인 어조로 답변합니다.\n"
            "5) 너무 추상적으로만 말하지 말고, 실제 제과 현장에서 쓰는 용어와 예시를 적절히 섞어 주세요.\n"
            "6) 사용자가 원치 않는 한, 이 모드에서는 특정 매장 이름을 임의로 만들어 추천하지 않습니다."
        )

        user_prompt = (
            f"사용자의 질문은 다음과 같습니다:\n\n"
            f"\"{query}\"\n\n"
            "이 질문에 대해 제과·제빵 전문가 입장에서 친절하고 깊이 있게 설명해 주세요.\n"
            "가능하다면 다음 구조를 따라 주세요.\n"
            "1) 한 줄 요약\n"
            "2) 핵심 개념 정리 (종류, 특징, 차이점 등)\n"
            "3) 제과·제빵 실무 관점의 팁 또는 예시\n"
            "4) 관련해서 더 알아보면 좋은 키워드 2~3개 제안\n"
        )

        try:
            resp = self.llm_client.chat.completions.create(
                model=self.llm_knowledge_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.35,
                max_tokens=1200,
            )
            answer = resp.choices[0].message.content.strip()
            print("🧠 지식 Q&A LLM 응답 생성 성공 (solar-pro-2)")
            return answer
        except Exception as e:
            print(f"⚠️ 지식 Q&A LLM 호출 실패: {e}")
            return (
                "제과·제빵 지식 설명용 LLM 호출에 문제가 발생했습니다. "
                "잠시 후 다시 시도해 주세요."
            )

    def _infer_query_type(self, query: str) -> str:
        """
        질의가 '추천/코스' 인지, '지식/설명' 인지 구분.
        - return "recommend" 또는 "knowledge"
        """
        q = query.strip()

        # 1) 추천/코스 의도 키워드
        recommend_keywords = [
            "추천해줘", "추천해 주세요", "추천해주세요",
            "맛집", "빵집 추천", "코스", "빵지순례",
            "어디 갈까", "어디가 좋을까", "어디가 좋나요",
            "가고 싶은", "갈 만한", "가면 좋은",
        ]
        for kw in recommend_keywords:
            if kw in q:
                return "recommend"

        # 2) 정보/지식 의도 키워드 (설명, 종류, 차이점 등)
        knowledge_keywords = [
            "어떤 종류", "종류가 있나요", "종류는?", "종류 알려줘",
            "차이점", "차이가 뭐야", "차이가 뭔가요",
            "유래", "역사", "기원", "특징", "설명해줘",
            "어떻게 만드는", "레시피", "만드는 법",
        ]
        for kw in knowledge_keywords:
            if kw in q:
                return "knowledge"

        # 3) 질문 끝이 ? 이면서 '맛집/추천/코스/빵지순례'가 없으면
        #    정보 질문일 가능성이 더 높다고 보고 knowledge 로 처리
        if "?" in q and "맛집" not in q and "추천" not in q and "코스" not in q:
            return "knowledge"

        # 기본값: 추천 모드
        return "recommend"


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
