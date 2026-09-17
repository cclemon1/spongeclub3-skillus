# plan.json 구조 — 리포트를 만들기 직전에 읽는다

`scripts/build.mjs`가 이 파일을 읽어 **카드뉴스형 슬라이드(1080×1350, 4:5)** 묶음을 만들고, `scripts/render.mjs`가 장마다 PNG로 저장한다. 각 장 오른쪽 위에 `1 / 5` 순서 표시가 붙고 파일명도 `report-01.png`, `report-02.png` … 순서라서 카톡에 순서대로 올리면 된다. 완성 예시는 `assets/example-plan.json`.

## 슬라이드 구성 (자동 배치)

| 장 | 내용 | 들어가는 필드 |
|---|---|---|
| 1 | 표지 — 결론 한 문장, 날씨, 아내에게 한마디, 5곳 한눈에 | `headline` `summary` `weather` `message` `places[].name/travelMin` |
| 2 | 1순위 하루 여정 | `itineraryNote` `itinerary` |
| 3 | 1순위 상세 + 식당 | `places[0]` 전체 |
| 4 | 다른 선택지 4곳 요약 | `places[1..4]` — why 첫 줄, departHint·caution, 식당 이름·메뉴 |
| 5 | 플랜 B · 챙길 것 · 메모 | `planB` `checklist` `notes` |

내용이 한 장에 안 들어가면 스크립트가 다음 장으로 넘기고 "(이어서)" 제목을 붙인다. **목표는 5장, 많아도 6장.** 7장 이상이면 아내가 끝까지 안 넘긴다 → 아래 글자 수 예산대로 줄이고 다시 빌드한다.

## 글자 수 예산 (한글 기준, 넘기면 장수가 늘어난다)

| 필드 | 예산 |
|---|---|
| `headline` | 35자 이내 |
| `summary` | 60자 이내 |
| `message` | 60자 이내 |
| `itinerary` | **7~10줄**. `title` 18자, `detail` 30자 이내. 사소한 줄(기저귀 갈기 등)은 앞뒤 줄 detail에 합친다 |
| `itineraryNote` | 50자 이내 |
| 1순위 `why` | 3개, 각 30자 |
| 1순위 `restaurants` | 최대 3곳, `why` 25자 |
| 2~5순위 `why` | **첫 줄만 표시됨** — 1개, 30자 |
| 2~5순위 `departHint` + `caution` | 합쳐서 35자 |
| 2~5순위 `restaurants` | 1~2곳, `menu` 12자 (이름과 메뉴만 표시) |
| `checklist` | 6~10개, 각 10자 |
| `notes` | 2~3줄 |

## 필드

```jsonc
{
  "meta": {
    "title": "9/19(토) 하준이랑 나들이 보고서",   // 브라우저 탭 제목
    "dateLabel": "9월 19일 토요일",               // 표지 + 각 장 머리글
    "recipient": "여보",                         // "○○에게 보고"로 붙음. 프로필의 호칭
    "author": "하준 아빠",
    "child": "하준 · 18개월",
    "from": "마포구 상암동",                     // 동 단위까지만 — 상세 주소는 넣지 않는다
    "transport": "car",                          // car | transit — transit이면 이동 아이콘이 🚇
    "createdAt": "9/17(목) 작성"
  },
  "headline": "...",        // ★ 결론 한 문장. 장소 + 핵심 배려 (예: "낮잠은 가는 차에서 재울게")
  "summary": "...",
  "weather": {              // ★
    "icon": "☀️", "summary": "맑음, 오후엔 조금 더움",
    "tempMin": 17, "tempMax": 27, "rainProb": 10, "dust": "좋음", "uv": "높음",
    "advice": "야외는 오전에 끝내고 13시 이후엔 그늘·실내로"
  },
  "message": "당신은 토요일 오전 푹 쉬어. 점심 먹고 2시에 들어갈게!",  // 표지에 들어감
  "itineraryNote": "하준이 오전 낮잠(9:30~10:30)을 이동 시간에 맞췄어.",
  "itinerary": [            // ★ 1순위 장소의 하루 시간표
    { "time": "09:30", "type": "move", "title": "출발 (차 약 45분)", "detail": "출발하면 바로 낮잠" }
    // type: prep(준비) move(차·대중교통) walk(도보) play(놀기) meal(식사) snack(간식·수유·기저귀) nap(낮잠) rest(휴식) home(귀가)
  ],
  "places": [               // ★ 5곳, rank 1~5
    {
      "rank": 1, "name": "서울대공원 동물원", "area": "경기 과천시",
      "category": "야외",                  // 실내 / 야외 / 실내+야외
      "travelMin": 45, "distanceKm": 24,   // route.mjs 결과 (예전 이름 driveMin도 읽음)
      "travelMode": "car",                 // car | transit | walk (생략하면 meta.transport)
      "transitRoute": "3호선 연산→수영, 2호선 환승 · 엘리베이터 3번 출구",  // 대중교통일 때 1순위에 표시
      "openRun": false, "reservation": false,
      "why": ["이번 주에 여기인 이유"],
      "babyInfo": ["유모차 대여", "수유실"],
      "hours": "09:00~18:00", "fee": "어른 5,000원 · 만 6세 미만 무료",
      "departHint": "09:30 출발 · 오전 낮잠 차에서",
      "caution": "주차장 11시 이후 만차",   // 가장 중요한 주의 1개. 확인 못 한 정보는 "확인 필요"로
      "restaurants": [                      // 최소 1곳 (place-selection.md 4절의 넓히기 순서)
        { "name": "과천 한우곰탕", "menu": "곰탕 (아기는 밥 말아서)", "why": "안 매운 국물, 아기의자 있음", "distance": "차 5분" }
      ]
    }
  ],
  "planB": "비 오거나 30° 넘으면 → 2순위 ○○(실내)로 변경",
  "checklist": ["기저귀 6장", "물티슈", "..."],
  "notes": ["이동시간 산출 방식", "정보 확인 기준일"]
}
```

## 빌드·렌더

```bash
node <skill>/scripts/build.mjs <outdir>/plan.json        # → <outdir>/report.html (브라우저로 열면 슬라이드가 세로로 쌓여 보임)
node <skill>/scripts/render.mjs <outdir>/report.html      # → <outdir>/report-01.png, report-02.png …
```

render.mjs 종료 코드:
- `0` 성공. 출력에 몇 장인지 나온다 → 7장 이상이면 줄이고 다시.
- `5` 이미지는 만들었지만 **한 블록이 한 장보다 커서 넘친 장**이 있다 (⚠ 표시된 장). 그 장의 긴 글을 줄여 다시 빌드한다.
- `3` 브라우저 없음 → HTML만 전달하고 "브라우저에서 열어 캡처하면 된다"고 안내.

렌더 후 **이미지를 직접 열어 본다.** 거의 빈 장(한두 줄만 넘어간 장)이 있으면 앞 장 글을 줄여서 합친다.
