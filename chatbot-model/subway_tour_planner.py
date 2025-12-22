from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import math
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 기본 데이터 구조
# ============================================================

@dataclass
class SubwayStation:
    """
    대전 1호선 한 역을 표현하는 구조체
    - id: 내부 식별용 (예: 'central_ro')
    - name: 역 이름 (예: '중앙로')
    - index: 노선 상의 순서 (0 ~ N-1, 왼쪽에서 오른쪽 혹은 반대로 일관되게 정렬)
    - lat/lon: 위도, 경도
    """
    id: str
    name: str
    index: int
    lat: float
    lon: float


@dataclass
class BakerySubwayInfo:
    """
    빵집과 가장 가까운 지하철역 정보
    - station_id: SubwayStation.id
    - station_index: SubwayStation.index
    - station_name: SubwayStation.name
    - walk_minutes: 역에서 빵집까지 도보 시간(분)
    """
    station_id: str
    station_index: int
    station_name: str
    walk_minutes: float


# ============================================================
# 거리/도보 시간 계산 유틸
# ============================================================

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    두 위경도 사이의 대략적인 거리(km)를 계산.
    """
    R = 6371.0
    rad = math.radians

    dlat = rad(lat2 - lat1)
    dlon = rad(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def estimate_walk_minutes(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    walk_speed_kmh: float = 4.0,
) -> float:
    """
    위경도 2점 사이를 도보로 이동할 때의 시간(분)을 단순 추정.
    """
    dist_km = haversine_km(lat1, lon1, lat2, lon2)
    hours = dist_km / max(walk_speed_kmh, 1e-6)
    return hours * 60.0


# ============================================================
# 빵집에 지하철 정보 붙이기 + 도보 20분 이내 필터
# ============================================================

def attach_nearest_subway_info(
    bakeries: List[Dict[str, Any]],
    subway_stations: List[SubwayStation],
    max_walk_minutes: float = 20.0,
) -> List[Dict[str, Any]]:
    """
    각 빵집에 가장 가까운 지하철역 정보를 붙이고,
    지하철역 도보 max_walk_minutes 이내인 빵집만 남긴다.

    입력 빵집 dict에는 최소한 아래 키가 필요합니다.
    - 'lat', 'lon' (위경도)
    - 'score' 또는 'final_score' 처럼 정렬에 사용될 점수 필드 (이름은 자유, 뒤에서 그대로 사용)

    반환: 'subway_info' 필드가 추가된 빵집 리스트
    """
    if not subway_stations:
        logger.warning("[SUBWAY] 지하철 역 정보가 없습니다. 필터링을 건너뜁니다.")
        return bakeries

    attached: List[Dict[str, Any]] = []
    for b in bakeries:
        lat = b.get("lat")
        lon = b.get("lon")
        if lat is None or lon is None:
            continue

        best_station: Optional[SubwayStation] = None
        best_minute = float("inf")

        for st in subway_stations:
            minutes = estimate_walk_minutes(lat, lon, st.lat, st.lon)
            if minutes < best_minute:
                best_minute = minutes
                best_station = st

        if best_station is None:
            continue

        if best_minute <= max_walk_minutes:
            b = dict(b)  # 원본 보호
            b["subway_info"] = BakerySubwayInfo(
                station_id=best_station.id,
                station_index=best_station.index,
                station_name=best_station.name,
                walk_minutes=best_minute,
            )
            attached.append(b)

    logger.info(
        f"[SUBWAY] 지하철역 도보 {max_walk_minutes}분 이내 매장만 유지: "
        f"{len(bakeries)} → {len(attached)}개"
    )
    return attached


# ============================================================
# 지하철 노선 기반 연속 구간 선택 + 코스 생성
# ============================================================

def _group_bakeries_by_station(
    bakeries: List[Dict[str, Any]],
    score_key: str,
) -> Dict[int, List[Dict[str, Any]]]:
    """
    station_index 기준으로 빵집을 그룹화하고,
    각 역 내에서는 score_key 기준 내림차순 정렬.
    """
    by_station: Dict[int, List[Dict[str, Any]]] = {}

    for b in bakeries:
        info: BakerySubwayInfo = b.get("subway_info")
        if not info:
            continue
        idx = info.station_index
        by_station.setdefault(idx, []).append(b)

    for idx, lst in by_station.items():
        lst.sort(key=lambda x: x.get(score_key, 0.0), reverse=True)

    return by_station


def _evaluate_interval(
    by_station: Dict[int, List[Dict[str, Any]]],
    station_indices_sorted: List[int],
    left: int,
    right: int,
    score_key: str,
    max_total_bakeries: int,
    max_bakeries_per_station: int,
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    [left, right] 구간에 대해:
    - 각 역에서 max_bakeries_per_station 개까지 가져오고
    - 전체에서 max_total_bakeries 개만 남겼을 때의 총 점수와 빵집 리스트를 반환
    """
    selected: List[Dict[str, Any]] = []

    for idx in station_indices_sorted:
        if idx < left or idx > right:
            continue
        station_bakeries = by_station.get(idx, [])
        if not station_bakeries:
            continue
        # 역별 상위 N개만 임시 후보로
        selected.extend(station_bakeries[:max_bakeries_per_station])

    if not selected:
        return 0.0, []

    # 전체에서 상위 max_total_bakeries만 선택
    selected.sort(key=lambda x: x.get(score_key, 0.0), reverse=True)
    selected = selected[:max_total_bakeries]

    total_score = sum(b.get(score_key, 0.0) for b in selected)
    return total_score, selected


