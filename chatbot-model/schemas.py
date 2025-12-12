# schemas.py
from dataclasses import dataclass
from datetime import date, time as dtime
from typing import Optional


@dataclass
class DateTimeConstraint:
    """
    사용자 질의에서 추출한 방문 기간/시간 제약.
    """
    has_date_range: bool
    start_date: Optional[date]
    end_date: Optional[date]
    start_time: Optional[dtime]
    end_time: Optional[dtime]
    # 날짜/시간 언급이 없을 때 → 현재 시각 기준으로만 필터링할지 여부
    use_now_if_missing: bool


@dataclass
class LocationFilter:
    """
    위치 필터
    kind:
      - "none"      : 위치 언급 없음 → 대전 전체
      - "city"      : 시 단위 (예: 대전)
      - "district"  : 구 단위 (예: 유성구)
      - "dong"      : 동 단위 (예: 봉명동)
      - "point"     : 특정 지점 기준 반경 radius_km 이내
    """
    kind: str
    value: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    radius_km: float = 3.0
