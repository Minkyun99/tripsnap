# location_module.py

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, Tuple

import requests

from schemas import LocationFilter


# --------------------------------------------------
#  위경도 거리 계산 (haversine)
# --------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    두 좌표(경위도) 사이의 거리를 km 단위로 계산.
    """
    R = 6371.0  # 지구 반지름 (km)

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# --------------------------------------------------
#  행정구역 메타데이터 보강
# --------------------------------------------------

CITY_PATTERN = re.compile(r"(대전|서울|부산|인천|광주|대구|울산|세종)[ ]*시?")
GU_PATTERN = re.compile(r"([가-힣]+구)")
DONG_PATTERN = re.compile(r"([가-힣0-9]+동)")


def _extract_city_district_from_address(addr: str) -> Tuple[str, str]:
    """
    도로명/지번 주소 문자열에서 (city, district)를 대략적으로 추출.
    예: "대전 서구 관저중로..." -> ("대전", "서구")
    """
    city = ""
    district = ""

    if not addr:
        return city, district

    m_city = CITY_PATTERN.search(addr)
    if m_city:
        city = m_city.group(1)

    m_gu = GU_PATTERN.search(addr)
    if m_gu:
        district = m_gu.group(1)
    else:
        m_dong = DONG_PATTERN.search(addr)
        if m_dong:
            district = m_dong.group(1)

    return city, district


def annotate_admin_areas(bakeries: List[Dict[str, Any]]) -> None:
    """
    각 매장에 '_city', '_district' 메타데이터를 채워 넣는다.
    """
    for b in bakeries:
        if "_city" in b and "_district" in b:
            continue

        addr = b.get("road_address") or b.get("jibun_address") or ""
        city, district = _extract_city_district_from_address(addr)

        if city:
            b["_city"] = city
        if district:
            b["_district"] = district


# --------------------------------------------------
#  Kakao 로컬 API 호출 (키워드 검색)
# --------------------------------------------------

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "d58a0c90acfbefb8a0a651c62c6fbd4c").strip()


def _kakao_keyword_search(query: str) -> Tuple[str, float, float]:
    """
    카카오 키워드 검색으로 POI(예: 대전역)를 좌표로 변환.
    반환: (place_name, lat, lon)
    """
    if not KAKAO_REST_API_KEY:
        return "", 0.0, 0.0

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": query, "size": 1}

    resp = requests.get(url, headers=headers, params=params, timeout=3)
    resp.raise_for_status()
    data = resp.json()

    docs = data.get("documents", [])
    if not docs:
        return "", 0.0, 0.0

    d0 = docs[0]
    name = d0.get("place_name") or query
    try:
        lat = float(d0["y"])
        lon = float(d0["x"])
    except Exception:
        return "", 0.0, 0.0

    return name, lat, lon


# --------------------------------------------------
#  위치 필터 적용
# --------------------------------------------------

def filter_bakeries_by_location(
    bakeries: List[Dict[str, Any]],
    loc_filter: LocationFilter,
) -> List[Dict[str, Any]]:
    """
    LocationFilter에 따라 빵집 리스트를 필터링.
    """
    if loc_filter is None or loc_filter.kind == "none":
        return list(bakeries)

    kind = loc_filter.kind

    # 도시 단위 필터 (예: 대전 전체)
    if kind == "city" and loc_filter.city:
        city = loc_filter.city
        result = []
        for b in bakeries:
            c = b.get("_city") or ""
            addr_concat = (b.get("road_address") or "") + " " + (b.get("jibun_address") or "")
            if c == city or city in addr_concat:
                result.append(b)
        return result

    # 구/동 단위 필터 (예: 유성구, 도안동)
    if kind == "district" and loc_filter.district:
        district = loc_filter.district
        result = []
        for b in bakeries:
            d = b.get("_district") or ""
            addr_concat = (b.get("road_address") or "") + " " + (b.get("jibun_address") or "")
            if d == district or district in addr_concat:
                result.append(b)
        return result

    # 포인트 기반(좌표 + 반경 km) 필터
    if kind == "point" and loc_filter.lat is not None and loc_filter.lon is not None:
        lat0 = loc_filter.lat
        lon0 = loc_filter.lon
        radius_km = loc_filter.radius_km or 5.0  # 기본 5km

        result = []
        for b in bakeries:
            try:
                lat = float(b.get("latitude", 0) or 0)
                lon = float(b.get("longitude", 0) or 0)
            except Exception:
                continue
            if lat == 0 and lon == 0:
                continue

            dist = haversine(lat0, lon0, lat, lon)
            if dist <= radius_km:
                result.append(b)

        return result

    # 그 외: 필터링하지 않고 그대로 반환
    return list(bakeries)


# --------------------------------------------------
#  사용자 질의에서 위치 파싱
# --------------------------------------------------

def extract_location_from_query(query: str) -> Tuple[LocationFilter, List[str]]:
    """
    사용자 자연어 질의에서 위치 정보를 추출하여 LocationFilter로 변환.
    - '대전역 근처 ...' / '... 대전역 근처 ...' → 카카오 키워드 검색으로 point 필터
    - '도안동 근처', '봉명동 근처' 등도 카카오로 point 필터
    - 그 외 '유성구', '서구', '동구' 등은 행정구역(district) 필터
    - 아무것도 못 찾으면 city='대전' 전체로 처리
    """
    logs: List[str] = []

    text = query.strip()

    # --------------------------------------------------
    # 1) '○○역 근처', '○○동 근처' 패턴 우선 처리
    #    - 핵심은 '근처' 바로 앞의 단어만 떼오는 것
    # --------------------------------------------------

    # 1-1) '역 근처' 패턴 → "대전역"만 추출
    m_station = re.search(r"([가-힣0-9A-Za-z]+역)\s*근처", text)
    if m_station:
        name = m_station.group(1)
        place, lat, lon = _kakao_keyword_search(name)
        if lat != 0.0 and lon != 0.0:
            logs.append(f"   📍 Kakao 위치 인식: '{place}' → lat={lat}, lon={lon}")
            # 도보/대중교통 여부는 answer_query 쪽에서 판단하지만,
            # 여기서는 반경만 지정해 둔다 (도보 기준은 약 1.3km 권장)
            loc_filter = LocationFilter(
                kind="point",
                lat=lat,
                lon=lon,
                radius_km=1.3,  # 기본적으로 도보 20분 이내 ~ 1.3km
            )
            return loc_filter, logs
        else:
            logs.append(f"   ⚠️ Kakao 위치 검색 실패: '{name}'")

    # 1-2) '동 근처' 패턴 → "도안동", "봉명동" 등만 추출
    m_dong = re.search(r"([가-힣0-9A-Za-z]+동)\s*근처", text)
    if m_dong:
        name = m_dong.group(1)
        place, lat, lon = _kakao_keyword_search(name)
        if lat != 0.0 and lon != 0.0:
            logs.append(f"   📍 Kakao 위치 인식: '{place}' → lat={lat}, lon={lon}")
            loc_filter = LocationFilter(
                kind="point",
                lat=lat,
                lon=lon,
                radius_km=1.3,  # 도보 20분 권장 반경
            )
            return loc_filter, logs
        else:
            logs.append(f"   ⚠️ Kakao 위치 검색 실패: '{name}'")

    # --------------------------------------------------
    # 2) '○○역에서', '○○역을 중심으로'와 같은 패턴도 보조 처리
    # --------------------------------------------------
    m_station2 = re.search(r"([가-힣0-9A-Za-z]+역)", text)
    if m_station2:
        name = m_station2.group(1)
        place, lat, lon = _kakao_keyword_search(name)
        if lat != 0.0 and lon != 0.0:
            logs.append(f"   📍 Kakao 위치 인식: '{place}' → lat={lat}, lon={lon}")
            loc_filter = LocationFilter(
                kind="point",
                lat=lat,
                lon=lon,
                radius_km=1.3,  # 도보 20분 권장 반경
            )
            return loc_filter, logs
        else:
            logs.append(f"   ⚠️ Kakao 위치 검색 실패: '{name}'")

    # --------------------------------------------------
    # 3) '유성구', '서구', '동구', '중구' 등 행정구역(district) 인식
    # --------------------------------------------------
    # 대전 기준 예시지만, 확장 가능.
    district_candidates = ["유성구", "서구", "동구", "중구", "대덕구"]
    for dist in district_candidates:
        if dist in text:
            logs.append(f"   📍 행정구역 기반 검색(범위): district={dist}")
            loc_filter = LocationFilter(
                kind="district",
                city="대전",
                district=dist,
            )
            return loc_filter, logs

    # --------------------------------------------------
    # 4) '대전', '서울' 등 도시 단위 인식
    # --------------------------------------------------
    city_candidates = ["대전", "서울", "부산", "인천", "광주", "대구", "울산", "세종"]
    for city in city_candidates:
        if city in text:
            logs.append(f"   📍 행정구역 기반 검색(범위): city={city}")
            loc_filter = LocationFilter(
                kind="city",
                city=city,
            )
            return loc_filter, logs

    # --------------------------------------------------
    # 5) 아무 위치 정보도 찾지 못한 경우
    #    - 현재 데이터가 대부분 대전이라면, 대전 전체로 가정
    # --------------------------------------------------
    logs.append("   ℹ️ 위치/행정구역 언급 없음 → 대전 전체(데이터 전체) 기준")
    loc_filter = LocationFilter(
        kind="city",
        city="대전",
    )
    return loc_filter, logs
