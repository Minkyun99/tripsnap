# location_module.py

from __future__ import annotations

import math
import os
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from urllib.parse import quote

from schemas import LocationFilter, TransportMode

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "d58a0c90acfbefb8a0a651c62c6fbd4c").strip()

# --------------------------------------------------
#  기본 경로 설정 & 대전 지하철 1호선 JSON 경로
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# 1순위: location_module.py와 같은 폴더
SUBWAY_JSON_PATH = BASE_DIR / "daejeon_subway_line1.json"

# 2순위: BASE_DIR / "data" / ...
if not SUBWAY_JSON_PATH.exists():
    SUBWAY_JSON_PATH = BASE_DIR / "data" / "daejeon_subway_line1.json"


# --------------------------------------------------
#  전역 Subway Cache
# --------------------------------------------------
DAEJEON_SUBWAY_STATIONS: List[Dict[str, Any]] = []


# --------------------------------------------------
#  이동 수단 파싱
# --------------------------------------------------


def detect_transport_mode(user_query: str) -> Tuple[TransportMode, List[str]]:
    logs: List[str] = []
    q = user_query.replace(" ", "")

    if any(kw in q for kw in ["도보로", "도보를이용", "걸어서", "걸어가", "걷기"]):
        logs.append("🚶 이동 수단 인식: 도보 기준 동선 최적화")
        return TransportMode.WALK, logs

    if any(kw in q for kw in ["지하철로", "지하철을이용", "전철로", "전철을이용", "지하철", "전철"]):
        logs.append("🚇 이동 수단 인식: 지하철 기준 동선 최적화")
        return TransportMode.SUBWAY, logs

    if "버스" in q:
        logs.append("🚌 이동 수단 인식: 버스 기준 동선 최적화")
        return TransportMode.BUS, logs

    if "대중교통" in q:
        logs.append("🚉🚌 이동 수단 인식: 지하철+버스 혼합(대중교통) 기준 동선 최적화")
        return TransportMode.TRANSIT_MIXED, logs

    if any(kw in q for kw in ["차로", "운전해서", "자차로", "드라이브해서", "자차", "자동차", "운전"]):
        logs.append("🚗 이동 수단 인식: 자차 기준 동선 최적화")
        return TransportMode.CAR, logs

    logs.append("ℹ️ 이동 수단 명시 없음 → 기본값 대중교통(지하철+버스 혼합)")
    return TransportMode.TRANSIT_MIXED, logs


# --------------------------------------------------
#  위경도 거리 계산 (haversine)
# --------------------------------------------------

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
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




def _kakao_keyword_search(query: str) -> Tuple[str, float, float]:
    api_key = KAKAO_REST_API_KEY
    if not api_key:
        return "", 0.0, 0.0

    headers = {"Authorization": f"KakaoAK {api_key}"}
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    try:
        resp = requests.get(url, headers=headers, params={"query": query}, timeout=5)
        data = resp.json()
        docs = data.get("documents", [])
        if not docs:
            return "", 0.0, 0.0

        place = docs[0]
        y = float(place.get("y", 0.0))
        x = float(place.get("x", 0.0))
        name = place.get("place_name", query)

        return name, y, x
    except Exception:
        return "", 0.0, 0.0

# --------------------------------------------------
#  대전 1호선 역 정보 JSON 로딩
# --------------------------------------------------

def load_daejeon_subway_stations_from_json() -> List[Dict[str, Any]]:
    stations: List[Dict[str, Any]] = []

    if not SUBWAY_JSON_PATH.exists():
        print(f"⚠️ 지하철 JSON 파일 없음: {SUBWAY_JSON_PATH}")
        return stations

    try:
        with SUBWAY_JSON_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"⚠️ 지하철 JSON 파싱 실패: {e}")
        return stations

    for item in data:
        name = (item.get("station_name") or item.get("name") or "").strip()
        address = (item.get("address") or "").strip()
        if not name:
            continue

        lat = item.get("lat")
        lon = item.get("lon")

        lat_f = lon_f = None

        if lat is not None and lon is not None:
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except Exception:
                lat_f = lon_f = None

        if lat_f is None or lon_f is None:
            queries = [f"대전 {name}", name]
            if address:
                queries.append(address)

            for q in queries:
                _, y, x = _kakao_keyword_search(q)
                if y != 0.0 and x != 0.0:
                    lat_f = y
                    lon_f = x
                    break

        if lat_f is None or lon_f is None:
            continue

        stations.append(
            {
                "name": name,
                "address": address,
                "lat": float(lat_f),
                "lon": float(lon_f),
            }
        )

    print(f"🚇 대전 1호선 역 데이터 로드: {len(stations)}개")
    return stations




