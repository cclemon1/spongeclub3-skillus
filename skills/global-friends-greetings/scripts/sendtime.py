#!/usr/bin/env python3
"""발송자 현지시간 기준으로 발송 시각을 계산한다. 기본값은 한국시간(KST).

인사말은 '받는 쪽에서 언제 읽히느냐'가 전부다. 사우디 거래처가 이드 아침에 폰을 켰을 때
메시지가 이미 와 있는 것과, 그날 저녁에 도착하는 것은 완전히 다른 인상이다.
문제는 보내는 사람이 다른 시간대에 앉아 있다는 것 — 상대의 오전 8시가 내 시계로 몇 시인지는
나라마다 다르고, 서머타임 때문에 계절마다 또 달라진다. 그래서 스크립트가 계산한다.

발송자가 한국이 아니면 --home 으로 바꾼다:  --home Europe/Berlin

핵심 출력 세 가지:
  1. 전날 저녁 도착  — 기념일 전에 미리 닿게 (내 시계 기준 발송 시각)
  2. 당일 아침 도착  — 기념일 당일 아침 인박스 맨 위 (내 시계 기준 발송 시각)
  3. 왓츠앱 안전대   — 상대 현지 09~21시에 해당하는 내 시계 구간. 이 밖에 보내면 현지 새벽에
                      폰이 울린다. 이메일은 언제 보내도 되지만 왓츠앱은 아니다.

사용법
  sendtime.py --country SA --date 2027-03-20
  sendtime.py --country US,DE,VN,BR --date 2026-12-25
  sendtime.py --tz America/Los_Angeles --date 2026-12-25
  sendtime.py --country SA --date 2027-03-20 --json
  sendtime.py --country SA --date 2027-03-20 --home America/New_York
  sendtime.py --country SA --date 2027-03-20 --home America/New_York
"""

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, time, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    sys.exit("Python 3.9+ 필요 (zoneinfo)")

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRIES = os.path.join(os.path.dirname(HERE), "data", "countries.csv")
HOME_TZ = "Asia/Seoul"   # 발송자 시간대. --home 으로 바꾼다.


def home_zone():
    return ZoneInfo(HOME_TZ)


def home_label(instant=None):
    """KST, CET 같은 짧은 이름. 없으면 타임존 이름을 그대로 쓴다."""
    try:
        name = (instant or datetime.now(home_zone())).astimezone(home_zone()).tzname()
        if name and not name.startswith(("+", "-", "UTC")):
            return name
    except Exception:
        pass
    return HOME_TZ.split("/")[-1]

# 도착 목표 시각(현지 기준). 왜 이 시각인가:
#  - 08:00 : 출근 직후 인박스 최상단. 그 전(새벽)에 보내면 밤새 온 메일에 밀린다.
#  - 19:00 : 전날 저녁, 일과가 끝나고 폰을 보는 시간. "미리 챙겼다"는 인상이 남는다.
ARRIVE_MORNING = time(8, 0)
ARRIVE_EVE = time(19, 0)
# 왓츠앱은 개인 폰이 울린다. 현지 09~21시를 벗어나면 보내지 않는다.
WA_OPEN, WA_CLOSE = time(9, 0), time(21, 0)
# 발송자 업무시간. 이 밖이면 예약 발송을 권해야 한다.
HOME_OPEN, HOME_CLOSE = time(9, 0), time(18, 0)

WD = ["월", "화", "수", "목", "금", "토", "일"]


def load_countries():
    if not os.path.exists(COUNTRIES):
        return {}
    with open(COUNTRIES, encoding="utf-8") as f:
        return {r["iso2"].strip().upper(): r for r in csv.DictReader(f)}


def to_home(local_dt_naive, tz):
    """상대 현지 naive datetime → 발송자 시간대의 aware datetime. 서머타임은 zoneinfo가 처리한다."""
    return local_dt_naive.replace(tzinfo=ZoneInfo(tz)).astimezone(home_zone())


def fmt(dt, ref_day=None):
    """발송자 시각을 사람이 읽는 형태로. 기준일과 다르면 며칠 차이인지 붙인다."""
    s = f"{dt.month}/{dt.day}({WD[dt.weekday()]}) {dt:%H:%M}"
    if ref_day is not None:
        delta = (dt.date() - ref_day).days
        if delta == -1:
            s += " [전날]"
        elif delta == 1:
            s += " [익일]"
        elif delta != 0:
            s += f" [{delta:+d}일]"
    return s


def in_home_hours(dt):
    return dt.weekday() < 5 and HOME_OPEN <= dt.time() <= HOME_CLOSE


