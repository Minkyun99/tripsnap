# ranking_utils.py
from typing import Any, Dict, List, Tuple
import math


def _safe_rating(bakery: Dict[str, Any]) -> float:
    """
    네이버/카카오 평점 중 하나를 사용하고,
    없으면 보수적으로 4.0으로 둡니다.
    """
    rating_info = bakery.get("rating") or {}
    r = rating_info.get("naver_rate") or rating_info.get("kakao_rate")
    try:
        return float(r)
    except Exception:
        return 4.0


def _get_review_stats(
    bakery: Dict[str, Any],
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
) -> Tuple[int, Dict[str, int]]:
    """
    review_stats_cache 에서 매장 이름 기준으로 (총 리뷰 수, 키워드 카운트 dict)를 가져옵니다.
    (없으면 (0, {})로 처리)
    """
    name = bakery.get("name") or bakery.get("slug_en") or ""
    if not name:
        return 0, {}
    if name not in review_stats_cache:
        return 0, {}
    return review_stats_cache[name]


def _get_total_reviews(
    bakery: Dict[str, Any],
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
) -> int:
    total, _ = _get_review_stats(bakery, review_stats_cache)
    return total


def _get_keywords(bakery: Dict[str, Any]) -> List[str]:
    """
    최종 키워드 목록 (예: 에그타르트, 소금빵, 휘낭시에 등)을 가져옵니다.
    """
    kd = bakery.get("keyword_details") or {}
    return kd.get("final_keywords") or []


def _compute_base_score(
    bakery: Dict[str, Any],
    menu_keywords: List[str],
    intent_flags: Dict[str, Any],
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
    known_flagship_names: List[str],
) -> Tuple[float, int]:
    """
    기본 점수 계산.
    - 평점: 0.6 비중
    - 리뷰 수(log 스케일): 0.4 비중
    - 메뉴 키워드(예: 에그타르트 등) 매칭: +0.5씩 가점
    - (옵션) 빵지순례 코스에서 대표 플래그십에 소폭 가산
    """
    name = bakery.get("name") or bakery.get("slug_en") or ""
    rating = _safe_rating(bakery)
    total_reviews = _get_total_reviews(bakery, review_stats_cache)

    # 인기도: 리뷰 수를 로그 스케일로
    pop_score = math.log10(total_reviews + 1)

    # 메뉴 키워드 매칭
    final_keywords = _get_keywords(bakery)
    kw_set = set(final_keywords)
    menu_kw_set = set(menu_keywords)
    menu_match_cnt = len(menu_kw_set & kw_set)
    menu_match_score = menu_match_cnt * 0.5

    base = rating * 0.6 + pop_score * 0.4 + menu_match_score

    # 빵지순례 모드에서 대표 플래그십(성심당 등)에 약간 보너스
    if intent_flags.get("is_flagship_tour") and known_flagship_names:
        if any(flag in name for flag in known_flagship_names):
            base += 0.5

    return base, total_reviews


def _extract_brand_key(name: str, known_flagship_names: List[str]) -> str:
    """
    같은 브랜드의 여러 지점을 하나로 묶기 위한 brand key 추출.

    - known_flagship_names 에 들어 있는 문자열이 이름에 포함되면 그걸 브랜드 키로 사용
      (예: '성심당 본점', '성심당 DCC점', '성심당 롯데백화점 대전점' -> '성심당')
    - 아니면, 공백 앞 첫 단어를 브랜드 키로 사용
      (예: '몽심 도안점' -> '몽심')
    """
    if not name:
        return ""

    for brand in known_flagship_names or []:
        if brand and brand in name:
            return brand

    # 공백 기준 첫 토큰 사용
    return name.split()[0]


def _is_coffee_dominant_for_tour(
    name: str,
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
    coffee_threshold_ratio: float = 1.5,
) -> bool:
    """
    빵지순례에서 제외해야 할 정도로 '커피가 맛있어요' 비중이 높은지 판단.

    규칙:
      - 키워드 카운트:
          coffee  = '커피가 맛있어요'
          bread   = '빵이 맛있어요'
          dessert = '디저트가 맛있어요'
      - main_sweet = max(bread, dessert)

      - 아래 중 하나면 True (즉, 빵지순례에서 제외):
          * main_sweet == 0 이고 coffee > 0
              -> 빵/디저트 언급이 거의 없고 커피만 언급되는 카페 성격
          * coffee / main_sweet >= coffee_threshold_ratio
              -> 커피가 빵/디저트보다 확실히 더 많이 언급됨
    """
    total, kw_counts = review_stats_cache.get(name, (0, {}))
    if not kw_counts:
        return False

    coffee = kw_counts.get("커피가 맛있어요", 0)
    bread = kw_counts.get("빵이 맛있어요", 0)
    dessert = kw_counts.get("디저트가 맛있어요", 0)

    if coffee <= 0:
        return False

    main_sweet = max(bread, dessert)

    # 빵/디저트 언급이 전혀 없고 커피만 있는 경우 → 커피집으로 보고 제외
    if main_sweet == 0 and coffee > 0:
        return True

    # 빵/디저트 언급은 있으나, 커피가 훨씬 더 많이 언급되는 경우
    if main_sweet > 0:
        ratio = coffee / float(main_sweet)
        if ratio >= coffee_threshold_ratio:
            return True

    return False