def get_subway_stations() -> List[Dict[str, Any]]:
    global DAEJEON_SUBWAY_STATIONS
    if not DAEJEON_SUBWAY_STATIONS:
        DAEJEON_SUBWAY_STATIONS = load_daejeon_subway_stations_from_json()
    return DAEJEON_SUBWAY_STATIONS



# --------------------------------------------------
#  가장 가까운 지하철역 찾기 (JSON + haversine)
# --------------------------------------------------

def find_nearest_subway_station(
    lat: float,
    lon: float,
    radius_m: int = 1500,
) -> Tuple[str, float, float]:
    stations = get_subway_stations()
    if not stations:
        return "", 0.0, 0.0

    nearest = None
    min_dist = float("inf")

    for st in stations:
        sy = st.get("lat")
        sx = st.get("lon")
        if sy is None or sx is None:
            continue

        try:
            d = haversine(lat, lon, float(sy), float(sx))
        except Exception:
            continue

        if d < min_dist:
            min_dist = d
            nearest = st

    if nearest is None:
        return "", 0.0, 0.0

    if min_dist * 1000 > radius_m:
        return "", 0.0, 0.0

    return nearest["name"], float(nearest["lat"]), float(nearest["lon"])


# --------------------------------------------------
#  Kakao 지도 링크 빌더
# --------------------------------------------------

def build_kakao_place_url(name: str, lat: float, lon: float) -> str:
    """
    Kakao 지도에서 '해당 위치를 바로 표시'하는 URL 생성.
    예: https://map.kakao.com/link/map/이름,위도,경도
    """
    if not name or not lat or not lon:
        return ""
    qname = quote(name)
    return f"https://map.kakao.com/link/map/{qname},{lat},{lon}"


def build_kakao_route_url(
    mode: str,
    origin_name: str,
    origin_lat: float,
    origin_lon: float,
    dest_name: str,
    dest_lat: float,
    dest_lon: float,
) -> str:
    """
    Kakao 지도 '길찾기 바로가기' URL 생성.
    mode: 'car' | 'traffic' | 'walk' | 'bicycle'
    예: https://map.kakao.com/link/by/traffic/출발이름,위도,경도/도착이름,위도,경도
    """
    if not origin_name or not dest_name:
        return ""
    q_origin = quote(origin_name)
    q_dest = quote(dest_name)
    return (
        f"https://map.kakao.com/link/by/{mode}/"
        f"{q_origin},{origin_lat},{origin_lon}/"
        f"{q_dest},{dest_lat},{dest_lon}"
    )


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

    # 1) '○○역 근처'
    m_station = re.search(r"([가-힣0-9A-Za-z]+역)\s*근처", text)
    if m_station:
        name = m_station.group(1)
        place, lat, lon = _kakao_keyword_search(name)
        if lat != 0.0 and lon != 0.0:
            logs.append(f"   📍 Kakao 위치 인식: '{place}' → lat={lat}, lon={lon}")
            loc_filter = LocationFilter(
                kind="point",
                lat=lat,
                lon=lon,
                radius_km=1.3,  # 도보 20분 내외
            )
            return loc_filter, logs
        else:
            logs.append(f"   ⚠️ Kakao 위치 검색 실패: '{name}'")

    # 2) '○○동 근처'
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
                radius_km=1.3,
            )
            return loc_filter, logs
        else:
            logs.append(f"   ⚠️ Kakao 위치 검색 실패: '{name}'")

    # 3) '○○역에서', '○○역을 중심으로' 등 역 단어만 있는 케이스
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
                radius_km=1.3,
            )
            return loc_filter, logs
        else:
            logs.append(f"   ⚠️ Kakao 위치 검색 실패: '{name}'")

    # 4) '유성구', '서구', '동구', '중구', '대덕구'
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

    # 5) '대전', '서울' 등 도시 단위
    city_candidates = ["대전", "서울", "부산", "인천", "광주", "대구", "울산", "세종"]
    for city in city_candidates:
        if city in text:
            logs.append(f"   📍 행정구역 기반 검색(범위): city={city}")
            loc_filter = LocationFilter(
                kind="city",
                city=city,
            )
            return loc_filter, logs

    # 6) 아무 위치 정보도 없으면, 기본값: 대전 전체
    logs.append("   ℹ️ 위치/행정구역 언급 없음 → 대전 전체(데이터 전체) 기준")
    loc_filter = LocationFilter(
        kind="city",
        city="대전",
    )
    return loc_filter, logs
