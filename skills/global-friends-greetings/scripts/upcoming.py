#!/usr/bin/env python3
"""Query the occasion calendar: what is coming up, where, and how to greet it.

The point of this script is that date arithmetic is the part of the job a model
should never do by hand. Lunar and Hijri dates move, multi-day holidays straddle
month boundaries, and an off-by-one on Eid is a real business error. Let the
script resolve dates; spend your own effort on writing the message.

Usage
  upcoming.py                              next 30 days, all countries
  upcoming.py --days 14                    next 14 days
  upcoming.py --country SA,AE,TR           filter by ISO2 country codes
  upcoming.py --region "Middle East"       filter by region
  upcoming.py --month 2027-03              everything in March 2027
  upcoming.py --year 2027                  everything in 2027
  upcoming.py --date 2026-12-25            everything on one day
  upcoming.py --search eid                 fuzzy name search
  upcoming.py --from 2026-11-01 --to 2026-12-31
  upcoming.py --json                       machine-readable output

Add --full to print greeting phrases and notes instead of the compact table.
"""

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timedelta

try:
    import sendtime
except ImportError:  # 다른 디렉터리에서 실행된 경우
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import sendtime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
OCCASIONS = os.path.join(DATA, "occasions.csv")
COUNTRIES = os.path.join(DATA, "countries.csv")


def load_countries():
    if not os.path.exists(COUNTRIES):
        return {}
    with open(COUNTRIES, encoding="utf-8") as f:
        return {r["iso2"].strip().upper(): r for r in csv.DictReader(f)}


def load_occasions():
    with open(OCCASIONS, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("id", "").strip()]


def split_list(value):
    return [p.strip().upper() for p in (value or "").replace("|", ";").split(";") if p.strip()]


def resolve_dates(row, years):
    """Return the list of start dates this occasion falls on within `years`.

    A fixed occasion recurs every year at fixed:MM-DD, so it resolves for any
    year asked. A moving occasion only exists where the data file carries an
    explicit date_<year> column, which is deliberate: a missing year should
    surface as a gap to go re-verify, never as a silently invented date.
    """
    out = []
    rule = (row.get("date_rule") or "").strip()
    if rule.startswith("fixed:"):
        mmdd = rule.split(":", 1)[1]
        try:
            month, day = (int(x) for x in mmdd.split("-"))
        except ValueError:
            return out
        for y in years:
            try:
                out.append(date(y, month, day))
            except ValueError:
                # Feb 29 in a non-leap year — observed on Feb 28.
                if (month, day) == (2, 29):
                    out.append(date(y, 2, 28))
    else:
        for y in years:
            raw = (row.get(f"date_{y}") or "").strip()
            if not raw or raw.lower().startswith(("tbd", "n/a", "-")):
                continue
            for part in raw.split(";"):
                part = part.strip()
                if not part:
                    continue
                try:
                    out.append(datetime.strptime(part, "%Y-%m-%d").date())
                except ValueError:
                    continue
    return out


def occurrences(rows, start, end, countries=None, regions=None, search=None,
                country_meta=None):
    years = list(range(start.year, end.year + 1))
    country_meta = country_meta or {}
    hits = []
    for row in rows:
        row_countries = split_list(row.get("countries"))
        if countries:
            if row_countries and not (set(row_countries) & set(countries)):
                continue
        if regions:
            row_regions = {
                (country_meta.get(c, {}).get("region") or "").strip().lower()
                for c in row_countries
            }
            if not (row_regions & {r.lower() for r in regions}):
                continue
        if search:
            haystack = " ".join(
                (row.get(k) or "") for k in
                ("name_en", "name_local", "romanization", "notes", "countries")
            ).lower()
            if search.lower() not in haystack:
                continue

        try:
            duration = max(1, int(float(row.get("duration_days") or 1)))
        except ValueError:
            duration = 1

        for d in resolve_dates(row, years):
            last = d + timedelta(days=duration - 1)
            if last < start or d > end:
                continue
            hits.append({
                "date": d.isoformat(),
                "end_date": last.isoformat() if duration > 1 else "",
                "days_away": (d - date.today()).days,
                "weekday": d.strftime("%a"),
                "countries": row_countries,
                "name_en": row.get("name_en", ""),
                "name_local": row.get("name_local", ""),
                "romanization": row.get("romanization", ""),
                "type": row.get("type", ""),
                "tone": row.get("tone", ""),
                "duration_days": duration,
                "greeting_local": row.get("greeting_local", ""),
                "greeting_romanized": row.get("greeting_romanized", ""),
                "greeting_meaning": row.get("greeting_meaning", ""),
                "send_window": row.get("send_window", ""),
                "notes": row.get("notes", ""),
                "id": row.get("id", ""),
            })
    hits.sort(key=lambda h: (h["date"], h["name_en"]))
    return hits


TONE_MARK = {"celebratory": "축", "solemn": "!!", "neutral": "  "}


