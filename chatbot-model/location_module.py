# location_module.py
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from schemas import LocationFilter

# 대전 5개 구
DAEJEON_DISTRICTS = ["동구", "중구", "서구", "유성구", "대덕구"]

# Kakao 로컬 REST API 키 (환경변수 권장)
KAKAO_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "").strip()


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 거리(km) 계산."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def annotate_admin_areas(bakeries: List[Dict[str, Any]]) -> None:
    """
    dessert_en.json의 district / jibun_address를 사용해서
    _city, _district, _dong 메타 필드를 추가.
    """
    for b in bakeries:
        district = (b.get("district") or "").strip()
        b["_district"] = district if district else None

        jibun = b.get("jibun_address", "") or ""
        dong = None
        parts = jibun.split()
        for p in parts:
            if p.endswith("동"):
                dong = p
                break
        b["_dong"] = dong
        b["_city"] = "대전"  # 데이터 자체가 대전 지역이라는 가정


def search_kakao_location(place: str) -> Optional[Tuple[float, float, str]]:
    """
    Kakao 로컬 API로 위치 검색.
    성공 시 (lat, lon, place_name) 반환, 실패 시 None.
    """
    if not KAKAO_API_KEY:
        return None

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": place, "page": 1, "size": 1}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=3)
        if resp.status_code != 200:
            return None
        data = resp.json()
        docs = data.get("documents", [])
        if not docs:
            return None
        d = docs[0]
        lat = float(d["y"])
        lon = float(d["x"])
        name = d.get("place_name", place)
        return lat, lon, name
    except Exception:
        return None


def extract_location_from_query(query: str) -> Tuple[LocationFilter, List[str]]:
    """
    질의에서 위치 조건을 뽑아 LocationFilter로 반환.
    로그용 메시지 리스트도 함께 반환.
    """
    logs: List[str] = []
    text = query.strip()

    # 1) "대전역 근처", "시청 주변" 등 → Kakao 검색 (point)
    m_near = re.search(r"(.+?)(근처|주변)", text)
    if m_near:
        place = m_near.group(1).strip()
        loc = search_kakao_location(place)
        if loc:
            lat, lon, pname = loc
            logs.append(f"   📍 Kakao 위치 인식: '{pname}' → lat={lat}, lon={lon}")
            return LocationFilter(kind="point", lat=lat, lon=lon, radius_km=3.0), logs
        else:
            logs.append(f"   ⚠️ Kakao 위치 검색 실패: '{place}'")

    # 2) 행정구역(시/구/동) 인식
    city = "대전" if "대전" in text else None

    district = None
    for d in DAEJEON_DISTRICTS:
        if d in text:
            district = d
            break

    dong = None
    m_dong = re.search(r"([가-힣0-9]+동)", text)
    if m_dong:
        dong = m_dong.group(1)

    if dong:
        logs.append(f"   📍 행정구역 기반 검색(범위): dong={dong}")
        return LocationFilter(kind="dong", value=dong), logs
    elif district:
        logs.append(f"   📍 행정구역 기반 검색(범위): district={district}")
        return LocationFilter(kind="district", value=district), logs
    elif city:
        logs.append(f"   📍 행정구역 기반 검색(범위): city={city}")
        return LocationFilter(kind="city", value=city), logs
    else:
        logs.append("   ℹ️ 위치/행정구역 언급 없음 → 대전 전체(데이터 전체) 기준")
        return LocationFilter(kind="none"), logs


def filter_bakeries_by_location(
    bakeries: List[Dict[str, Any]],
    loc: LocationFilter,
) -> List[Dict[str, Any]]:
    """
    LocationFilter에 따라 후보 매장을 필터링.
    """
    if loc.kind == "none":
        return bakeries

    if loc.kind == "city":
        return [b for b in bakeries if b.get("_city") == loc.value]

    if loc.kind == "district":
        return [b for b in bakeries if b.get("_district") == loc.value]

    if loc.kind == "dong":
        return [b for b in bakeries if b.get("_dong") == loc.value]

    if loc.kind == "point" and loc.lat is not None and loc.lon is not None:
        results: List[Dict[str, Any]] = []
        for b in bakeries:
            try:
                lat = float(b.get("latitude", 0) or 0)
                lon = float(b.get("longitude", 0) or 0)
            except Exception:
                continue
            if lat == 0 and lon == 0:
                continue
            dist = haversine(loc.lat, loc.lon, lat, lon)
            if dist <= loc.radius_km:
                b["_distance_km"] = dist
                results.append(b)
        return results

    return bakeries
