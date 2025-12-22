# ranking_utils.py

from typing import Any, Dict, List, Tuple
import math
from math import radians, sin, cos, sqrt, atan2
from schemas import TransportMode

EARTH_RADIUS_KM = 6371.0

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    두 좌표 사이의 대략적인 직선 거리(km).
    이미 구현돼 있다면 기존 함수를 사용하세요.
    """
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_KM * c

def estimate_walk_time_minutes(distance_km: float, walk_speed_kmph: float = 4.0) -> float:
    """
    도보 이동 시간(분) 근사. 기본 보행 속도 4km/h.
    """
    if distance_km <= 0:
        return 0.0
    return (distance_km / walk_speed_kmph) * 60.0

def estimate_transit_time_minutes(distance_km: float, mode: TransportMode) -> float:
    """
    지하철/버스 이동 시간(분)을 단순 직선거리 기반으로 근사.

    - 지하철: 평균 30km/h 가정
    - 버스: 평균 20km/h 가정
    - 혼합: 둘 중 작은 값 사용
    """
    if distance_km <= 0:
        return 0.0

    if mode == TransportMode.SUBWAY:
        speed = 30.0
    elif mode == TransportMode.BUS:
        speed = 20.0
    elif mode == TransportMode.TRANSIT_MIXED:
        # 단순화: 지하철 vs 버스 중 더 빠른 쪽
        speed = 25.0
    else:
        # 도보/자차는 여기서 다루지 않음
        speed = 25.0

    return (distance_km / speed) * 60.0



def _safe_rating(bakery: Dict[str, Any]) -> float:
    """
    dessert_en.json 의 rating 필드 변경을 반영하여 안전하게 평점을 가져온다.

    지원하는 구조:
      1) 새 구조 (현재): bakery["rating"] 이 숫자(또는 숫자 문자열)
         - 네이버 + 카카오 합산 점수 (0~10 스케일) 로 가정
         - 내부에서는 0~5 스케일로 쓰기 위해 2로 나눠서 사용
      2) 구 구조: bakery["rating"] 이 dict 이고
         - rating["rating"], rating["naver_rate"], rating["kakao_rate"] 중 하나를 사용
         - 이 값이 5를 초과하면 동일하게 2로 나눠서 0~5 스케일로 정규화

    어떤 경우에도 숫자로 변환 실패 시 보수적으로 4.0을 반환.
    """
    raw = bakery.get("rating")

    # -----------------------------
    # 1) dict 형태 (구조 호환)
    # -----------------------------
    if isinstance(raw, dict):
        rating_info = raw

        # 우선순위: rating > naver_rate > kakao_rate
        for key in ("rating", "naver_rate", "kakao_rate"):
            if key in rating_info and rating_info[key] not in (None, ""):
                candidate = rating_info[key]
                try:
                    val = float(candidate)
                except Exception:
                    try:
                        val = float(str(candidate).replace(",", ""))
                    except Exception:
                        continue

                # 혹시 0~10 스케일로 들어온 경우를 대비해 5 초과 시 2로 나눔
                if val > 5.0:
                    val = val / 2.0
                return val

        # dict 인데 usable 값이 하나도 없으면 default
        return 4.0

    # -----------------------------
    # 2) 새 구조: 숫자 또는 숫자 문자열
    # -----------------------------
    if raw is None or raw == "":
        return 4.0

    try:
        val = float(raw)
    except Exception:
        try:
            val = float(str(raw).replace(",", ""))
        except Exception:
            return 4.0

    # 현재 JSON은 네이버+카카오 합산(0~10) → 내부 0~5 로 변환
    if val > 5.0:
        val = val / 2.0

    return val






def _get_review_stats(
    bakery: Dict[str, Any],
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
) -> Tuple[int, Dict[str, int]]:
    """
    review_stats_cache 에서 (총 리뷰 수, 키워드별 카운트)를 가져온다.
    """
    name = bakery.get("name") or bakery.get("slug_en") or ""
    total, kw_counts = review_stats_cache.get(name, (0, {}))
    return int(total), (kw_counts or {})


def _get_keywords(
    bakery: Dict[str, Any]
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """
    keyword_details 에서 최종 키워드 리스트와 keyword_stats 를 가져온다.
    - final_keywords: ['소금빵', '에그타르트', ...]
    - keyword_stats: {
         '소금빵': {'pos_count': 10, 'ratio': 0.1},
         ...
      }
    """
    kd = bakery.get("keyword_details") or {}
    final_keywords = kd.get("final_keywords") or []
    kw_stats = kd.get("keyword_stats") or {}
    return final_keywords, kw_stats


def _compute_base_score(
    bakery: Dict[str, Any],
    menu_keywords: List[str],
    intent_flags: Dict[str, Any],
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
    known_flagship_names: List[str],
) -> Tuple[float, int, int]:
    """
    기본 점수 계산:

    - 메뉴 키워드가 없는 일반 질의:
        · 평점: 0.6 비중
        · 리뷰 수(log 스케일): 0.4 비중

    - 메뉴 키워드를 명시한 질의(예: 소금빵, 에그타르트 등):
        · 해당 메뉴 키워드의 '강도'(pos_count 기반)를 최우선으로 반영
        · 그 다음으로 평점, 그 다음으로 리뷰 수가 따라오는 구조
        → 사용자가 특정 빵을 콕 집었을 때
          그 빵이 얼마나 많이 언급됐는지가 랭킹에 강하게 반영되도록 설계.
    """
    name = bakery.get("name") or bakery.get("slug_en") or ""
    rating = _safe_rating(bakery)
    total_reviews, _ = _get_review_stats(bakery, review_stats_cache)
    pop_score = math.log10(total_reviews + 1)

    final_keywords, kw_stats = _get_keywords(bakery)
    kw_set = set(final_keywords)

    menu_kw_set = set(menu_keywords)
    has_menu_query = len(menu_kw_set) > 0

    # 메뉴 키워드 일치 개수 (소금빵, 에그타르트 등 몇 개나 겹치는지)
    menu_match_cnt = len(menu_kw_set & kw_set)

    # 메뉴 키워드 "강도" 점수: 키워드별 pos_count를 log 스케일로 합산
    menu_intensity_score = 0.0
    if has_menu_query and menu_match_cnt > 0:
        for kw in menu_kw_set:
            stat = kw_stats.get(kw)
            if not stat:
                continue
            c = stat.get("pos_count", 0)
            if c > 0:
                # 예: 소금빵 10회 → log10(11) ~= 1.04
                #     소금빵 50회 → log10(51) ~= 1.71  → 더 높은 점수
                menu_intensity_score += math.log10(c + 1)

    # -----------------------------
    # 1) 메뉴 키워드가 없는 일반 질의
    # -----------------------------
    if not has_menu_query:
        base = rating * 0.6 + pop_score * 0.4
        return base, total_reviews, menu_match_cnt

    # -----------------------------
    # 2) 메뉴 키워드가 있는 질의
    #    (예: 소금빵, 에그타르트 등)
    # -----------------------------
    if menu_match_cnt > 0:
        # 메뉴 강도를 최우선, 그 다음 평점, 그 다음 리뷰 수
        base = (
            menu_intensity_score * 3.0  # 메뉴 강도 비중 크게
            + rating * 0.5              # 기본 평점
            + pop_score * 0.2           # 리뷰 수는 보조 역할
        )
    else:
        # 메뉴 키워드가 있지만, 이 매장은 해당 메뉴가 없음
        # → 메뉴 점수 없이 기본 평점/리뷰만 반영 (다만 우선순위는 떨어지도록)
        base = rating * 0.5 + pop_score * 0.3

    # (옵션) 빵지순례 모드 + 플래그십 이름 가중 (현재 known_flagship_names는 비어 있음)
    if intent_flags.get("is_flagship_tour") and known_flagship_names:
        if any(flag and flag in name for flag in known_flagship_names):
            base += 0.5

    return base, total_reviews, menu_match_cnt


def _extract_brand_key(name: str, known_flagship_names: List[str]) -> str:
    """
    같은 브랜드의 여러 지점을 하나로 묶기 위한 brand key 추출.
    예: '성심당 본점', '성심당 대전역점' → '성심당'
    """
    if not name:
        return ""

    # 우선, 플래그십 이름이 포함되어 있으면 그걸 브랜드 키로 사용
    for brand in known_flagship_names or []:
        if brand and brand in name:
            return brand

    # 아니면 공백 앞 첫 단어 (예: '몽심 도안점' -> '몽심')
    return name.split()[0]


def _is_coffee_dominant_for_tour(
    name: str,
    review_stats_cache: Dict[str, Tuple[int, Dict[str, int]]],
    coffee_threshold_ratio: float = 1.4,
) -> bool:
    """
    빵지순례에서 제외해야 할 정도로 '커피가 맛있어요' 비중이 높은지 판단.
    - '빵이 맛있어요' 또는 '디저트가 맛있어요'가 거의 없는데
      '커피가 맛있어요'만 많은 경우 → 카페로 보고 제외
    - 커피가 빵/디저트 언급에 비해 너무 많은 경우도 제외
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

    # 빵/디저트 언급이 전혀 없고 커피만 있는 경우 → 커피집
    if main_sweet == 0 and coffee > 0:
        return True

    # 빵/디저트 언급은 있으나, 커피가 훨씬 더 많이 언급되는 경우
    if main_sweet > 0 and (coffee / main_sweet) >= coffee_threshold_ratio:
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
        · 평점/리뷰수 기반 점수 계산 후, 상위 top_k 반환
    - 메뉴 키워드 포함 질의(소금빵, 에그타르트 등):
        · 해당 메뉴 키워드의 리뷰 언급 강도(pos_count)를 크게 반영
        · 메뉴가 실제로 많이 언급된 매장을 최상단으로 끌어올림
    - 빵지순례 모드 (is_flagship_tour=True):
        · 리뷰 수가 너무 적은 매장은 컷 (예: 200건 미만 제외)
        · '커피가 맛있어요' 비중이 과도한 카페는 제외
        · 같은 브랜드(성심당, 콜드버터 등)는 1곳만 추천
    """
    scored_items: List[Dict[str, Any]] = []

    # 1) 모든 후보에 대해 기본 점수 계산
    for b in candidates:
        base_score, total_reviews, menu_match_cnt = _compute_base_score(
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
                "menu_match_cnt": menu_match_cnt,
            }
        )

    # 2) 점수순 정렬 (공통)
    scored_items.sort(key=lambda x: x["score"], reverse=True)

    # 2-1) 메뉴 키워드가 명시된 경우:
    #      해당 키워드를 전혀 포함하지 않는 매장은,
    #      '메뉴 매칭 매장만으로도 top_k를 채울 수 있을 때' 뒤로 미룸
    if menu_keywords:
        menu_matched = [it for it in scored_items if it.get("menu_match_cnt", 0) > 0]
        if len(menu_matched) >= top_k:
            scored_items = menu_matched

    # 3) 빵지순례 모드가 아니면 → 단순 상위 top_k 반환
    if not intent_flags.get("is_flagship_tour"):
        return [(it["bakery"], it["score"]) for it in scored_items[:top_k]]

    # ============================
    # 빵지순례 모드 전용 로직
    # ============================
    MIN_REVIEWS_FOR_TOUR = 200

    flagship_candidates: List[Dict[str, Any]] = []

    # 3-1) 리뷰 수 기준 + 커피 비중 기준 1차 필터
    for it in scored_items:
        if it["total_reviews"] < MIN_REVIEWS_FOR_TOUR:
            continue

        name = it["name"]

        if _is_coffee_dominant_for_tour(name, review_stats_cache):
            continue

        flagship_candidates.append(it)

    # 후보가 너무 적으면 컷 해제하고 전체 사용
    if len(flagship_candidates) < top_k:
        flagship_candidates = scored_items

    selected: List[Tuple[Dict[str, Any], float]] = []
    used_brands = set()

    # 3-2) 브랜드 중복을 최소화하면서 선택
    for item in flagship_candidates:
        if len(selected) >= top_k:
            break
        name = item["name"]
        brand_key = _extract_brand_key(name, known_flagship_names)
        if brand_key and brand_key in used_brands:
            continue
        selected.append((item["bakery"], item["score"]))
        if brand_key:
            used_brands.add(brand_key)

    # 3-3) 그래도 top_k 를 못 채웠다면,
    #      남은 것에서 브랜드 중복 허용하며 채우기 (안전망)
    if len(selected) < top_k:
        already_ids = {id(b) for b, _ in selected}
        for item in flagship_candidates:
            if len(selected) >= top_k:
                break
            if id(item["bakery"]) in already_ids:
                continue
            selected.append((item["bakery"], item["score"]))

    return selected
