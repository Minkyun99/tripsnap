# naver_hours_checker.py
import re
from datetime import date
from typing import Dict, Tuple, Optional

import requests
from bs4 import BeautifulSoup

# 간단한 in-memory 캐시: (url, yyyymmdd) -> bool
# True  = 해당 날짜에 임시휴무
# False = 임시휴무 아님(정상 영업 또는 조기마감 안내만 있는 경우)
_temp_closure_cache: Dict[Tuple[str, str], bool] = {}


def _fetch_naver_html(url: str) -> Optional[str]:
    """
    네이버 플레이스 HTML을 가져온다.
    실패 시 None.
    """
    if not url:
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"⚠️ 네이버 영업시간 HTML 요청 실패 ({url}): {e}")
        return None


def _parse_temp_closure(html: str, target: date) -> bool:
    """
    네이버 플레이스 HTML에서 임시휴무 여부를 판별한다.

    - '임시휴무'라는 단어가 포함되어 있으면 거의 확실히 임시휴무로 간주
    - '휴무' + 날짜 조합이 보이면 해당 날짜 임시휴무로 간주
    - '정기휴무(매주 수요일)' 처럼 '정기휴무'는 여기서 처리하지 않고,
      정기휴무는 기존 time_module / dessert_en.json 로직에 맡긴다.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) 먼저 영업시간 패널(anchor) 쪽 텍스트 위주로 본다
    panel = soup.find("a", class_="gKP9i")
    if panel is not None:
        text = panel.get_text(" ", strip=True)
    else:
        # fallback: 전체 페이지 텍스트
        text = soup.get_text(" ", strip=True)

    # 전부 소문자/대문자 섞여 있어도 상관없도록
    # (한글이므로 크게 의미는 없지만, 안전하게)
    norm = text

    # 1) '임시휴무'가 들어가면 해당 날짜 임시휴무로 본다
    if "임시휴무" in norm:
        return True

    # 2) '오늘 임시휴무', '오늘 휴무' 같은 패턴
    #    (네이버에서 보통 '오늘은 휴무입니다' 같은 문구로 뜨는 경우)
    #    여기서는 단순히 '오늘' + '휴무' 동시 출현을 체크
    if "오늘" in norm and "휴무" in norm:
        # 오늘 날짜 질의일 가능성이 크므로 True
        return True

    # 3) 대상 날짜를 문자열로 만들어서 '12월 15일 휴무' 같은 패턴 잡기
    month_day_kr = f"{target.month}월 {target.day}일"
    # 예: '12월 15일 휴무', '12월 15일 임시휴무'
    if month_day_kr in norm and "휴무" in norm:
        return True

    # 4) '휴무 안내' 등 단어가 있지만 정확한 날짜가 없으면
    #    여기서 임시휴무로 단정 짓지 않고 False.
    #    (정기휴무 / 과거 안내일 수 있음)
    #    필요하면 여기에 추가 패턴을 넣을 수 있다.
    return False


def is_temporarily_closed_by_naver(url: str, target_date: date) -> bool:
    """
    dessert_en.json의 url(네이버 플레이스) 기준으로
    특정 날짜(target_date)에 임시휴무인지 판별.

    - 내부 캐시를 사용해 같은 가게/날짜에 대해 반복 요청 최소화
    - 네이버 HTML 구조 변경에 따라 후에 파서만 수정하면 전체 로직은 그대로 유지 가능
    """
    if not url:
        return False

    key = (url, target_date.strftime("%Y%m%d"))
    if key in _temp_closure_cache:
        return _temp_closure_cache[key]

    html = _fetch_naver_html(url)
    if not html:
        _temp_closure_cache[key] = False
        return False

    closed = _parse_temp_closure(html, target_date)
    _temp_closure_cache[key] = closed
    return closed
