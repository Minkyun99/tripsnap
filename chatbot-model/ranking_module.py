from __future__ import annotations

from math import log10
from typing import Any, Dict, List, Tuple, Optional, Set

from schemas import LocationFilter, TransportMode
from ranking_utils import (
    haversine_distance_km,
    estimate_walk_time_minutes,
)

from location_module import (
    find_nearest_subway_station,
    get_subway_stations
)

# -----------------------------
# 상수 정의
# -----------------------------
MAX_WALK_MINUTES = 20          # 도보 전용/일반 도보 허용 시간 (약 1.3km)
MAX_WALK_FROM_STATION_MIN = 20 # 역/정류장에서 빵집까지 허용 도보 시간 (지하철/버스 역 기준에선 별도 사용 가능)
MAX_TRANSIT_DISTANCE_KM = 20 # 대중교통 추천 시, 직선거리 기준 너무 먼 코스는 제외

# 플래그십(대표) 빵집 이름 패턴: 빵지순례/대표 코스일 때 가산점 부여
KNOWN_FLAGSHIP_NAMES: List[str] = [
    "성심당",
    "정인구팥빵",
    "콜드버터베이크샵",
    "구오베이크샵",
    "데아로즈",
    "대전사람 수부씨",
    "몽심",
]


# -----------------------------
# 리뷰 통계/인기도 계산
# -----------------------------
def build_review_stats_cache(bakeries: List[Dict[str, Any]]) -> Dict[str, Tuple[int, Dict[str, int]]]:
    """
    빵집별 리뷰 키워드 총량과 키워드별 카운트를 캐싱한다.

    반환 형태:
        {
            "성심당 본점": (총_키워드_등장수, {"\"빵이 맛있어요\"": 45483, ...}),
            ...
        }
    """
    cache: Dict[str, Tuple[int, Dict[str, int]]] = {}
    for b in bakeries:
        name = b.get("name") or b.get("slug_en")
        if not name:
            continue

        total = 0
        kw_counts: Dict[str, int] = {}
        for rk in b.get("review_keywords") or []:
            kw = rk.get("keyword")
            cnt = rk.get("count") or 0
            if not kw:
                continue
            try:
                cnt_int = int(cnt)
            except Exception:
                try:
                    cnt_int = int(str(cnt).replace(",", ""))
                except Exception:
                    cnt_int = 0
            total += cnt_int
            kw_counts[kw] = cnt_int

        cache[name] = (total, kw_counts)

    return cache


def _parse_rating(bakery: Dict[str, Any]) -> float:
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


def compute_popularity_score(
    bakery: Dict[str, Any],
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
) -> float:
    """
    평점 + 리뷰 규모를 합친 인기도 점수 (대략 0~10 스케일).
    """
    name = bakery.get("name") or bakery.get("slug_en") or ""
    rating = _parse_rating(bakery)  # 보통 0~5
    total_reviews, _ = review_stats_cache.get(name, (0, {}))

    # 평점 0~5 → 0~1
    rating_norm = (rating / 5.0) if rating > 0 else 0.5  # 정보 없으면 0.5 정도

    # 리뷰 수를 log 스케일로 0~1 정규화 (기준 50,000 리뷰)
    max_reviews = 50000.0
    review_norm = log10(total_reviews + 1) / log10(max_reviews + 1)

    popularity = 0.6 * rating_norm + 0.4 * review_norm
    return popularity * 10.0  # 0~10 근사 스케일


# -----------------------------
# 메뉴 키워드 / 빵지순례 의도
# -----------------------------
def extract_menu_keywords(query: str, menu_keyword_set: Set[str]) -> List[str]:
    """
    base_keywords.json의 메뉴 키워드 중 질의에 등장하는 것만 추출.
    """
    found: List[str] = []
    for kw in menu_keyword_set:
        if kw in query and kw not in found:
            found.append(kw)
    return found


def detect_flagship_tour_intent(
    query: str,
    menu_keywords: List[str],
) -> Dict[str, Any]:
    """
    '대전 대표 빵집', '빵지순례', '성지순례' 등 플래그십 코스 추천 의도 탐지.
    """
    q = query.replace(" ", "")
    is_flagship = False
    if any(token in q for token in ["빵지순례", "성지순례", "대표빵집", "대전대표", "대전핫플", "빵투어"]):
        is_flagship = True
    if "코스추천" in q or "코스짜줘" in q:
        is_flagship = True

    return {
        "is_flagship_tour": is_flagship,
        "has_menu_focus": len(menu_keywords) > 0,
    }