def build_subway_contiguous_tour(
    bakeries: List[Dict[str, Any]],
    subway_stations: List[SubwayStation],
    *,
    score_key: str = "final_score",
    max_total_bakeries: int = 10,
    max_bakeries_per_station: int = 3,
) -> List[Dict[str, Any]]:
    """
    '지하철 모드'에서 사용할 투어 경로 생성.

    조건
    ----
    1) 노선 상에서 '연속된 역 구간 [L, R]'만 사용 (중간에 역이 '뚝' 끊기지 않음)
    2) 한 번 정해진 구간은 한 방향으로만 이동 (역을 왕복하지 않음)
    3) 각 역에서 일정 개수까지만 선택 (max_bakeries_per_station)
    4) 전체 추천 개수는 max_total_bakeries 이하

    반환
    ----
    - 최종 방문 순서에 맞게 정렬된 빵집 리스트
      (station_index 오름차순으로 정렬되어 있기 때문에, 실제 동선도 한 방향으로만 진행)
    """
    if not bakeries:
        return []

    # 1) station_index 기준으로 그룹화
    by_station = _group_bakeries_by_station(bakeries, score_key)
    if not by_station:
        return []

    station_indices_sorted = sorted(by_station.keys())

    best_score = 0.0
    best_interval: Optional[Tuple[int, int]] = None
    best_bakeries: List[Dict[str, Any]] = []

    # 2) 모든 연속 구간 [L, R]을 브루트포스 탐색 (역 수가 22개라 충분히 가능)
    for i, left_idx in enumerate(station_indices_sorted):
        for right_idx in station_indices_sorted[i:]:
            total_score, selected = _evaluate_interval(
                by_station=by_station,
                station_indices_sorted=station_indices_sorted,
                left=left_idx,
                right=right_idx,
                score_key=score_key,
                max_total_bakeries=max_total_bakeries,
                max_bakeries_per_station=max_bakeries_per_station,
            )
            if total_score <= 0.0 or not selected:
                continue
            if total_score > best_score:
                best_score = total_score
                best_interval = (left_idx, right_idx)
                best_bakeries = selected

    if not best_interval or not best_bakeries:
        # 연속 구간으로 만들 수 있는 게 없다면, 그냥 상위 N개 fallback
        logger.info(
            "[SUBWAY] 연속 구간 경로를 찾지 못해, 단순 상위 랭킹으로 대체합니다."
        )
        fallback = sorted(
            bakeries,
            key=lambda x: x.get(score_key, 0.0),
            reverse=True,
        )
        return fallback[:max_total_bakeries]

    L, R = best_interval
    logger.info(
        f"[SUBWAY] 선택된 지하철 연속 구간: index {L} ~ {R} "
        f"(총 점수={best_score:.3f}, 매장수={len(best_bakeries)})"
    )

    # 3) 선택된 빵집들을 '역 index → 빵집' 순으로 재정렬
    def _station_index(b: Dict[str, Any]) -> int:
        info: BakerySubwayInfo = b["subway_info"]
        return info.station_index

    def _score(b: Dict[str, Any]) -> float:
        return b.get(score_key, 0.0)

    # 역 index 오름차순, 같은 역 내에서는 점수 높은 순
    best_bakeries.sort(key=lambda x: (_station_index(x), -_score(x)))

    # 4) 편의를 위해, 최종 결과에 역 정보(이름, 도보시간)를 평평하게 풀어서 넣어줌
    result: List[Dict[str, Any]] = []
    for b in best_bakeries:
        info: BakerySubwayInfo = b["subway_info"]
        enriched = dict(b)
        enriched["nearest_subway_station_name"] = info.station_name
        enriched["nearest_subway_station_index"] = info.station_index
        enriched["nearest_subway_walk_minutes"] = round(info.walk_minutes, 1)
        result.append(enriched)

    return result


# ============================================================
# 상위 레벨: 랭킹 + 지하철 모드 투어 생성 헬퍼
# ============================================================

def plan_bakery_tour_with_subway(
    ranked_bakeries: List[Dict[str, Any]],
    subway_stations: List[SubwayStation],
    *,
    score_key: str = "final_score",
    max_walk_minutes: float = 20.0,
    max_total_bakeries: int = 10,
    max_bakeries_per_station: int = 3,
) -> List[Dict[str, Any]]:
    """
    이미 랭킹이 끝난 빵집 리스트(ranked_bakeries)를 입력으로 받아
    '지하철 모드'에 맞게 최종 코스를 생성합니다.

    1) 지하철역 도보 max_walk_minutes 분 이내인 매장만 남기고
    2) 역 index 기준 연속 구간을 찾은 뒤
    3) 그 구간 안에서 최적의 빵집 조합(점수 합 최대)을 선택합니다.
    """
    logger.info(f"[SUBWAY] 이동 수단 모드: subway")
    logger.info(
        f"[SUBWAY] 입력 랭킹 후보: {len(ranked_bakeries)}개, "
        f"지하철역 {len(subway_stations)}개"
    )

    # 1. 역 도보 20분 이내 필터
    attached = attach_nearest_subway_info(
        ranked_bakeries,
        subway_stations,
        max_walk_minutes=max_walk_minutes,
    )

    if not attached:
        logger.info("[SUBWAY] 지하철 도보 범위 내 매장이 없어, 기존 랭킹 상위만 반환합니다.")
        return ranked_bakeries[:max_total_bakeries]

    # 2. 연속 구간 기반 최적 코스 구성
    route = build_subway_contiguous_tour(
        attached,
        subway_stations=subway_stations,
        score_key=score_key,
        max_total_bakeries=max_total_bakeries,
        max_bakeries_per_station=max_bakeries_per_station,
    )

    logger.info(
        f"[SUBWAY] 최종 지하철 코스 매장 수: {len(route)}개 "
        f"(요청 상한={max_total_bakeries})"
    )

    return route
