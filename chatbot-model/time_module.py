# time_module.py
import re
from datetime import date, datetime, time as dtime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from schemas import DateTimeConstraint

class DateTimeParser:
    """
    시간/날짜 관련 함수를 감싸는 래퍼 클래스.
    기존 코드에서 self.time_parser.extract_datetime_constraint(query)
    형태로 호출할 수 있게 해주는 호환용 클래스입니다.
    """

    def extract_datetime_constraint(self, query: str):
        # 기존 parse_date_time_from_query를 그대로 재사용
        return parse_date_time_from_query(query)

    def is_open_at(self, business_hours, dt):
        return is_open_at(business_hours, dt)

    def is_available_in_period(self, business_hours, start_dt, end_dt):
        return is_available_in_period(business_hours, start_dt, end_dt)
    

WEEKDAYS = ["monday", "tuesday", "wednesday",
            "thursday", "friday", "saturday", "sunday"]

KOREAN_WEEKDAY_MAP = {
    0: "월요일",
    1: "화요일",
    2: "수요일",
    3: "목요일",
    4: "금요일",
    5: "토요일",
    6: "일요일",
}


def parse_business_hours_field(
    field: str
) -> Optional[Tuple[dtime, dtime, Optional[dtime]]]:
    """
    예) '11:00 - 22:00 (21:15 라스트오더)' → (11:00, 22:00, 21:15)
    """
    text = field.strip()
    if any(x in text for x in ["휴무", "쉼", "휴점", "정기휴무"]):
        return None

    m = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", text)
    if not m:
        return None

    oh, om, ch, cm = map(int, m.groups())

    # 24:00 처리
    if ch == 24 and cm == 0:
        ch, cm = 23, 59

    if not (0 <= oh <= 23 and 0 <= om <= 59 and 0 <= ch <= 23 and 0 <= cm <= 59):
        return None

    open_t = dtime(hour=oh, minute=om)
    close_t = dtime(hour=ch, minute=cm)

    last_order_t: Optional[dtime] = None

    # (21:15 라스트오더) 형식
    m_lo = re.search(r"(\d{1,2}):(\d{2})\s*라스트오더", text)
    if m_lo:
        l_h, l_m = map(int, m_lo.groups())
        if 0 <= l_h <= 23 and 0 <= l_m <= 59:
            last_order_t = dtime(hour=l_h, minute=l_m)
    else:
        # '21시 15분 라스트오더' 형식
        m_lo2 = re.search(r"(\d{1,2})\s*시\s*(\d{1,2})?\s*분?\s*라스트오더", text)
        if m_lo2:
            l_h = int(m_lo2.group(1))
            l_m = int(m_lo2.group(2) or 0)
            if 0 <= l_h <= 23 and 0 <= l_m <= 59:
                last_order_t = dtime(hour=l_h, minute=l_m)

    return open_t, close_t, last_order_t


def build_business_hours_index(
    bakeries: List[Dict[str, Any]]
) -> Dict[str, Dict[int, Dict[str, Optional[dtime]]]]:
    """
    dessert_en.json의 monday~sunday 필드를 파싱해서 요일별 영업시간 인덱스를 만든다.
    return: { bakery_name: { weekday_int: {"open":t, "close":t, "last_order":t or None}, ... }, ... }
    """
    index: Dict[str, Dict[int, Dict[str, Optional[dtime]]]] = {}

    for b in bakeries:
        name = b.get("name") or b.get("slug_en") or ""
        if not name:
            continue

        weekly_info: Dict[int, Dict[str, Optional[dtime]]] = {}
        has_any = False

        for idx, wd in enumerate(WEEKDAYS):
            field = (b.get(wd) or "").strip()
            if not field:
                continue

            parsed = parse_business_hours_field(field)
            if parsed is None:
                continue

            open_t, close_t, last_order_t = parsed
            weekly_info[idx] = {
                "open": open_t,
                "close": close_t,
                "last_order": last_order_t,
            }
            has_any = True

        if has_any:
            index[name] = weekly_info

    return index


