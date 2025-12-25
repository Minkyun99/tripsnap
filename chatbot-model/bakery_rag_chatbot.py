import json
import os
import math
from datetime import datetime, time
from typing import Any, Dict, List, Tuple, Optional

import chromadb

from schemas import DateTimeConstraint, LocationFilter, TransportMode

from location_module import (
    annotate_admin_areas,
    extract_location_from_query,
    filter_bakeries_by_location,
    detect_transport_mode,
    haversine,
    find_nearest_subway_station,
    build_kakao_place_url,
    build_kakao_route_url,
)

from time_module import (
    build_business_hours_index,
    is_available_in_period,
    is_open_at,
    parse_date_time_from_query,
    KOREAN_WEEKDAY_MAP,
    DateTimeParser,
)
from ranking_module import (
    build_review_stats_cache,
    compute_popularity_score,
    detect_flagship_tour_intent,
    extract_menu_keywords,
    generate_search_queries,
    rank_bakeries,
)
from ranking_utils import (
    haversine_distance_km,
    estimate_walk_time_minutes,
    estimate_transit_time_minutes,
    _safe_rating,
)


try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import requests
except ImportError:
    requests = None


# ==================================================
#  대전 1호선 역 순서 (동선 최적화용 메타데이터)
# ==================================================

SUBWAY_LINE1_SEQUENCE = [
    "판암",
    "신흥",
    "대동",
    "대전",
    "중앙로",
    "중구청",
    "서대전네거리",
    "오룡",
    "용문",
    "탄방",
    "시청",
    "정부청사",
    "갈마",
    "월평",
    "갑천",
    "유성온천",
    "구암",
    "현충원",
    "월드컵경기장",
    "노은",
    "지족",
    "반석",
]

SUBWAY_LINE1_INDEX = {name: idx for idx, name in enumerate(SUBWAY_LINE1_SEQUENCE)}


def _normalize_station_name_for_line(name: str) -> str:
    if not name:
        return ""
    return name.split("(")[0].strip()


def get_subway_station_order_index(station_name: str) -> int:
    base = _normalize_station_name_for_line(station_name)
    return SUBWAY_LINE1_INDEX.get(base, -1)


def infer_line_direction(visited_stations):
    indices = [
        get_subway_station_order_index(s)
        for s in visited_stations
        if get_subway_station_order_index(s) >= 0
    ]
    if len(indices) < 2:
        return 0
    if indices[-1] > indices[0]:
        return 1
    if indices[-1] < indices[0]:
        return -1
    return 0


# ==================================================
#  Upstage Embedding 클라이언트
#   - sentence-transformers / torch 제거용
#   - 문서/쿼리 임베딩을 Upstage Embedding API로 생성
# ==================================================