def fmt_offset(hours):
    """UTC+5:30, UTC+5:45 같은 30/45분 시차를 반올림 없이 표기한다.

    인도(+5:30)·네팔(+5:45)·미얀마(+6:30)·이란(+3:30)을 정수로 뭉개면
    발송 시각이 15~30분 어긋난다. 왓츠앱 안전대 경계에서는 이게 실제로 문제가 된다.
    """
    sign = "+" if hours >= 0 else "-"
    total = int(round(abs(hours) * 60))
    h, m = divmod(total, 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")


def fmt_lag(hours):
    if not hours:
        return "시차 없음"
    total = int(round(abs(hours) * 60))
    h, m = divmod(total, 60)
    span = f"{h}시간" + (f" {m}분" if m else "")
    return f"내 쪽이 {span} {'빠름' if hours > 0 else '느림'}"


def plan(tz, occasion_day, label=""):
    """한 나라 × 한 기념일에 대한 발송 계획."""
    prev_day = occasion_day - timedelta(days=1)

    eve_kst = to_home(datetime.combine(prev_day, ARRIVE_EVE), tz)
    morn_kst = to_home(datetime.combine(occasion_day, ARRIVE_MORNING), tz)
    wa_from = to_home(datetime.combine(occasion_day, WA_OPEN), tz)
    wa_to = to_home(datetime.combine(occasion_day, WA_CLOSE), tz)
    # 마감: 이 시각을 넘기면 "기념일 전에 도착"이 성립하지 않는다.
    eve_deadline = to_home(datetime.combine(prev_day, time(23, 59)), tz)
    day_deadline = to_home(datetime.combine(occasion_day, time(23, 59)), tz)

    noon = datetime.combine(occasion_day, ARRIVE_MORNING)
    local_off = noon.replace(tzinfo=ZoneInfo(tz)).utcoffset().total_seconds() / 3600
    home_off = noon.replace(tzinfo=home_zone()).utcoffset().total_seconds() / 3600
    lag = home_off - local_off  # 발송자가 상대보다 몇 시간 빠른가

    flags = []
    if not in_home_hours(morn_kst):
        flags.append("당일아침 도착분은 내 업무시간 밖 → 예약 발송 필요")
    if not in_home_hours(eve_kst):
        flags.append("전날저녁 도착분은 내 업무시간 밖 → 예약 발송 필요")
    if abs(lag) >= 12:
        flags.append("시차 12시간 이상 — 내 날짜와 상대 날짜가 어긋난다, 발송일 재확인")

    return {
        "label": label,
        "tz": tz,
        "utc_offset": fmt_offset(local_off),
        "lag_from_korea_h": lag,
        "occasion_date": occasion_day.isoformat(),
        "eve_arrival_kst": eve_kst.isoformat(),
        "morning_arrival_kst": morn_kst.isoformat(),
        "deadline_before_occasion_kst": eve_deadline.isoformat(),
        "deadline_same_day_kst": day_deadline.isoformat(),
        "whatsapp_window_kst": [wa_from.isoformat(), wa_to.isoformat()],
        "flags": flags,
        "_eve": eve_kst, "_morn": morn_kst, "_waf": wa_from, "_wat": wa_to,
        "_dl_eve": eve_deadline, "_dl_day": day_deadline,
    }


def render(p, occasion_day):
    out = [f"  {p['label']:<28} {p['tz']} ({p['utc_offset']}, {fmt_lag(p['lag_from_korea_h'])})"]
    L = home_label()
    out.append(f"      [권장] 당일 아침 도착   → {L} {fmt(p['_morn'], occasion_day)} 발송")
    out.append(f"             전날 저녁 도착   → {L} {fmt(p['_eve'], occasion_day)} 발송")
    out.append(f"      [마감] 기념일 전 도착   → {L} {fmt(p['_dl_eve'], occasion_day)} 까지")
    out.append(f"             당일 안에 도착   → {L} {fmt(p['_dl_day'], occasion_day)} 까지")
    out.append(f"      [왓츠앱] 안전대         → {L} {fmt(p['_waf'], occasion_day)} ~ {fmt(p['_wat'], occasion_day)}")
    for f in p["flags"]:
        out.append(f"      ! {f}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="기념일 현지 날짜 YYYY-MM-DD")
    ap.add_argument("--country", help="ISO2 코드 콤마 구분, 예: SA,AE,VN")
    ap.add_argument("--tz", help="IANA 타임존 직접 지정, 예: America/Los_Angeles")
    ap.add_argument("--home", help="발송자 타임존 (기본 Asia/Seoul), 예: Europe/Berlin")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.home:
        global HOME_TZ
        try:
            ZoneInfo(args.home)
        except Exception:
            sys.exit(f"알 수 없는 타임존: {args.home}")
        HOME_TZ = args.home

    day = datetime.strptime(args.date, "%Y-%m-%d").date()
    meta = load_countries()
    targets = []

    if args.tz:
        targets.append((args.tz, args.tz))
    if args.country:
        for code in (c.strip().upper() for c in args.country.split(",")):
            row = meta.get(code)
            if not row:
                print(f"[경고] {code}: countries.csv에 없음 — --tz로 직접 지정하세요",
                      file=sys.stderr)
                continue
            tz = (row.get("tz") or "").strip()
            if not tz:
                print(f"[경고] {code}: tz 컬럼 비어 있음", file=sys.stderr)
                continue
            name = f"{code} {row.get('name_ko') or row.get('name_en', '')}"
            targets.append((tz, name))
            note = (row.get("tz_note") or "").strip()
            if note:
                print(f"[참고] {code}: {note}", file=sys.stderr)
    if not targets:
        sys.exit("--country 또는 --tz 가 필요합니다")

    plans = [plan(tz, day, label) for tz, label in targets]

    if args.json:
        print(json.dumps([{k: v for k, v in p.items() if not k.startswith("_")}
                          for p in plans], ensure_ascii=False, indent=2))
        return

    print(f"기념일 현지 날짜: {day} ({WD[day.weekday()]})   / 발송자 기준: {home_label()} ({HOME_TZ})\n")
    for p in plans:
        print(render(p, day))
        print()
    print("이메일은 밤에 보내도 무례하지 않다 — 도착 시각만 맞추면 된다.")
    print("왓츠앱은 현지 시각이 곧 알림음이다 — 안전대를 벗어나면 예약 발송하거나 이메일로 돌린다.")


if __name__ == "__main__":
    main()