def generate_search_queries(
    user_query: str,
    menu_keywords: List[str],
    loc_filter: LocationFilter,
    intent_flags: Dict[str, Any],
) -> List[str]:
    """
    벡터 검색용 보조 쿼리 생성.
    LocationFilter의 필드명이 구현에 따라 다를 수 있으므로
    getattr()으로 안전하게 city/district/dong 정보를 가져온다.
    """
    queries: List[str] = [user_query]

    # LocationFilter의 실제 필드명을 몰라도 동작하도록 방어적으로 처리
    loc_city = (
        getattr(loc_filter, "city", None)
        or getattr(loc_filter, "city_name", None)
        or getattr(loc_filter, "region_city", None)
    )
    loc_district = (
        getattr(loc_filter, "district", None)
        or getattr(loc_filter, "district_name", None)
        or getattr(loc_filter, "region_district", None)
    )
    loc_dong = (
        getattr(loc_filter, "dong", None)
        or getattr(loc_filter, "dong_name", None)
        or getattr(loc_filter, "region_dong", None)
    )

    loc_parts: List[str] = []
    if loc_city:
        loc_parts.append(str(loc_city))
    if loc_district:
        loc_parts.append(str(loc_district))
    if loc_dong:
        loc_parts.append(str(loc_dong))

    loc_prefix = " ".join(loc_parts) if loc_parts else ""

    # 1) 위치 + 디저트/빵집 기본 쿼리
    if loc_prefix:
        queries.append(f"{loc_prefix} 디저트 빵집 베이커리")
        if menu_keywords:
            queries.append(f"{loc_prefix} {' '.join(menu_keywords)} 맛집 빵집 베이커리")

    # 2) 메뉴 기반 보조 쿼리
    if menu_keywords:
        mk_text = " ".join(menu_keywords)
        queries.append(f"{mk_text} 맛집 빵집 베이커리")
        queries.append(f"{mk_text} 겉바속촉 촉촉한 구움과자 전문 빵집")

    # 3) 빵지순례/대표 코스 의도일 때
    if intent_flags.get("is_flagship_tour"):
        if loc_prefix:
            queries.append(f"{loc_prefix} 대표 빵집 베이커리")
            queries.append(f"{loc_prefix} 빵지순례 코스 빵집")
        else:
            # 위치 정보가 없으면 기본적으로 '대전' 기준으로 검색
            queries.append("대전 대표 빵집 베이커리")
            queries.append("대전 빵지순례 코스 빵집")

    # 4) 중복 제거
    seen = set()
    deduped: List[str] = []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            deduped.append(q)

    return deduped


# -----------------------------
# 거리/이동수단 필터링
# -----------------------------
def is_within_walk_limit(distance_km: float, max_minutes: float) -> bool:
    walk_time = estimate_walk_time_minutes(distance_km)
    return walk_time <= max_minutes


def filter_bakeries_by_transport(
    bakeries: List[Dict[str, Any]],
    user_lat: Optional[float],
    user_lon: Optional[float],
    transport_mode: TransportMode,
) -> List[Dict[str, Any]]:
    if user_lat is None or user_lon is None:
        return bakeries

    filtered: List[Dict[str, Any]] = []

    for b in bakeries:
        raw_lat = b.get("lat") or b.get("latitude")
        raw_lon = b.get("lon") or b.get("longitude")

        if not raw_lat or not raw_lon:
            continue

        try:
            blat = float(raw_lat)
            blon = float(raw_lon)
        except Exception:
            continue

        dist_km = haversine_distance_km(user_lat, user_lon, blat, blon)

        if transport_mode == TransportMode.WALK:
            if is_within_walk_limit(dist_km, MAX_WALK_MINUTES):
                filtered.append(b)

        elif transport_mode in (
            TransportMode.BUS,
            TransportMode.TRANSIT_MIXED,
            TransportMode.SUBWAY,
        ):
            if dist_km <= MAX_TRANSIT_DISTANCE_KM:
                filtered.append(b)
        else:
            filtered.append(b)

    return filtered


