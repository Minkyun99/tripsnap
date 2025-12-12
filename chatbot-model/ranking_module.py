from __future__ import annotations

from math import log10
from typing import Any, Dict, List, Tuple

from schemas import LocationFilter


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


def extract_menu_keywords(query: str, menu_keyword_set: set[str]) -> List[str]:
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
    queries = [user_query]

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


def rank_bakeries(
    candidates: List[Dict[str, Any]],
    menu_keywords: List[str],
    intent_flags: Dict[str, Any],
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
    known_flagship_names: List[str],
    top_k: int = 10,
) -> List[Tuple[Dict[str, Any], float]]:
    """
    최종 랭킹 함수.

    요구사항 반영:
    1) 특정 메뉴(예: 휘낭시에)가 있는 경우
       - 해당 메뉴 언급량이 너무 낮은 매장은 컷
       - 신생 매장은 전체 리뷰 수가 적어도 해당 메뉴 언급량이 절대적으로 많으면 상위 랭킹

    2) 빵지순례 / 대표 코스
       - 성심당, 몽심, 콜드버터 등 플래그십 매장에 가산점
    """
    has_menu_focus = len(menu_keywords) > 0
    is_flagship_tour = intent_flags.get("is_flagship_tour", False)

    precomputed: List[Dict[str, Any]] = []
    max_menu_count = 0

    for b in candidates:
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

    # 메뉴 포커스가 있을 때 메뉴 언급량 기준으로 너무 약한 매장 컷
    if has_menu_focus:
        if max_menu_count <= 0:
            filtered_for_scoring = precomputed
        else:
            min_abs = 3  # 절대 최소 언급량 (예: 1~2회인 매장 컷)
            min_rel = int(max_menu_count * 0.1)  # 최고치의 10%
            threshold = max(min_abs, min_rel)

            filtered_for_scoring = []
            for row in precomputed:
                if row["menu_count"] >= threshold:
                    filtered_for_scoring.append(row)
            # 다 날아가면 원본 유지
            if not filtered_for_scoring:
                filtered_for_scoring = precomputed
    else:
        filtered_for_scoring = precomputed

    # 실제 스코어 계산
    scored: List[Tuple[Dict[str, Any], float]] = []
    for row in filtered_for_scoring:
        b = row["bakery"]
        name = row["name"]
        total_reviews = row["total_reviews"]
        popularity = row["popularity"]
        menu_count = row["menu_count"]

        is_flagship = any(flag in name for flag in known_flagship_names)

        score = 0.0

        if has_menu_focus:
            denom = max(total_reviews, 1)
            menu_density = menu_count / denom
            menu_raw_component = log10(menu_count + 1)
            pop_component = popularity / 10.0  # 0~1

            score = (
                0.55 * menu_raw_component
                + 0.25 * menu_density * 10.0
                + 0.20 * pop_component
            )
        else:
            pop_component = popularity / 10.0
            score = pop_component

        if is_flagship_tour and is_flagship:
            score += 1.5  # 빵지순례 모드 플래그십 가산점

        scored.append((b, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    if top_k is not None and top_k > 0:
        return scored[:top_k]
    return scored
