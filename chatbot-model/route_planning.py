# route_planning.py
from __future__ import annotations
from typing import List, Dict, Optional, Tuple
import math


def _to_float(value) -> float:
    """문자열/숫자 모두 안전하게 float 변환."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    위도/경도로 두 지점 사이의 대략적인 거리(km)를 구합니다.
    지하철 노선처럼 '대략적인 공간적 거리'를 기준으로 동선을 매끄럽게 만드는 데 사용.
    """
    R = 6371.0  # 지구 반지름 (km)

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def optimize_route_by_distance(
    bakeries: List[Dict],
    start_point: Dict,
) -> List[Dict]:
    """
    '지하철 동선'처럼 왔다 갔다 하지 않도록
    start_point 기준으로 가까운 순서대로 매장을 방문하는 경로를 생성합니다.

    - bakeries: 최종 코스에 넣기로 한 빵집 리스트 (dict에 latitude, longitude 포함)
    - start_point: 사용자의 시작 위치 또는 첫 방문 매장
                   { "latitude": ..., "longitude": ... } 형태

    반환값: 경로가 최적화된 bakeries 리스트 (순서만 바뀜)
    """
    if not bakeries:
        return []

    # 시작 좌표
    current_lat = _to_float(start_point["latitude"])
    current_lon = _to_float(start_point["longitude"])

    remaining = list(bakeries)  # shallow copy
    ordered: List[Dict] = []

    while remaining:
        # 현재 지점에서 가장 가까운 매장을 하나 선택 (최근접 이웃 탐색)
        def distance_from_current(b: Dict) -> float:
            lat = _to_float(b["latitude"])
            lon = _to_float(b["longitude"])
            return haversine_km(current_lat, current_lon, lat, lon)

        next_bakery = min(remaining, key=distance_from_current)
        ordered.append(next_bakery)
        remaining.remove(next_bakery)

        current_lat = _to_float(next_bakery["latitude"])
        current_lon = _to_float(next_bakery["longitude"])

    return ordered


def choose_start_point(
    user_location: Optional[Dict],
    bakeries: List[Dict],
) -> Dict:
    """
    - 사용자의 현재 위치가 있으면 그 위치를 시작점
    - 없으면: 첫 번째 빵집을 시작점으로 사용
    """
    if user_location and "latitude" in user_location and "longitude" in user_location:
        return {
            "latitude": _to_float(user_location["latitude"]),
            "longitude": _to_float(user_location["longitude"]),
        }

    if not bakeries:
        raise ValueError("bakeries가 비어 있어 시작점을 정할 수 없습니다.")

    first = bakeries[0]
    return {
        "latitude": _to_float(first["latitude"]),
        "longitude": _to_float(first["longitude"]),
    }


def optimize_flagship_route(
    ranked_bakeries: List[Dict],
    user_location: Optional[Dict],
    max_spots: int = 10,
) -> Tuple[Dict, List[Dict]]:
    """
    1) 점수 순으로 정렬된 ranked_bakeries에서 상위 max_spots 후보를 고르고
    2) 시작점(user_location 또는 첫 매장)을 기준으로
    3) 거리 기반 경로 최적화(지하철 동선처럼)를 적용한 리스트를 반환합니다.

    반환:
    - start_point: 실제 시작점 (위경도)
    - optimized_bakeries: 순서가 최적화된 빵집 리스트
    """
    # 상위 N개만 사용 (예: 10곳)
    flagship = ranked_bakeries[:max_spots]

    if not flagship:
        return choose_start_point(user_location, []), []

    start_point = choose_start_point(user_location, flagship)
    optimized = optimize_route_by_distance(flagship, start_point)
    return start_point, optimized