def filter_bakeries_by_subway_station_access(
    bakeries: List[Dict[str, Any]],
    max_walk_min: float = MAX_WALK_FROM_STATION_MIN,
) -> List[Dict[str, Any]]:
    """
    지하철 모드에서 사용할 1차 필터.

    - 각 빵집 기준으로 '대전 1호선 역 리스트'에서 가장 가까운 역을 찾고
    - 역 → 빵집까지 도보 시간이 max_walk_min 분 이하인 매장만 남긴다.
    - 주변에 역이 없거나, 도보 시간이 초과되면 제외.
    """
    filtered: List[Dict[str, Any]] = []

    for b in bakeries:
        lat = b.get("latitude")
        lon = b.get("longitude")
        if lat in (None, "", 0, "0") or lon in (None, "", 0, "0"):
            continue
        try:
            blat = float(lat)
            blon = float(lon)
        except (TypeError, ValueError):
            continue

        # 대전 1호선 역 리스트 기준 '가장 가까운 역' 찾기
        station_name, s_lat, s_lon = find_nearest_subway_station(blat, blon)
        if not station_name or not s_lat or not s_lon:
            # 주변에 역이 없다고 판단
            continue

        # 역 ↔ 빵집 거리 → 도보 시간
        dist_km = haversine_distance_km(blat, blon, s_lat, s_lon)
        walk_min = estimate_walk_time_minutes(dist_km)

        if walk_min <= max_walk_min:
            filtered.append(b)

    return filtered