def parse_date_time_from_query(query: str) -> DateTimeConstraint:
    """
    쿼리에서 2025.12.25 ~ 2025.12.26, 8시, 밤 9시, 21:00 같은 패턴을 추출.
    """
    text = query.replace(" ", "")
    date_matches = list(re.finditer(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", text))

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    has_date_range = False

    if len(date_matches) >= 2:
        y1, m1, d1 = map(int, date_matches[0].groups())
        y2, m2, d2 = map(int, date_matches[-1].groups())
        start_date = date(y1, m1, d1)
        end_date = date(y2, m2, d2)
        has_date_range = True
    elif len(date_matches) == 1:
        y, m, d = map(int, date_matches[0].groups())
        start_date = end_date = date(y, m, d)
        has_date_range = True

    # 시간
    times: List[Tuple[dtime, int]] = []

    # 21:00
    for m in re.finditer(r"(\d{1,2}):(\d{2})", text):
        h, mm = map(int, m.groups())
        if 0 <= h <= 23 and 0 <= mm <= 59:
            times.append((dtime(hour=h, minute=mm), m.start()))

    # (밤 9시, 오후 3시 30분 등)
    for m in re.finditer(r"(오전|오후|밤|저녁|새벽)?(\d{1,2})시(\d{1,2})?분?", text):
        ampm = m.group(1) or ""
        h = int(m.group(2))
        mm = int(m.group(3) or 0)
        if "오후" in ampm or "밤" in ampm or "저녁" in ampm:
            if h < 12:
                h += 12
        elif "새벽" in ampm and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= mm <= 59:
            times.append((dtime(hour=h, minute=mm), m.start()))

    times = sorted(times, key=lambda x: x[1])
    start_time: Optional[dtime] = None
    end_time: Optional[dtime] = None

    if len(times) >= 2:
        start_time = times[0][0]
        end_time = times[-1][0]
    elif len(times) == 1:
        t, idx = times[0]
        if "까지" in text[idx: idx + 10]:
            end_time = t
        elif "부터" in text[max(0, idx - 10): idx + 3]:
            start_time = t
        else:
            end_time = t

    use_now_if_missing = not has_date_range and (start_time is None and end_time is None)

    return DateTimeConstraint(
        has_date_range=has_date_range,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        use_now_if_missing=use_now_if_missing,
    )


def is_open_at(
    bakery: Dict[str, Any],
    dt: datetime,
    business_hours_index: Dict[str, Dict[int, Dict[str, Optional[dtime]]]],
) -> bool:
    """
    특정 datetime에 '빵 구매 가능' 여부 (라스트오더 포함).
    """
    name = bakery.get("name") or bakery.get("slug_en") or ""
    if not name or name not in business_hours_index:
        return False

    weekday = dt.weekday()
    day_info = business_hours_index[name].get(weekday)
    if not day_info:
        return False

    open_t = day_info.get("open")
    close_t = day_info.get("close")
    last_t = day_info.get("last_order")
    if not open_t or not close_t:
        return False

    effective_close = last_t or close_t
    current = dt.time()

    return (open_t <= current <= effective_close)


def is_available_in_period(
    bakery: Dict[str, Any],
    constraint: DateTimeConstraint,
    business_hours_index: Dict[str, Dict[int, Dict[str, Optional[dtime]]]],
) -> Tuple[bool, Optional[dtime]]:
    """
    기간/시간 제약에서 '빵 구매 가능' 여부.
    반환: (해당 기간 중 최소 하루라도 가능 여부, 마지막 날짜 기준 라스트오더/마감시간)
    """
    name = bakery.get("name") or bakery.get("slug_en") or ""
    if not name or name not in business_hours_index:
        return False, None

    weekly = business_hours_index[name]

    # 날짜 범위가 없는 경우: 요일 패턴만 보고 가능 여부 판단
    if not constraint.has_date_range:
        if constraint.start_time is None and constraint.end_time is None:
            return True, None

        for wd in range(7):
            day_info = weekly.get(wd)
            if not day_info:
                continue
            open_t = day_info.get("open")
            close_t = day_info.get("close")
            last_t = day_info.get("last_order")
            if not open_t or not close_t:
                continue
            effective_close = last_t or close_t

            if constraint.start_time and constraint.end_time:
                if (open_t <= constraint.end_time and
                        effective_close >= constraint.start_time):
                    return True, effective_close
            elif constraint.start_time:
                if effective_close >= constraint.start_time:
                    return True, effective_close
            elif constraint.end_time:
                if open_t <= constraint.end_time:
                    return True, effective_close
        return False, None

    # 날짜 범위가 있는 경우
    current_date = constraint.start_date
    last_day_close: Optional[dtime] = None

    while current_date and constraint.end_date and current_date <= constraint.end_date:
        wd = current_date.weekday()
        day_info = weekly.get(wd)
        if day_info:
            open_t = day_info.get("open")
            close_t = day_info.get("close")
            last_t = day_info.get("last_order")
            if open_t and close_t:
                effective_close = last_t or close_t

                if constraint.start_time and constraint.end_time:
                    if (open_t <= constraint.end_time and
                            effective_close >= constraint.start_time):
                        if current_date == constraint.end_date:
                            last_day_close = effective_close
                        return True, last_day_close
                elif constraint.start_time:
                    if effective_close >= constraint.start_time:
                        if current_date == constraint.end_date:
                            last_day_close = effective_close
                        return True, last_day_close
                elif constraint.end_time:
                    if open_t <= constraint.end_time:
                        if current_date == constraint.end_date:
                            last_day_close = effective_close
                        return True, last_day_close
                else:
                    if current_date == constraint.end_date:
                        last_day_close = effective_close
                    return True, last_day_close

        current_date += timedelta(days=1)

    return False, None