def rank_bakeries(
    candidates: List[Dict[str, Any]],
    menu_keywords: List[str],
    intent_flags: Dict[str, Any],
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
    known_flagship_names: List[str],
    top_k: int = 10,
) -> List[Tuple[Dict[str, Any], float]]:
    """
    공통 랭킹 함수.

    - 일반 추천:
        · 평점/리뷰수/메뉴 키워드 기반 점수 계산 후, 단순 상위 top_k 반환
    - 빵지순례 모드 (is_flagship_tour=True):
        · 리뷰 수가 너무 적은 매장은 컷 (예: 200건 미만 제외)
        · '커피가 맛있어요' 비중이 과도하게 높은 카페는 제외
          (단, '빵이 맛있어요' 또는 '디저트가 맛있어요'가 비슷한 수준이면 허용)
        · 같은 브랜드(성심당, 콜드버터, 캘리포니아 등)는 1곳만 추천
        · 이후 점수 순으로 top_k 구성
    """
    scored_items: List[Dict[str, Any]] = []

    # 1) 모든 후보에 대해 기본 점수 계산
    for b in candidates:
        base_score, total_reviews = _compute_base_score(
            b,
            menu_keywords,
            intent_flags,
            review_stats_cache,
            known_flagship_names,
        )
        name = b.get("name") or b.get("slug_en") or ""

        scored_items.append(
            {
                "bakery": b,
                "name": name,
                "score": base_score,
                "total_reviews": total_reviews,
            }
        )

    # 2) 점수순 정렬 (공통)
    scored_items.sort(key=lambda x: x["score"], reverse=True)

    # 3) 빵지순례 모드가 아니면, 예전처럼 단순 상위 top_k 반환
    if not intent_flags.get("is_flagship_tour"):
        return [(it["bakery"], it["score"]) for it in scored_items[:top_k]]

    # ============================
    # 빵지순례 모드 전용 로직
    # ============================

    MIN_REVIEWS_FOR_TOUR = 200  # 필요하면 150 / 300 등으로 조정 가능

    flagship_candidates: List[Dict[str, Any]] = []

    # 3-1) 리뷰 수 기준 + 커피 비중 기준 1차 필터
    for it in scored_items:
        # 리뷰 컷
        if it["total_reviews"] < MIN_REVIEWS_FOR_TOUR:
            continue

        name = it["name"]

        # 커피 비중이 과도하게 높은 카페는 빵지순례에서 제외
        if _is_coffee_dominant_for_tour(name, review_stats_cache):
            continue

        flagship_candidates.append(it)

    # 컷을 치고 나니 후보가 너무 적으면, 안전하게 커피/리뷰 컷 해제해서 전체 사용
    if len(flagship_candidates) < top_k:
        flagship_candidates = scored_items

    selected: List[Tuple[Dict[str, Any], float]] = []
    used_brands = set()

    # 3-2) 브랜드 중복 제거하면서 점수 순으로 선택
    for item in flagship_candidates:
        if len(selected) >= top_k:
            break

        name = item["name"]
        brand_key = _extract_brand_key(name, known_flagship_names)

        # 같은 브랜드(성심당, 콜드버터, 캘리포니아 등)의 다른 지점은 스킵
        if brand_key in used_brands:
            continue

        selected.append((item["bakery"], item["score"]))
        used_brands.add(brand_key)

    # 3-3) 그래도 top_k 를 못 채웠다면,
    #      남은 것에서 브랜드 중복 허용하며 채우기 (거의 발생 X, 안전망)
    if len(selected) < top_k:
        already_ids = {id(b) for b, _ in selected}
        for item in flagship_candidates:
            if len(selected) >= top_k:
                break
            if id(item["bakery"]) in already_ids:
                continue
            selected.append((item["bakery"], item["score"]))

    return selected