# -----------------------------
# 최종 랭킹
# -----------------------------
def rank_bakeries(
    user_query: str,
    candidates: List[Dict[str, Any]],
    menu_keywords: List[str],
    loc_filter: LocationFilter,
    user_lat: Optional[float],
    user_lon: Optional[float],
    transport_mode: TransportMode,
    intent_flags: Dict[str, Any],
    top_k: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    최종 랭킹 함수.

    요구사항 반영:
    1) 특정 메뉴(예: 휘낭시에, 소금빵 등)가 있는 경우
       - 해당 메뉴 언급량이 너무 낮은 매장은 컷
       - 신생 매장은 전체 리뷰 수가 적어도 해당 메뉴 언급량이 절대적으로 많으면 상위 랭킹

    2) 빵지순례 / 대표 코스
       - KNOWN_FLAGSHIP_NAMES 에 포함된 플래그십 매장에 가산점

    3) 이동수단
       - TransportMode.WALK: 사용자 기준 도보 20분 이내만 남김
       - 그 외 대중교통 모드: 직선거리 15km 넘는 매장은 후보에서 제거
    """

    logs: List[str] = []

    # 0. 리뷰 통계 캐시 생성
    review_stats_cache = build_review_stats_cache(candidates)
    logs.append(f"🧮 리뷰 통계 캐시 생성: {len(review_stats_cache)}개 매장")

        # 1. 이동수단 기반 1차 필터
    logs.append(f"🚦 이동 수단 모드: {transport_mode.value}")
    pre_filtered = filter_bakeries_by_transport(
        candidates,
        user_lat=user_lat,
        user_lon=user_lon,
        transport_mode=transport_mode,
    )
    logs.append(f"📍 이동수단/거리 기반 1차 필터링: {len(candidates)} → {len(pre_filtered)}개")

    # ✅ 지하철 모드일 때: '역 기준 도보 15분 이내' 매장만 유지
    if transport_mode == TransportMode.SUBWAY:
        before = len(pre_filtered)
        pre_filtered = filter_bakeries_by_subway_station_access(
            pre_filtered,
            max_walk_min=MAX_WALK_FROM_STATION_MIN,
        )
        logs.append(
            f"🚇 지하철역 도보 {MAX_WALK_FROM_STATION_MIN}분 이내 매장만 유지: {before} → {len(pre_filtered)}개"
        )


    has_menu_focus = len(menu_keywords) > 0
    is_flagship_tour = intent_flags.get("is_flagship_tour", False)

    precomputed: List[Dict[str, Any]] = []
    max_menu_count = 0

    # 2. 매장별 기본 스탯/메뉴 언급 수 전처리
    for b in pre_filtered:
        name = b.get("name") or b.get("slug_en") or ""
        total_reviews, _ = review_stats_cache.get(name, (0, {}))
        popularity = compute_popularity_score(b, review_stats_cache)

        kd = b.get("keyword_details") or {}
        kw_stats = kd.get("keyword_stats") or {}

        menu_count = 0
        if has_menu_focus:
            for mk in menu_keywords:
                stat = kw_stats.get(mk) or {}
                cnt = stat.get("pos_count") or 0
                try:
                    cnt_int = int(cnt)
                except Exception:
                    cnt_int = 0
                menu_count += cnt_int

        precomputed.append(
            {
                "bakery": b,
                "name": name,
                "total_reviews": total_reviews,
                "popularity": popularity,
                "menu_count": menu_count,
            }
        )
        if has_menu_focus and menu_count > max_menu_count:
            max_menu_count = menu_count

    logs.append(f"📊 메뉴 포커스 여부: {has_menu_focus}, 최대 메뉴 언급 수: {max_menu_count}")

    # 3. 메뉴 포커스가 있을 때 메뉴 언급량 기준으로 너무 약한 매장 컷
    if has_menu_focus:
        if max_menu_count <= 0:
            filtered_for_scoring = precomputed
            logs.append("⚠️ 메뉴 언급이 거의 없어 메뉴 기반 컷을 적용하지 않습니다.")
        else:
            min_abs = 3              # 절대 최소 언급량 (예: 1~2회인 매장 컷)
            min_rel = int(max_menu_count * 0.1)  # 최고치의 10%
            threshold = max(min_abs, min_rel)
            logs.append(f"✂ 메뉴 언급 컷 임계값: {threshold}회 이상인 매장만 유지")

            filtered_for_scoring: List[Dict[str, Any]] = []
            for row in precomputed:
                if row["menu_count"] >= threshold:
                    filtered_for_scoring.append(row)
            # 다 날아가면 원본 유지
            if not filtered_for_scoring:
                logs.append("⚠️ 모든 매장이 컷되어, 메뉴 기반 컷을 무시하고 전체를 사용합니다.")
                filtered_for_scoring = precomputed
    else:
        filtered_for_scoring = precomputed

    # 4. 실제 스코어 계산
    scored: List[Tuple[Dict[str, Any], float]] = []
    for row in filtered_for_scoring:
        b = row["bakery"]
        name = row["name"]
        total_reviews = row["total_reviews"]
        popularity = row["popularity"]
        menu_count = row["menu_count"]

        is_flagship = any(flag in name for flag in KNOWN_FLAGSHIP_NAMES)

        if has_menu_focus:
            denom = max(total_reviews, 1)
            menu_density = menu_count / denom
            menu_raw_component = log10(menu_count + 1)
            pop_component = popularity / 10.0  # 0~1

            score = (
                0.55 * menu_raw_component
                + 0.25 * menu_density * 10.0   # 비율도 0~10 스케일로 반영
                + 0.20 * pop_component
            )
        else:
            pop_component = popularity / 10.0
            score = pop_component

        if is_flagship_tour and is_flagship:
            score += 1.5  # 빵지순례 모드 플래그십 가산점

        scored.append((b, score))

    # 5. 스코어 기준 정렬
    scored.sort(key=lambda x: x[1], reverse=True)

    # 6. 상위 K개만 자르기 (요청된 경우)
    if top_k is not None and top_k > 0:
        scored = scored[:top_k]

    ranked_bakeries = [b for b, _ in scored]
    logs.append(f"✅ 최종 랭킹 완료: {len(ranked_bakeries)}개 매장")

    return ranked_bakeries, logs



def filter_subway_walk_range(bakeries):
    stations = get_subway_stations()
    result = []

    for b in bakeries:
        # lat/lon → 없으면 latitude/longitude 사용
        raw_lat = b.get("lat") if b.get("lat") is not None else b.get("latitude")
        raw_lon = b.get("lon") if b.get("lon") is not None else b.get("longitude")

        if raw_lat in (None, "", 0, "0") or raw_lon in (None, "", 0, "0"):
            continue

        try:
            blat = float(raw_lat)
            blon = float(raw_lon)
        except (TypeError, ValueError):
            continue

        min_walk = 999999

        for st in stations:
            d = haversine_distance_km(blat, blon, st["lat"], st["lon"])
            walk_min = estimate_walk_time_minutes(d)
            min_walk = min(min_walk, walk_min)

        if min_walk <= MAX_WALK_FROM_STATION_MIN:  # “도보 20분 기준”
            b["_nearest_subway_walk_min"] = round(min_walk)
            result.append(b)

    return result


def get_menu_focus_score(bakery, query_menus):
    stats = bakery.get("keyword_details", {}).get("keyword_stats", {})
    total_count = sum(v["pos_count"] for v in stats.values()) or 1

    def count_of(kw):
        return stats.get(kw, {}).get("pos_count", 0)

    exact_cnt = sum(count_of(k) for k in query_menus["exact"])
    family_cnt = sum(count_of(k) for k in query_menus["family"])

    exact_ratio = exact_cnt / total_count

    score = (
        exact_cnt * 3.0 +
        family_cnt * 1.5 +
        exact_ratio * 5.0
    )
    return score, exact_cnt