def render_plan(hits, country_meta, only=None):
    """기념일 × 국가별로 한국시간 발송 시각을 붙여 낸다.

    한 기념일이 20개국에서 동시에 열리면 KST 발송 시각도 20가지다 — 크리스마스
    아침 인사를 한 시각에 일괄 발송하면 누군가에게는 전날 밤, 누군가에게는
    다음날 점심에 닿는다. 그래서 국가 단위로 쪼개서 보여준다.
    """
    lines = []
    for h in hits:
        day = datetime.strptime(h["date"], "%Y-%m-%d").date()
        codes = [c for c in h["countries"] if not only or c in only]
        if not codes:
            continue
        mark = TONE_MARK.get(h["tone"], "  ")
        lines.append(f"\n{h['date']} ({h['weekday']}) [{mark}] {h['name_en']}")
        if h["tone"] == "solemn":
            lines.append("    ※ 추모일 — 'Happy' 금지")
        for code in codes:
            row = country_meta.get(code)
            tz = (row or {}).get("tz", "").strip()
            if not tz:
                lines.append(f"  {code}: tz 정보 없음 — countries.csv 확인 필요")
                continue
            name = f"{code} {(row.get('name_ko') or row.get('name_en') or '').strip()}"
            lines.append(sendtime.render(sendtime.plan(tz, day, name), day))
    return "\n".join(lines) if lines else "해당 조건에 맞는 건이 없습니다."


def render(hits, full=False):
    if not hits:
        return "No occasions found in that window."
    lines = []
    solemn = [h for h in hits if h["tone"] == "solemn"]
    for h in hits:
        mark = TONE_MARK.get(h["tone"], "  ")
        span = f"..{h['end_date'][5:]}" if h["end_date"] else ""
        where = ",".join(h["countries"][:6]) + ("+" if len(h["countries"]) > 6 else "")
        lines.append(
            f"{h['date']}{span} {h['weekday']} [{mark}] {h['name_en']}  ({where})"
        )
        if full:
            if h["name_local"]:
                loc = h["name_local"]
                if h["romanization"]:
                    loc += f" / {h['romanization']}"
                lines.append(f"      local name : {loc}")
            if h["greeting_local"]:
                g = h["greeting_local"]
                if h["greeting_romanized"]:
                    g += f" ({h['greeting_romanized']})"
                if h["greeting_meaning"]:
                    g += f" — {h['greeting_meaning']}"
                lines.append(f"      greeting   : {g}")
            if h["send_window"]:
                lines.append(f"      send when  : {h['send_window']}")
            if h["notes"]:
                lines.append(f"      note       : {h['notes']}")
            lines.append("")
    if solemn:
        lines.append("")
        lines.append(
            "SOLEMN — do not write 'Happy'. Use 'remembering', 'observing', "
            "'our respects on':"
        )
        for h in solemn:
            lines.append(f"  - {h['date']} {h['name_en']} ({','.join(h['countries'][:6])})")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, help="window of N days from today")
    p.add_argument("--from", dest="start", help="start date YYYY-MM-DD")
    p.add_argument("--to", dest="end", help="end date YYYY-MM-DD")
    p.add_argument("--date", help="a single day YYYY-MM-DD")
    p.add_argument("--month", help="YYYY-MM")
    p.add_argument("--year", type=int)
    p.add_argument("--country", help="comma-separated ISO2 codes, e.g. SA,AE,VN")
    p.add_argument("--region", help="comma-separated regions, e.g. 'Middle East,Europe'")
    p.add_argument("--search", help="substring match on occasion name or notes")
    p.add_argument("--full", action="store_true", help="show greetings and notes")
    p.add_argument("--plan", action="store_true",
                   help="국가별 한국시간(KST) 발송 시각·마감까지 계산해서 출력")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    today = date.today()
    if args.date:
        start = end = datetime.strptime(args.date, "%Y-%m-%d").date()
    elif args.month:
        y, m = (int(x) for x in args.month.split("-"))
        start = date(y, m, 1)
        end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
    elif args.year:
        start, end = date(args.year, 1, 1), date(args.year, 12, 31)
    elif args.start or args.end:
        start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else today
        end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else start + timedelta(days=30)
    else:
        start = today
        end = today + timedelta(days=args.days or 30)

    if not os.path.exists(OCCASIONS):
        sys.exit(f"Missing data file: {OCCASIONS}")

    country_meta = load_countries()
    only = [c.strip().upper() for c in args.country.split(",")] if args.country else None
    hits = occurrences(
        load_occasions(), start, end,
        countries=only,
        regions=[r.strip() for r in args.region.split(",")] if args.region else None,
        search=args.search,
        country_meta=country_meta,
    )

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    elif args.plan:
        print(f"{start} → {end}   ({len(hits)}건)   발송자 기준: 한국시간(KST)")
        print(render_plan(hits, country_meta, only=only))
    else:
        print(f"{start} → {end}   ({len(hits)} occasions)\n")
        print(render(hits, full=args.full))


if __name__ == "__main__":
    main()
