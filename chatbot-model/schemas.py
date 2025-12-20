# schemas.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Optional, Literal


@dataclass
class DateTimeConstraint:
    """
    사용자 질의에서 파싱한 날짜/시간 제약을 담는 구조체.
    - has_date_range: 날짜 범위가 명시되었는지 여부
    - start_date / end_date: 방문 시작/종료 날짜
    - start_time / end_time: 방문 시작/종료 시간
    - use_now_if_missing: 날짜/시간이 없고 '지금/바로' 의도가 있을 때, 현재 시각 기준으로 처리할지 여부
    """
    has_date_range: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    use_now_if_missing: bool = False


@dataclass
class LocationFilter:
    """
    위치 필터 정보.
    kind:
      - "none"     : 위치 제약 없음
      - "city"     : 도시 단위 필터 (예: 대전 전체)
      - "district" : 행정구역(구/동) 필터 (예: 유성구, 도안동)
      - "point"    : 좌표 + 반경 km 필터 (예: 대전역 근처 2km)
    """
    kind: Literal["none", "city", "district", "point"] = "none"

    # 행정구역 기반 필터용
    city: Optional[str] = None          # 예: "대전"
    district: Optional[str] = None      # 예: "유성구", "도안동"

    # 포인트 기반 필터용
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_km: Optional[float] = None   # None이면 기본값(내부 로직) 사용