class UpstageEmbeddingClient:
    """
    Upstage(https://api.upstage.ai/v1) Embedding API 래퍼.

    - query:  solar-embedding-1-large-query
    - passage: solar-embedding-1-large-passage

    UPSTAGE_API_KEY 환경변수를 사용합니다.
    """

    def __init__(self, api_key: Optional[str] = None):
        if OpenAI is None:
            raise RuntimeError(
                "openai 패키지가 필요합니다. "
                "pip install openai 후 사용해 주세요."
            )

        key = (api_key or os.getenv("UPSTAGE_API_KEY", "")).strip()
        if not key:
            raise RuntimeError(
                "UPSTAGE_API_KEY 가 설정되어 있지 않습니다. "
                "Upstage 콘솔에서 API 키를 발급 후 환경변수에 설정해 주세요."
            )

        # Upstage는 OpenAI 호환 API이므로 base_url만 바꿔서 사용
        self.client = OpenAI(
            api_key=key,
            base_url="https://api.upstage.ai/v1",
        )

        # 필요 시 환경변수로 오버라이드 가능
        self.query_model = os.getenv(
            "UPSTAGE_EMBED_QUERY_MODEL",
            "solar-embedding-1-large-query",
        )
        self.doc_model = os.getenv(
            "UPSTAGE_EMBED_DOC_MODEL",
            "solar-embedding-1-large-passage",
        )

    def embed_query(self, text: str) -> List[float]:
        """
        검색 쿼리용 임베딩 (Query 모델 사용)
        """
        if not text:
            text = " "
        resp = self.client.embeddings.create(
            model=self.query_model,
            input=text,
        )
        return resp.data[0].embedding

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        문서(빵집 설명 등)용 임베딩 (Passage 모델 사용)
        - 대량 인덱싱용으로 사용할 수 있음
        """
        if not texts:
            return []
        resp = self.client.embeddings.create(
            model=self.doc_model,
            input=texts,
        )
        return [d.embedding for d in resp.data]


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

        # ---------- Kakao Mobility Navi API 키 ----------
        self.kakao_mobility_api_key = (
            os.getenv("KAKAO_MOBILITY_API_KEY", "d58a0c90acfbefb8a0a651c62c6fbd4c")
            or os.getenv("KAKAO_REST_API_KEY", "d58a0c90acfbefb8a0a651c62c6fbd4c")
        )
        if self.kakao_mobility_api_key and requests is not None:
            print("🚗 Kakao Mobility Navi API 키 감지 – 실제 도로 기준 이동거리/시간을 사용합니다.")
        else:
            print("⚠️ Kakao Mobility Navi API 미사용 – 직선거리 기반 이동시간 추정만 사용합니다.")

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

        # ---------- Upstage Embedding 클라이언트 ----------
        self.embedding_client: Optional[UpstageEmbeddingClient] = None
        if OpenAI is not None:
            try:
                self.embedding_client = UpstageEmbeddingClient()
                print(
                    "🧮 Upstage Embedding 클라이언트 초기화 완료 "
                    "(solar-embedding-1-large-query / passage)"
                )
            except Exception as e:
                print(f"⚠️ Upstage Embedding 초기화 실패: {e}")
        else:
            print("⚠️ openai 패키지 미설치 – Upstage Embedding 사용 불가 (벡터 검색 비활성화)")

        # ---------- 벡터 DB (Chroma, embedding_function 없이 사용) ----------
        print("📦 Chroma 벡터 DB 연결 (기존 인덱스 사용)")
        print(f"💾 벡터 DB 경로: {os.path.abspath(self.vectordb_path)}")
        self.chroma_client = chromadb.PersistentClient(path=self.vectordb_path)
        # embedding_function 을 지정하지 않고, query_embeddings 를 직접 전달
        self.bakery_collection = self.chroma_client.get_or_create_collection(
            name="bakery_collection",
            metadata={"hnsw:space": "cosine"},
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

        # ---------- LLM (재랭킹/지식 모드) ----------
        self.llm_client = None
        api_key = os.getenv("UPSTAGE_API_KEY", "up_eF6eMmmYAQTpSHqAaRNSJ5wJ9Sm1B").strip()
        if api_key and OpenAI is not None:
            try:
                self.llm_client = OpenAI(
                    api_key=api_key,
                    base_url="https://api.upstage.ai/v1",
                )
                self.llm_rerank_model = "solar-mini-250422"
                self.llm_knowledge_model = "solar-mini-250422"
                print("🧠 Upstage LLM 클라이언트 초기화 완료 (재랭킹/지식 모드)")
            except Exception as e:
                print(f"⚠️ Upstage LLM 클라이언트 초기화 실패: {e}")
        else:
            print("⚠️ UPSTAGE_API_KEY 미설정 또는 openai 패키지 미설치로 LLM 재랭킹 비활성화")

        # 시간/날짜 파서
        self.time_parser = DateTimeParser()

        # 빵 구매 평균 체류 시간(분)
        self.avg_purchase_minutes: float = 15.0

        # 도보 코스 최대 이동시간(분) – “도보 20분 룰”
        self.MAX_WALK_MINUTES: float = 20.0

        print("✅ 시스템 초기화 완료!\n")

        # 플래그십/유명 리스트 (현재 미사용)
        self.known_flagship_names: List[str] = []

    # ==============================
    #  벡터 검색 (Upstage 임베딩 사용)
    # ==============================

    def _vector_search_bakeries(
        self,
        queries: List[str],
        top_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        - 기존: SentenceTransformerEmbeddingFunction + query_texts
        - 변경: Upstage Embedding API로 쿼리 임베딩 생성 후 query_embeddings 로 검색
        """
        if self.bakery_collection is None:
            return list(self.bakeries)

        if self.embedding_client is None:
            # 임베딩 사용 불가 시 전체 데이터로 fallback
            print("⚠️ Upstage Embedding 클라이언트 없음 → 전체 데이터 fallback")
            return list(self.bakeries)

        slug_scores: Dict[str, float] = {}

        for q in queries:
            try:
                # 쿼리 문장을 Upstage Query 모델로 임베딩
                q_vec = self.embedding_client.embed_query(q)

                res = self.bakery_collection.query(
                    query_embeddings=[q_vec],
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
                # Chroma 기본은 "distance" = 1 - cosine_sim 또는 유사 metric
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
        max_items: int = 3,
    ) -> List[Tuple[Dict[str, Any], float]]:
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

        system_prompt = """
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

        tail = ranked[len(top_slice):]
        return new_top + tail

    # ==============================
    #  이동 수단/동선 + "지금" 인식
    # ==============================

    def _infer_travel_mode(self, query: str) -> str:
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
        한 구간(매장→다음 매장)당 허용하는 최대 거리(km).
        - walk: 도보 20분 룰을 보수적으로 반영 (약 3km/h 기준 → 1.0km)
        - car / transit: 상대적으로 여유 있게 설정
        """
        if travel_mode == "walk":
            speed_kmh = 3.0
            max_min = self.MAX_WALK_MINUTES
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

    def _prune_far_same_station_bakeries(
        self,
        items: List[Dict[str, Any]],
        max_walk_min: float = 25.0,
    ) -> List[Dict[str, Any]]:
        from collections import defaultdict

        station_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for it in items:
            sname = it.get("station_name")
            if not sname:
                continue
            station_groups[sname].append(it)

        kept: List[Dict[str, Any]] = [it for it in items if not it.get("station_name")]

        for station_name, group in station_groups.items():
            if len(group) <= 1:
                kept.extend(group)
                continue

            sorted_group = sorted(
                group,
                key=lambda x: (x.get("route_score") or x.get("score") or 0.0),
                reverse=True,
            )
            anchor = sorted_group[0]
            kept.append(anchor)

            a_coord = anchor.get("coord")
            if not a_coord:
                kept.extend(sorted_group[1:])
                continue

            ax, ay = a_coord

            for it in sorted_group[1:]:
                coord = it.get("coord")
                if not coord:
                    kept.append(it)
                    continue

                bx, by = coord
                dist_km = haversine_distance_km(ax, ay, bx, by)
                walk_min = estimate_walk_time_minutes(dist_km)

                if walk_min <= max_walk_min:
                    kept.append(it)

        return kept

    def _has_now_intent(self, query: str) -> bool:
        text = query.replace(" ", "")
        keywords = ["지금", "바로", "당장", "지금바로", "바로가", "지금갈", "지금당장", "현재"]
        return any(k in text for k in keywords)

    def _mode_label(self, travel_mode: str) -> str:
        return {
            "walk": "도보",
            "transit": "대중교통",
            "car": "자차",
        }.get(travel_mode, "대중교통")

    def _get_leg_display_mode(self, dist_km: float, travel_mode: str) -> str:
        walk_threshold = self._max_leg_distance_km("walk")
        if travel_mode in ("transit", "car") and dist_km <= walk_threshold:
            return "walk"
        return travel_mode

    # ==============================
    #  Kakao Mobility 길찾기 연동
    # ==============================

    def _call_kakao_mobility_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ) -> Optional[Tuple[float, float]]:
        if not self.kakao_mobility_api_key or requests is None:
            return None
        try:
            url = "https://apis-navi.kakaomobility.com/v1/directions"
            headers = {
                "Authorization": f"KakaoAK {self.kakao_mobility_api_key}",
                "Content-Type": "application/json",
            }
            params = {
                "origin": f"{start_lon},{start_lat}",
                "destination": f"{end_lon},{end_lat}",
                "priority": "RECOMMEND",
            }
            resp = requests.get(url, headers=headers, params=params, timeout=3)
            if resp.status_code != 200:
                print(f"⚠️ Kakao Mobility API 응답 코드: {resp.status_code}")
                return None
            data = resp.json()
            routes = data.get("routes")
            if not routes:
                return None
            summary = routes[0].get("summary", {})
            distance_m = float(summary.get("distance", 0.0))
            duration_s = float(summary.get("duration", 0.0))
            if distance_m <= 0:
                return None
            distance_km = distance_m / 1000.0
            duration_min = duration_s / 60.0 if duration_s > 0 else 0.0
            return distance_km, duration_min
        except Exception as e:
            print(f"⚠️ Kakao Mobility directions 호출 실패: {e}")
            return None

    def _get_leg_distance_and_durations(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ) -> Tuple[float, float, float]:
        kakao_result = self._call_kakao_mobility_route(start_lat, start_lon, end_lat, end_lon)
        if kakao_result is not None:
            distance_km, car_min = kakao_result
            walk_min = distance_km / 3.3 * 60.0 if distance_km > 0 else 0.0
        else:
            distance_km = haversine_distance_km(start_lat, start_lon, end_lat, end_lon)
            walk_min = estimate_walk_time_minutes(distance_km)
            car_min = estimate_transit_time_minutes(distance_km, TransportMode.CAR)

        return distance_km, walk_min, car_min

    # ==============================
    #  대기시간/오픈시간 헬퍼
    # ==============================

    def _is_public_holiday(self, date_obj) -> bool:
        fixed_holidays = {
            (1, 1),
            (3, 1),
            (5, 5),
            (6, 6),
            (8, 15),
            (10, 3),
            (10, 9),
            (12, 25),
        }
        return (date_obj.month, date_obj.day) in fixed_holidays

    def _get_expected_wait_minutes(
        self,
        bakery: Dict[str, Any],
        constraint: DateTimeConstraint,
    ) -> float:
        wp = bakery.get("waiting_prediction") or {}
        preds = wp.get("predictions") or {}
        overall = wp.get("overall_stats") or {}

        ref_date: Optional[datetime.date] = None
        ref_time: Optional[datetime.time] = None

        if constraint.has_date_range and constraint.start_date:
            ref_date = constraint.start_date
            ref_time = constraint.start_time or constraint.end_time
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
            if base_wait <= 0 and "predicted_wait_minutes" in day_pred:
                try:
                    base_wait = float(day_pred["predicted_wait_minutes"])
                except Exception:
                    base_wait = 0.0

        if base_wait <= 0 and "average_minutes" in overall:
            try:
                base_wait = float(overall["average_minutes"])
            except Exception:
                base_wait = 0.0

        if base_wait <= 0:
            return 0.0

        factor = 1.0

        if ref_date is not None:
            weekday_idx = ref_date.weekday()
            if weekday_idx >= 5:
                factor *= 1.2
            if self._is_public_holiday(ref_date):
                factor *= 1.3

        name = bakery.get("name") or bakery.get("slug_en") or ""
        total_reviews, _ = self.review_stats_cache.get(name, (0, {}))
        if total_reviews >= 2000:
            factor *= 1.3
        elif total_reviews >= 1000:
            factor *= 1.2
        elif total_reviews >= 500:
            factor *= 1.1

        return base_wait * factor

    def _get_earliest_open_minutes(self, bakery: Dict[str, Any]) -> Optional[int]:
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

    def _infer_start_minutes(
        self,
        constraint: DateTimeConstraint,
    ) -> Tuple[int, str]:
        if constraint.has_date_range and constraint.start_time is not None:
            h = constraint.start_time.hour
            m = constraint.start_time.minute
            return h * 60 + m, constraint.start_time.strftime("%H:%M")

        if constraint.use_now_if_missing:
            now = datetime.now()
            return now.hour * 60 + now.minute, f"현재 시각({now.strftime('%H:%M')})"

        return 11 * 60, "오전 11:00"

    def _format_minutes_to_hhmm(self, minutes: int) -> str:
        minutes = minutes % (24 * 60)
        h = minutes // 60
        m = minutes % 60
        return f"{h:02d}:{m:02d}"

    # ==============================
    #  동선 최적화 (지하철 노선 기반 + 일반 거리 기반)
    # ==============================

    def _order_bakeries_by_route(
        self,
        ranked: List[Any],
        loc_filter: Optional[LocationFilter],
        travel_mode: str,
        constraint: DateTimeConstraint,
        menu_keywords: List[str],
    ) -> List[Tuple[Dict[str, Any], float]]:
        # 0) 입력 정규화
        norm_ranked: List[Tuple[Dict[str, Any], float]] = []

        for item in ranked:
            bakery = None
            score = 0.0

            if isinstance(item, dict):
                if isinstance(item.get("bakery"), dict):
                    bakery = item["bakery"]
                    score = float(item.get("score", 0.0) or 0.0)
                else:
                    bakery = item
                    score = float(item.get("score", 0.0) or 0.0)
            elif isinstance(item, (tuple, list)):
                if len(item) >= 1 and isinstance(item[0], dict):
                    bakery = item[0]
                    if len(item) >= 2:
                        try:
                            score = float(item[1])
                        except Exception:
                            score = 0.0

            if isinstance(bakery, dict):
                norm_ranked.append((bakery, score))

        if len(norm_ranked) <= 1:
            return norm_ranked

        # 출발 시각
        start_minutes, _ = self._infer_start_minutes(constraint)

        # 1) 공통 아이템 구조 구성
        items: List[Dict[str, Any]] = []
        for idx, (bakery, score) in enumerate(norm_ranked):
            # 좌표
            lat = None
            lon = None
            try:
                lat = float(bakery.get("latitude") or 0)
                lon = float(bakery.get("longitude") or 0)
                if lat == 0 or lon == 0:
                    lat, lon = None, None
            except Exception:
                lat, lon = None, None
            coord = (lat, lon) if (lat is not None and lon is not None) else None

            # 가까운 지하철역
            station_name = None
            station_index = -1
            if coord is not None:
                try:
                    s_name, s_lat, s_lon = find_nearest_subway_station(coord[0], coord[1])
                    station_name = _normalize_station_name_for_line(s_name) if s_name else None
                    if station_name:
                        station_index = get_subway_station_order_index(station_name)
                except Exception:
                    station_name = None
                    station_index = -1

            # 대기시간 / 오픈시간 기반 route_score
            try:
                wait_min = self._get_expected_wait_minutes(bakery, constraint)
            except Exception:
                wait_min = 0.0

            open_min = self._get_earliest_open_minutes(bakery)

            base_score = float(score or 0.0)
            route_score = base_score

            # 대기시간이 긴 매장은 앞쪽에
            if wait_min and wait_min > 0:
                route_score += min(wait_min, 30.0) * 0.2

            # 너무 늦게 여는 매장은 패널티
            if open_min is not None:
                delta = open_min - start_minutes
                if delta > 180:
                    if delta > 300:
                        route_score -= 1.5
                    else:
                        route_score -= 1.0

            items.append(
                {
                    "bakery": bakery,
                    "score": base_score,
                    "route_score": route_score,
                    "coord": coord,
                    "station_name": station_name,
                    "station_index": station_index,
                    "wait_minutes": float(wait_min or 0.0),
                    "open_minutes": open_min,
                    "orig_idx": idx,
                }
            )

        if len(items) <= 1:
            return norm_ranked

        # 출발 위치
        origin_coord: Optional[Tuple[float, float]] = None
        if loc_filter is not None:
            lat = getattr(loc_filter, "lat", None)
            lon = getattr(loc_filter, "lon", None)
            kind = getattr(loc_filter, "kind", None)
            if kind == "point" and lat is not None and lon is not None:
                origin_coord = (lat, lon)

        # 2) 지하철 모드: 기존 역 순서 기반 로직 유지
        if travel_mode == "transit":
            station_clusters: Dict[int, List[Dict[str, Any]]] = {}
            no_station_items: List[Dict[str, Any]] = []

            for it in items:
                s_idx = it.get("station_index", -1)
                if isinstance(s_idx, int) and s_idx >= 0:
                    station_clusters.setdefault(s_idx, []).append(it)
                else:
                    no_station_items.append(it)

            if not station_clusters:
                return self._order_bakeries_by_route_distance(items, origin_coord, travel_mode)

            for s_idx, bucket in station_clusters.items():
                bucket.sort(
                    key=lambda x: (x.get("route_score") or x.get("score") or 0.0),
                    reverse=True,
                )

            all_station_indices = sorted(station_clusters.keys())

            def choose_start_station_index() -> int:
                nonlocal origin_coord
                if origin_coord is not None:
                    best_idx = None
                    best_dist = None
                    for s_idx, bucket in station_clusters.items():
                        rep_coord = None
                        for it in bucket:
                            if it.get("coord") is not None:
                                rep_coord = it["coord"]
                                break
                        if rep_coord is None:
                            continue
                        d = haversine_distance_km(
                            origin_coord[0], origin_coord[1],
                            rep_coord[0], rep_coord[1],
                        )
                        if best_dist is None or d < best_dist:
                            best_dist = d
                            best_idx = s_idx
                    if best_idx is not None:
                        return best_idx

                best_idx = None
                best_score = None
                for s_idx, bucket in station_clusters.items():
                    top_score = bucket[0].get("route_score") or bucket[0].get("score") or 0.0
                    if best_score is None or top_score > best_score:
                        best_score = top_score
                        best_idx = s_idx
                return int(best_idx if best_idx is not None else all_station_indices[0])

            start_station_idx = choose_start_station_index()

            left_indices = sorted(
                [i for i in all_station_indices if i < start_station_idx],
                reverse=True,
            )
            right_indices = sorted(
                [i for i in all_station_indices if i > start_station_idx]
            )

            pattern1_indices = [start_station_idx] + right_indices + left_indices
            pattern2_indices = [start_station_idx] + left_indices + right_indices

            def build_route(pattern_indices: List[int]) -> List[Dict[str, Any]]:
                route_items: List[Dict[str, Any]] = []
                for s_idx in pattern_indices:
                    bucket = station_clusters.get(s_idx, [])
                    for it in bucket:
                        route_items.append(it)
                return route_items

            route1_items = build_route(pattern1_indices)
            route2_items = build_route(pattern2_indices)

            def route_cost_by_station_index(route_items: List[Dict[str, Any]]) -> float:
                total = 0.0
                last_idx_local: Optional[int] = None
                for it in route_items:
                    s_idx = it.get("station_index", -1)
                    if not isinstance(s_idx, int) or s_idx < 0:
                        continue
                    if last_idx_local is not None:
                        total += abs(s_idx - last_idx_local)
                    last_idx_local = s_idx
                return total

            cost1 = route_cost_by_station_index(route1_items)
            cost2 = route_cost_by_station_index(route2_items)

            if cost1 <= cost2:
                chosen_route_items = route1_items
            else:
                chosen_route_items = route2_items

            no_station_items_sorted = sorted(
                no_station_items,
                key=lambda x: (x.get("route_score") or x.get("score") or 0.0),
                reverse=True,
            )

            final_items = chosen_route_items + no_station_items_sorted
            return [(it["bakery"], it["score"]) for it in final_items]

        # 3) 그 외 모드: 거리 + 인기도(route_score) 가중 그리디
        return self._order_bakeries_by_route_distance(items, origin_coord, travel_mode)

    # --------------------------------------------------
    #  거리 기반 그리디 경로 (walk / car / 일반 fallback용)
    # --------------------------------------------------
    def _order_bakeries_by_route_distance(
        self,
        items: List[Dict[str, Any]],
        origin_coord: Optional[Tuple[float, float]],
        travel_mode: str,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        - origin_coord가 있으면 거기서 가장 '거리+인기도'가 좋은 빵집부터 시작
        - 없으면 route_score(없으면 score)가 가장 높은 빵집부터 시작
        - 매 단계마다 현재 위치에서
            composite = route_score - α * distance_km
          를 최대화하는 미방문 빵집을 선택 (단, d <= max_leg_km)
        - walk 모드에서는 max_leg_km을 넘는 후보는 '다음 클러스터'로 간주하고
          경로에서 제외하여 도보 20분 룰을 강제
        - car / transit 모드에서는 남은 후보를 route_score 순으로 뒤에 붙여
          다음 클러스터로 점프
        """

        if not items:
            return []

        max_leg_km = self._max_leg_distance_km(travel_mode)

        # 거리 페널티 가중치(α)
        if travel_mode == "walk":
            distance_weight = 0.8  # 도보는 거리 비중을 더 높게
        elif travel_mode == "car":
            distance_weight = 0.2
        else:  # transit, 기타
            distance_weight = 0.3

        # 시작점 선택
        if origin_coord is not None:
            best_item = None
            best_score = None
            for it in items:
                coord = it.get("coord")
                if coord is None:
                    continue
                d = haversine_distance_km(
                    origin_coord[0], origin_coord[1],
                    coord[0], coord[1],
                )
                base = it.get("route_score") or it.get("score") or 0.0
                comp = float(base) - distance_weight * d
                if best_score is None or comp > best_score:
                    best_score = comp
                    best_item = it
            if best_item is None:
                start_item = max(
                    items,
                    key=lambda x: (x.get("route_score") or x.get("score") or 0.0),
                )
            else:
                start_item = best_item
        else:
            start_item = max(
                items,
                key=lambda x: (x.get("route_score") or x.get("score") or 0.0),
            )

        used = set()
        route: List[Dict[str, Any]] = []

        route.append(start_item)
        used.add(start_item["orig_idx"])

        while len(used) < len(items):
            last = route[-1]
            last_coord = last.get("coord")
            if last_coord is None:
                break

            best_next = None
            best_comp = None

            for it in items:
                if it["orig_idx"] in used:
                    continue
                coord = it.get("coord")
                if coord is None:
                    continue
                d = haversine_distance_km(
                    last_coord[0], last_coord[1],
                    coord[0], coord[1],
                )
                # 한 구간 최대 거리 제한(클러스터 경계)
                if d > max_leg_km:
                    continue

                base = it.get("route_score") or it.get("score") or 0.0
                comp = float(base) - distance_weight * d
                if best_comp is None or comp > best_comp:
                    best_comp = comp
                    best_next = it

            if best_next is None:
                # 더 이상 "허용 거리 안의 후보"가 없다면
                remaining = [
                    it for it in items
                    if it["orig_idx"] not in used
                ]

                if travel_mode == "walk":
                    # 도보 모드: 20분(≈ max_leg_km) 넘는 후보는
                    # 도보 코스에서 제외 → 경로 종료
                    break
                else:
                    # 자차/대중교통 모드: 남은 후보를 route_score 순으로 뒤에 붙여
                    # 다음 클러스터로 점프
                    remaining_sorted = sorted(
                        remaining,
                        key=lambda x: (x.get("route_score") or x.get("score") or 0.0),
                        reverse=True,
                    )
                    route.extend(remaining_sorted)
                    break

            route.append(best_next)
            used.add(best_next["orig_idx"])

        return [(it["bakery"], it["score"]) for it in route]

    def _filter_candidates_by_travel_time_from_origin(
        self,
        candidates: List[Dict[str, Any]],
        loc_filter: Optional[LocationFilter],
        transport_mode: TransportMode,
        logs: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        시작 위치(사용자 좌표/역 근처) 기준으로
        - 도보: 20분
        - 대중교통/지하철/버스: 30분
        - 자차: 40분
        이내로만 갈 수 있는 빵집만 남긴다.
        """
        if loc_filter is None or loc_filter.kind != "point":
            return list(candidates)

        if loc_filter.lat is None or loc_filter.lon is None:
            return list(candidates)

        user_lat = loc_filter.lat
        user_lon = loc_filter.lon

        # 모드별 최대 허용 시간(분)
        if transport_mode == TransportMode.WALK:
            max_min = 20.0
        elif transport_mode in {TransportMode.SUBWAY, TransportMode.BUS, TransportMode.TRANSIT_MIXED}:
            max_min = 30.0
        elif transport_mode == TransportMode.CAR:
            max_min = 40.0
        else:
            max_min = 30.0  # 기본값

        kept: List[Dict[str, Any]] = []
        before = len(candidates)

        for b in candidates:
            try:
                lat = float(b.get("latitude") or 0.0)
                lon = float(b.get("longitude") or 0.0)
                if not lat or not lon:
                    # 좌표가 없으면 시간 필터를 적용할 수 없으므로 일단 유지
                    kept.append(b)
                    continue
            except Exception:
                kept.append(b)
                continue

            dist_km, walk_min, car_min = self._get_leg_distance_and_durations(
                user_lat, user_lon, lat, lon
            )

            # 모드별 실제 이동시간 추정
            if transport_mode == TransportMode.WALK:
                travel_min = walk_min
            elif transport_mode == TransportMode.CAR:
                if car_min > 0:
                    travel_min = car_min
                else:
                    travel_min = estimate_transit_time_minutes(
                        dist_km, TransportMode.CAR
                    )
            else:
                # 대중교통/지하철/버스 → 차량 시간에 여유를 좀 더 준 보정
                if car_min > 0:
                    travel_min = max(car_min * 1.5, walk_min * 0.6, 10.0)
                else:
                    travel_min = max(walk_min * 0.6, 10.0)

            if travel_min <= max_min + 1e-6:
                kept.append(b)

        after = len(kept)
        if logs is not None:
            mode_name = getattr(transport_mode, "name", str(transport_mode))
            logs.append(
                f"📍 시작 위치 기준 이동시간 필터 후 후보: {before} → {after}개 "
                f"(모드={mode_name}, 최대 {int(max_min)}분 이내)"
            )

        return kept

    # ==============================
    #  메인 질의 처리
    # ==============================

    def answer_query(self, query: str) -> str:
        logs: List[str] = []

        query_type = self._infer_query_type(query)
        logs.append(f"🧭 질의 타입: {query_type}")

        # ① 빵/디저트와 무관한 질문이면 즉시 거절 응답
        if query_type == "irrelevant":
            return (
                "이 챗봇은 **빵집·디저트 맛집 추천**과 **빵/디저트 관련 지식** 질문만 도와드릴 수 있습니다.\n"
                "지금 주신 질문은 이 범위와 관련이 없어 답변해 드리기 어렵습니다.\n\n"
                "대신 예를 들어 다음과 같은 질문을 해 보실 수 있어요.\n"
                "  - '대전역 근처 휘낭시에 맛집 추천해줘'\n"
                "  - '구암역 근처 마들렌 맛집을 추천해줘'\n"
                "  - '마들렌이랑 휘낭시에 차이가 뭐야?'\n"
            )

        # ② 빵/디저트 '지식' 질문이면 지식 모드로 처리
        if query_type == "knowledge":
            answer_text = self._answer_knowledge_query_with_llm(query)
            return answer_text

        # ③ 나머지는 빵집 추천 로직 (기존 코드 그대로)
        loc_filter, loc_logs = extract_location_from_query(query)
        logs.extend(loc_logs)

        transport_mode, transport_logs = detect_transport_mode(query)
        logs.extend(transport_logs)

        dt_constraint = parse_date_time_from_query(query)

        # '지금/바로' 의도가 없을 때는 기본적으로 현재시각을 쓰지 않음
        if (
            not dt_constraint.has_date_range
            and dt_constraint.start_time is None
            and dt_constraint.end_time is None
            and not self._has_now_intent(query)
        ):
            dt_constraint.use_now_if_missing = False

        logs.append(
            "🕒 시간/날짜 파싱 결과: "
            f"has_date_range={dt_constraint.has_date_range}, "
            f"start_date={dt_constraint.start_date}, end_date={dt_constraint.end_date}, "
            f"start_time={dt_constraint.start_time}, end_time={dt_constraint.end_time}, "
            f"use_now_if_missing={dt_constraint.use_now_if_missing}"
        )

        # 3) 메뉴 키워드 / 플래그십 의도
        menu_keywords = extract_menu_keywords(query, self.menu_keywords_set)
        logs.append(f"🍞 메뉴 키워드 인식: {menu_keywords}")

        intent_flags = detect_flagship_tour_intent(query, menu_keywords)
        logs.append(f"🧭 의도 플래그: {intent_flags}")

        # 4) 벡터 검색 쿼리 생성
        search_queries = generate_search_queries(
            user_query=query,
            menu_keywords=menu_keywords,
            loc_filter=loc_filter,
            intent_flags=intent_flags,
        )
        logs.append("🔍 벡터 검색용 생성 쿼리:")
        for q in search_queries:
            logs.append(f"   - {q}")

        # 5) 벡터 검색 → 1차 후보
        candidates = self._vector_search_bakeries(search_queries, top_k=80)
        logs.append(f"🔎 벡터 검색 기반 1차 후보: {len(candidates)}개")

        # 6) 행정구역/반경 기반 위치 필터
        before_loc = len(candidates)
        candidates = filter_bakeries_by_location(candidates, loc_filter)
        logs.append(f"📍 위치/범위 필터 후 후보: {before_loc} → {len(candidates)}개")

        # 7) 시작 위치 기준 "이동시간" 필터 (도보 20분 / 대중교통 30분 / 자차 40분 룰)
        before_travel = len(candidates)
        candidates = self._filter_candidates_by_travel_time_from_origin(
            candidates=candidates,
            loc_filter=loc_filter,
            transport_mode=transport_mode,
            logs=logs,
        )

        # 후보가 너무 빡세게 줄어들면, 로그를 남기고 그대로 진행
        if before_travel > 0 and len(candidates) == 0:
            logs.append(
                "⚠️ 이동시간 필터에서 모든 후보가 제거되어, "
                "이동시간 필터 이전 후보를 그대로 사용합니다."
            )
            candidates = filter_bakeries_by_location(
                self._vector_search_bakeries(search_queries, top_k=80),
                loc_filter,
            )

        # 8) 랭킹 (1차 시도)
        user_lat = getattr(loc_filter, "lat", None)
        user_lon = getattr(loc_filter, "lon", None)

        ranked_list, ranking_logs = rank_bakeries(
            user_query=query,
            candidates=candidates,
            menu_keywords=menu_keywords,
            loc_filter=loc_filter,
            user_lat=user_lat,
            user_lon=user_lon,
            transport_mode=transport_mode,
            intent_flags=intent_flags,
        )
        logs.extend(ranking_logs)

        original_ranked_list = list(ranked_list)

        # 8-1) 메뉴 키워드 때문에 너무 빡세게 걸러져 0개가 되는 경우 → 메뉴 키워드 없이 한 번 더 랭킹
        if not ranked_list and menu_keywords:
            logs.append(
                "⚠️ 1차 랭킹 결과가 0개라, 메뉴 키워드를 무시하고 재랭킹을 시도합니다."
            )
            ranked_list, ranking_logs2 = rank_bakeries(
                user_query=query,
                candidates=candidates,
                menu_keywords=[],  # 메뉴 제약 해제
                loc_filter=loc_filter,
                user_lat=user_lat,
                user_lon=user_lon,
                transport_mode=transport_mode,
                intent_flags=intent_flags,
            )
            logs.extend(ranking_logs2)
            original_ranked_list = list(ranked_list)

        # 9) 동선 최적화 (지하철/도보/자차 모드별)
        if ranked_list:
            if transport_mode == TransportMode.WALK:
                travel_mode_str = "walk"
            elif transport_mode == TransportMode.CAR:
                travel_mode_str = "car"
            else:
                # SUBWAY / BUS / TRANSIT_MIXED → 지하철 라인 기반 동선(한 방향) + 일반 대중교통
                travel_mode_str = "transit"

            routed = self._order_bakeries_by_route(
                ranked=ranked_list,
                loc_filter=loc_filter,
                travel_mode=travel_mode_str,
                constraint=dt_constraint,
                menu_keywords=menu_keywords,
            )

            # 동선 최적화 결과가 비어버리는 방어 로직
            if routed:
                ranked_list = routed
            else:
                logs.append(
                    "⚠️ 동선 최적화 이후 매장이 0개가 되어, "
                    "동선 최적화를 적용하지 않고 원래 랭킹 결과를 그대로 사용합니다."
                )
                ranked_list = [
                    (b, 0.0) for b in original_ranked_list
                ]

        # 10) 상위 N개만 사용
        MAX_RESULTS = 10
        if len(ranked_list) > MAX_RESULTS:
            ranked_list = ranked_list[:MAX_RESULTS]

        # ranked_bakeries 리스트만 별도 추출
        ranked_bakeries_only = [b for (b, _) in ranked_list]

        # 11) "별도 시간 미지정"인 경우, 추천 매장 중 가장 이른 오픈 시각을 시작 시각으로 사용
        if (
            ranked_bakeries_only
            and not dt_constraint.has_date_range
            and dt_constraint.start_time is None
            and not dt_constraint.use_now_if_missing
        ):
            earliest_min: Optional[int] = None
            for b in ranked_bakeries_only:
                m = self._get_earliest_open_minutes(b)
                if m is None:
                    continue
                if earliest_min is None or m < earliest_min:
                    earliest_min = m

            if earliest_min is not None:
                h = earliest_min // 60
                mm = earliest_min % 60
                try:
                    dt_constraint.start_time = time(hour=h, minute=mm)
                    logs.append(
                        f"⏰ 별도 방문 시작 시간이 없어, 추천 매장 중 가장 이른 오픈 시각 "
                        f"({h:02d}:{mm:02d})을 기준으로 일정을 시작합니다."
                    )
                except Exception:
                    pass

        # 12) 설명 헤더 구성
        explain_lines: List[str] = []
        explain_lines.append("=" * 60)
        explain_lines.append(f"🔍 '{query}'")
        explain_lines.append("=" * 60)

        for log in logs:
            if not log:
                continue
            if log[0].isspace():
                explain_lines.append(log)
            else:
                explain_lines.append(f"   {log}")

        explain_lines.append("")

        # 이동수단 라벨
        if transport_mode in {TransportMode.SUBWAY, TransportMode.BUS, TransportMode.TRANSIT_MIXED}:
            route_desc = "대중교통 이동 기준 동선"
        elif transport_mode == TransportMode.WALK:
            route_desc = "도보 이동 기준 동선"
        elif transport_mode == TransportMode.CAR:
            route_desc = "자차 이동 기준 동선"
        else:
            route_desc = "이동 수단을 고려한 동선"

        # 날짜 설명
        if dt_constraint.has_date_range and dt_constraint.start_date:
            if dt_constraint.end_date and dt_constraint.start_date == dt_constraint.end_date:
                date_desc = f"{dt_constraint.start_date} 하루"
            elif dt_constraint.end_date:
                date_desc = f"{dt_constraint.start_date} ~ {dt_constraint.end_date}"
            else:
                date_desc = f"{dt_constraint.start_date} 이후"
        else:
            date_desc = "요청하신 날짜/시간"

        explain_lines.append("안녕하세요, 30년간 제빵 현장에서 일해온 빵집 전문가입니다.")
        explain_lines.append("")
        explain_lines.append(
            f"요청하신 방문 기간/시간({date_desc})을 고려해서 "
            f"({route_desc} 포함) 아래와 같이 코스를 구성했습니다.\n"
        )

        # 13) 실제 답변 본문 생성
        answer_body = self.render_answer(
            user_query=query,
            ranked_bakeries=ranked_bakeries_only,
            loc_filter=loc_filter,
            dt_constraint=dt_constraint,
            transport_mode=transport_mode,
            intent_flags=intent_flags,
            menu_keywords=menu_keywords,
            debug_logs=logs,
        )

        full_answer = "\n".join(explain_lines) + "\n" + answer_body
        return full_answer


    def render_answer(
        self,
        user_query: str,
        ranked_bakeries: List[Dict[str, Any]],
        loc_filter: LocationFilter,
        dt_constraint: DateTimeConstraint,
        transport_mode: TransportMode,
        intent_flags: Dict[str, Any],
        menu_keywords: List[str],
        debug_logs: List[str],
    ) -> str:
        lines: List[str] = []

        if not ranked_bakeries:
            lines.append("죄송하지만, 주어진 조건에 맞는 빵집을 찾지 못했습니다.")
            lines.append("")
            lines.append("- 이동 수단이나 방문 지역/시간 조건을 조금 완화해서 다시 문의해 주세요.")
            return "\n".join(lines)

        total_travel_min: float = 0.0
        total_wait_min: float = 0.0

        start_minutes, start_label = self._infer_start_minutes(dt_constraint)
        current_time_min: float = float(start_minutes)

        if transport_mode == TransportMode.SUBWAY:
            mode_label = "지하철"
        elif transport_mode == TransportMode.BUS:
            mode_label = "버스"
        elif transport_mode == TransportMode.TRANSIT_MIXED:
            mode_label = "대중교통"
        elif transport_mode == TransportMode.CAR:
            mode_label = "자차"
        else:
            mode_label = "도보"

        lines.append(f"총 {len(ranked_bakeries)}곳의 빵집을 추천드립니다.\n")
        lines.append(
            f"(별도 방문 시작 시간이 명시되지 않아, 방문 시작 시각을 {start_label} 기준으로 가정했습니다.)\n"
        )

        prev_lat: Optional[float] = None
        prev_lon: Optional[float] = None
        prev_name: Optional[str] = None

        MAX_CLUSTER_WALK_MIN = 10

        for idx, bakery in enumerate(ranked_bakeries, start=1):
            name = (
                bakery.get("name")
                or bakery.get("slug_ko")
                or bakery.get("slug_en")
                or f"추천 {idx}번 빵집"
            )
            district = bakery.get("district") or bakery.get("_district") or ""
            road_address = (
                bakery.get("road_address")
                or bakery.get("jibun_address")
                or bakery.get("address")
                or ""
            )

            lat = None
            lon = None
            try:
                lat = float(bakery.get("latitude") or 0)
                lon = float(bakery.get("longitude") or 0)
                if lat == 0 or lon == 0:
                    lat, lon = None, None
            except Exception:
                lat, lon = None, None

            rating = _safe_get_rating(bakery)
            try:
                popularity = compute_popularity_score(bakery, self.review_stats_cache)
            except Exception:
                popularity = 0.0

            total_reviews, kw_counts = self.review_stats_cache.get(
                bakery.get("name") or bakery.get("slug_en") or "",
                (0, {}),
            )
            try:
                total_reviews_int = int(str(total_reviews).replace(",", ""))
            except Exception:
                total_reviews_int = 0

            feature_parts: List[str] = []
            if isinstance(kw_counts, dict) and kw_counts:
                top_items = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                for kw, cnt in top_items:
                    try:
                        cnt_int = int(str(cnt).replace(",", ""))
                    except Exception:
                        cnt_int = 0
                    feature_parts.append(f"\"{kw}\" {cnt_int}회")

            kd = bakery.get("keyword_details") or {}
            final_kw = kd.get("final_keywords") or []
            rep_keywords = ", ".join(final_kw[:8]) if final_kw else ""

            try:
                expected_wait = self._get_expected_wait_minutes(bakery, dt_constraint)
            except Exception:
                expected_wait = 0.0

            place_url = ""
            if lat is not None and lon is not None:
                place_url = build_kakao_place_url(name, lat, lon)

            station_line = ""
            if (
                lat is not None
                and lon is not None
                and transport_mode in {TransportMode.SUBWAY, TransportMode.TRANSIT_MIXED}
            ):
                try:
                    station_name, s_lat, s_lon = find_nearest_subway_station(lat, lon)
                except Exception:
                    station_name, s_lat, s_lon = "", 0.0, 0.0

                if station_name and s_lat and s_lon:
                    dist_km = haversine_distance_km(s_lat, s_lon, lat, lon)
                    walk_min = int(round(estimate_walk_time_minutes(dist_km)))
                    station_place_url = build_kakao_place_url(station_name, s_lat, s_lon)

                    station_line = (
                        f"🚇 지하철: '{station_name}'에서 하차 후 도보 약 {walk_min}분 내외\n"
                        f"   - 지하철역 위치(카카오맵): {station_place_url}"
                    )

            lines.append("=" * 50)
            lines.append(f"🥖 추천 {idx}: {name}")
            lines.append("=" * 50)

            if rating > 0 or total_reviews_int > 0 or popularity > 0:
                lines.append(
                    f"⭐ 통합 평점(추정): {rating:.2f}점 / 리뷰 규모: "
                    f"{total_reviews_int:,}건 수준 (인기도 점수: {popularity:.2f})"
                )
            elif rating > 0:
                lines.append(f"⭐ 통합 평점(추정): {rating:.2f}점")

            if district:
                lines.append(f"📍 위치: {district}")
            if road_address:
                lines.append(f"📡 도로명 주소: {road_address}")
            if place_url:
                lines.append(f"🔗 빵집 위치(카카오맵): {place_url}")

            if idx == 1:
                if mode_label in ["지하철", "버스", "대중교통"]:
                    lines.append(f"🧭 이동 수단: {mode_label} 기준으로 동선을 구성했습니다.")
                elif mode_label == "자차":
                    lines.append("🧭 이동 수단: 자차 기준으로 동선을 구성했습니다.")
                else:
                    lines.append("🧭 이동 수단: 도보 기준으로 동선을 구성했습니다.")

            if station_line:
                lines.append(station_line)

            # 이전 매장 → 현재 매장 이동
            leg_travel_min = 0.0

            if (
                idx > 1
                and prev_lat is not None
                and prev_lon is not None
                and lat is not None
                and lon is not None
                and prev_name
            ):
                try:
                    leg_km, walk_between_est, car_between_min = self._get_leg_distance_and_durations(
                        prev_lat, prev_lon, lat, lon
                    )
                    walk_between_min = int(round(walk_between_est))

                    if walk_between_min <= MAX_CLUSTER_WALK_MIN:
                        leg_travel_min = float(walk_between_min)
                        lines.append(
                            f"➡ 이전 추천 매장 → 여기까지: 도보 약 {walk_between_min}분"
                        )
                        route_url = build_kakao_route_url(
                            "walk",
                            prev_name, prev_lat, prev_lon,
                            name, lat, lon,
                        )
                        if route_url:
                            lines.append(f"   - 도보 동선(카카오맵): {route_url}")
                    else:
                        if transport_mode in {
                            TransportMode.SUBWAY,
                            TransportMode.BUS,
                            TransportMode.TRANSIT_MIXED,
                        }:
                            if car_between_min <= 0:
                                transit_min = max(walk_between_min * 0.6, 10.0)
                            else:
                                if leg_km <= 3.0:
                                    transit_min = max(
                                        car_between_min * 2.0,
                                        walk_between_min * 0.6,
                                        10.0,
                                    )
                                else:
                                    transit_min = max(
                                        car_between_min * 1.5,
                                        walk_between_min * 0.5,
                                        20.0,
                                    )

                            leg_travel_min = float(transit_min)
                            lines.append(
                                f"➡ 이전 추천 매장 → 여기까지: 약 {leg_km:.2f}km / "
                                f"예상 {int(round(transit_min))}분 ({mode_label})"
                            )
                            route_url = build_kakao_route_url(
                                "traffic",
                                prev_name, prev_lat, prev_lon,
                                name, lat, lon,
                            )
                            if route_url:
                                lines.append(
                                    f"   - 대중교통 길찾기(카카오맵): {route_url}\n"
                                    "     (실제 버스/지하철 노선과 실시간 소요 시간은 위 링크에서 확인해 주세요.)"
                                )
                        elif transport_mode == TransportMode.CAR:
                            if car_between_min > 0:
                                car_min = car_between_min
                            else:
                                car_min = estimate_transit_time_minutes(
                                    leg_km, TransportMode.CAR
                                )
                            leg_travel_min = float(car_min)
                            lines.append(
                                f"➡ 이전 추천 매장 → 여기까지: 약 {leg_km:.2f}km / "
                                f"예상 {int(round(car_min))}분 (자차)"
                            )
                            route_url = build_kakao_route_url(
                                "car",
                                prev_name, prev_lat, prev_lon,
                                name, lat, lon,
                            )
                            if route_url:
                                lines.append(
                                    f"   - 자차 길찾기(카카오맵): {route_url}"
                                )
                        else:
                            # 도보 모드(TransportMode.WALK)에서는
                            # 이미 경로 구성 단계에서 20분 초과 구간을 제거했으므로
                            # 여기에서는 Kakao 기준 시간이 20분을 조금 넘더라도
                            # 그대로 표시만 해준다.
                            leg_travel_min = float(walk_between_min)
                            lines.append(
                                f"➡ 이전 추천 매장 → 여기까지: 도보 약 {walk_between_min}분"
                            )
                            route_url = build_kakao_route_url(
                                "walk",
                                prev_name, prev_lat, prev_lon,
                                name, lat, lon,
                            )
                            if route_url:
                                lines.append(f"   - 도보 동선(카카오맵): {route_url}")
                except Exception:
                    leg_travel_min = 0.0

            total_travel_min += leg_travel_min

            open_minutes = self._get_earliest_open_minutes(bakery)
            arrival_time_min = current_time_min + leg_travel_min

            wait_for_open = 0.0
            if open_minutes is not None and arrival_time_min < open_minutes:
                wait_for_open = float(open_minutes - arrival_time_min)

            base_wait = float(expected_wait or 0.0)
            total_wait_for_shop = max(0.0, wait_for_open + base_wait)

            stay_minutes = float(self.avg_purchase_minutes)
            depart_time_min = arrival_time_min + total_wait_for_shop + stay_minutes

            total_wait_min += total_wait_for_shop

            if base_wait and base_wait > 0:
                wait_text = (
                    f"⏱ 평균 예상 대기시간(주말/공휴일/인기도 반영): "
                    f"약 {int(round(base_wait))}분 기준"
                )
                lines.append(wait_text)

            lines.append("")
            lines.append("⏰ 방문 시간 계획(예상):")
            lines.append(
                f"   - 예상 도착 시각: {self._format_minutes_to_hhmm(int(round(arrival_time_min)))}"
            )
            if leg_travel_min > 0:
                lines.append(
                    f"   - 이전 매장에서 이동: 약 {int(round(leg_travel_min))}분"
                )
            if wait_for_open > 0:
                if open_minutes is not None:
                    open_str = self._format_minutes_to_hhmm(int(open_minutes))
                    lines.append(
                        f"   - 오픈까지 대기: 약 {int(round(wait_for_open))}분 "
                        f"(영업 시작 시각 {open_str} 기준)"
                    )
                else:
                    lines.append(
                        f"   - 오픈까지 대기: 약 {int(round(wait_for_open))}분"
                    )
            if base_wait > 0:
                lines.append(
                    f"   - 줄 서는 시간(예상): 약 {int(round(base_wait))}분"
                )
            lines.append(
                f"   - 매장 내 머무는 시간(구매/시식): 약 {int(round(stay_minutes))}분"
            )
            lines.append(
                f"   → 다음 매장 이동 시작 시각: {self._format_minutes_to_hhmm(int(round(depart_time_min)))}"
            )

            current_time_min = depart_time_min

            lines.append("")
            lines.append("✨ 이 집의 특징(리뷰 키워드 상위):")
            if feature_parts:
                lines.append("   - " + ", ".join(feature_parts))
            else:
                lines.append("   - 리뷰 키워드 데이터가 충분하지 않습니다.")

            lines.append("")
            if rep_keywords:
                lines.append(f"   - 대표 메뉴/키워드: {rep_keywords}")
            else:
                lines.append("   - 대표 메뉴/키워드: (데이터 부족)")

            lines.append("")
            lines.append("👨‍🍳 전문가 코멘트:")
            lines.append(
                "   일정 수준 이상의 리뷰 수와 인기도를 가진 매장으로, "
                "빵지순례 코스로 묶어서 방문하기 좋은 집입니다."
            )
            lines.append("")

            prev_lat, prev_lon, prev_name = lat, lon, name

        # ----------------------
        # 코스 설계 이유 요약
        # ----------------------
        lines.append("==================================================")
        lines.append("🧾 이 코스를 이렇게 짠 이유")
        lines.append("==================================================")

        menu_focus_line = build_menu_focus_sentence(
            menu_keywords=menu_keywords,
            has_menu_focus=bool(intent_flags.get("has_menu_focus", False)),
        )
        lines.append(menu_focus_line)

        if transport_mode in {TransportMode.SUBWAY, TransportMode.BUS, TransportMode.TRANSIT_MIXED}:
            lines.append(
                "- 대전 1호선 주요 역 주변으로 묶어서, 지하철 노선도를 따라 "
                "한 방향으로 이동할 수 있도록 역 단위 클러스터를 구성했습니다."
            )
        else:
            lines.append(
                "- 현재 위치(또는 첫 방문 매장)를 기준으로 주변 빵집들을 거리 기반 클러스터로 나눈 뒤, "
                "가까운 클러스터를 먼저 소진하고 그 다음 클러스터로 이동하는 단방향(One-way) 동선을 구성했습니다."
            )

        lines.append(
            "- 각 클러스터 및 매장 선택 시, 단순 거리뿐 아니라 인기도(route_score)도 함께 고려하여 "
            "너무 멀리 돌아가지 않으면서도 인기 있는 매장은 비교적 코스 앞쪽에 배치하려고 했습니다."
        )
        lines.append(
            "- 리뷰 수와 waiting_prediction, 주말/공휴일 가중치를 이용해 "
            "대기시간이 길거나 인기·품절 위험이 있는 매장은 최대한 코스의 앞쪽에 배치했습니다."
        )
        if transport_mode == TransportMode.WALK:
            lines.append(
                f"- 도보 코스의 경우, 한 번에 이동하는 구간이 대략 {int(self.MAX_WALK_MINUTES)}분을 넘지 않도록 "
                "후보를 제한해 '도보 20분 룰'을 최대한 지키도록 구성했습니다."
            )
        else:
            lines.append(
                "- Kakao Mobility 내비 API가 허용하는 범위 안에서는 실제 도로 기준 거리와 차량 소요 시간을 활용해 "
                "도보·대중교통·자차 이동시간을 추정했고, API 호출에 실패한 경우에만 직선거리 기반 보정값을 사용했습니다."
            )

        lines.append("")
        lines.append("⏱️ 예상 소요 시간 요약 (이동 + 줄 서기)")
        lines.append(
            f"- 매장 간 이동 시간 합계(대략): 약 {int(round(total_travel_min))}분"
        )
        lines.append(
            f"- 줄 서는 시간(오픈 대기 포함, 대략): 약 {int(round(total_wait_min))}분"
        )
        lines.append(
            "- 실제 소요 시간은 요일/시간대/실제 대기 인원과 실시간 교통 상황에 따라 달라질 수 있으며, "
            "각 매장에서 머무르는 시간(시식·포장 등)은 사용자의 스타일에 따라 달라질 수 있습니다."
        )

        if intent_flags.get("debug", False) and debug_logs:
            lines.append("=" * 50)
            lines.append("[디버그 로그]")
            lines.extend(debug_logs)

        return "\n".join(lines)

    # =======================================================
    # 빵 관련 지식 모드
    # =======================================================

    def _answer_knowledge_query_with_llm(self, query: str) -> str:
        if self.llm_client is None:
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
            print("🧠 지식 Q&A LLM 응답 생성 성공 (solar-mini-250422)")
            return answer
        except Exception as e:
            print(f"⚠️ 지식 Q&A LLM 호출 실패: {e}")
            return (
                "제과·제빵 지식 설명용 LLM 호출에 문제가 발생했습니다. "
                "잠시 후 다시 시도해 주세요."
            )

    def _infer_query_type(self, query: str) -> str:
        """
        질의 타입 분류:
        - recommend  : 빵집/디저트 맛집·코스 추천
        - knowledge  : 빵/디저트 자체에 대한 지식 질문
        - irrelevant : 빵/디저트와 무관한 질문 → 답변 거절
        """
        q = query.strip()
        q_nospace = q.replace(" ", "")
        q_lower = q_nospace.lower()

        # 1) "빵/디저트 관련 질문인지" 먼저 판별 --------------------
        #    - 고정 키워드는 최소한만 두고
        #    - 나머지는 base_keywords.json에서 로드한 메뉴 키워드에 의존
        core_bakery_tokens = [
            "빵", "빵집", "베이커리",
            "디저트", "카페",
            "케이크", "케익",
            "구움과자", "브레드",
        ]

        is_bakery_related = any(tok in q for tok in core_bakery_tokens)

        # base_keywords.json 의 메뉴 키워드를 전부 스캔
        # (예: 마들렌, 휘낭시에, 크로와상/크루아상, 까눌레, 팡도르, 에클레어 등)
        if not is_bakery_related and getattr(self, "menu_keywords_set", None):
            for mk in self.menu_keywords_set:
                if not mk:
                    continue
                if mk in q:
                    is_bakery_related = True
                    break

        # 영어권 키워드 (영문 질의용 – 최소만)
        if not is_bakery_related:
            bakery_keywords_en = [
                "bread", "bakery", "cake", "dessert",
                "croissant", "baguette", "macaron",
                "madeleine", "financier", "scone",
                "tart", "pie", "cookie", "donut", "doughnut",
            ]
            if any(tok in q_lower for tok in bakery_keywords_en):
                is_bakery_related = True

        # 여기까지 했는데도 아무 관련 키워드가 없으면 → 이 챗봇의 도메인 밖
        if not is_bakery_related:
            return "irrelevant"

        # 2) 빵/디저트 관련으로 확정된 이후, "추천 vs 지식" 분리 -------------------

        # (1) 추천/코스 의도
        recommend_keywords = [
            "추천해줘", "추천 해줘", "추천해 주세요", "추천해주세요",
            "맛집", "빵집 추천", "코스", "빵지순례",
            "어디 갈까", "어디가 좋을까", "어디가 좋나요",
            "갈 만한", "가면 좋은", "가고 싶은",
            "코스 짜줘", "코스짜줘", "루트 짜줘", "동선 짜줘",
        ]
        for kw in recommend_keywords:
            if kw in q:
                return "recommend"

        # "추천"이라는 단어가 들어오면 기본적으로 추천 의도로 간주
        if "추천" in q:
            return "recommend"

        # (2) 지식/이론 질문 의도
        knowledge_keywords = [
            "어떤 종류", "종류가 있나요", "종류는", "종류 알려줘",
            "차이점", "차이가 뭐야", "차이가 뭔가요",
            "유래", "역사", "기원", "특징", "설명해줘",
            "왜 이렇게", "왜 그런가요", "원리", "원칙",
            "레시피", "만드는 법", "만드는법", "방법",
            "반죽", "발효", "굽는", "굽기", "온도", "시간",
        ]
        for kw in knowledge_keywords:
            if kw in q:
                return "knowledge"

        # 물음표가 있으면서 '맛집/추천/코스'가 없으면 → 지식 질문일 가능성이 높다고 보고 knowledge
        if "?" in q and not any(k in q for k in ["맛집", "추천", "코스", "빵집 추천"]):
            return "knowledge"

        # 3) 그 외는 기본적으로 "추천"으로 처리
        return "recommend"


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


def _safe_get_rating(bakery: Dict[str, Any]) -> float:
    """
    ranking_utils._safe_rating 을 그대로 래핑해서 사용.
    - 내부에서는 0~5 스케일의 통합 평점을 반환한다.
    """
    try:
        return float(_safe_rating(bakery))
    except Exception:
        return 0.0


def build_menu_focus_sentence(menu_keywords: List[str], has_menu_focus: bool) -> str:
    if has_menu_focus and menu_keywords:
        main_keywords = menu_keywords[:3]
        kw_text = " / ".join(main_keywords)
        return (
            f"- '{kw_text}' 관련 키워드가 많이 언급된 매장을 먼저 추린 뒤, "
            "그중에서 평점과 리뷰 수(인기도)를 기준으로 1차 랭킹을 했습니다."
        )
    else:
        return (
            "- 전체 빵집 중에서 평점과 리뷰 수(인기도)를 기준으로 1차 랭킹을 했습니다."
        )


if __name__ == "__main__":
    rag = BakeryExpertRAG()
    rag.interactive()
