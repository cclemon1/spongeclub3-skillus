# 공개 전 점검 규칙 카탈로그

`publish_check.py` 가 내는 규칙의 의미, 오탐 사례, 고치는 법. 우선순위 세 단으로 나눈다.

## 목차

- [무엇을 보나 — 파일 수집 범위](#무엇을-보나--파일-수집-범위)
- [지금 당장](#지금-당장)
- [이번 주](#이번-주)
- [나중에](#나중에)
- [예외 등록 요령](#예외-등록-요령)
- [모드별 차이](#모드별-차이)
- [스캐너가 못 보는 것](#스캐너가-못-보는-것)

---

## 무엇을 보나 — 파일 수집 범위

`git ls-files` (추적) + `git ls-files --others --exclude-standard` (미추적이지만 무시되지 않은 것).
즉 `git add -A && git push` 로 나갈 모든 것. `.gitignore` 된 파일(`.env.local`)은 보지 않는다 —
안 나가니까. 대신 `.gitignore` 에 그 항목이 *있는지*를 따로 본다.

건너뛰는 것: lockfile, `.min.js`, `.map`, 바이너리·이미지·오피스 파일, 2MB 초과, `node_modules`
같은 폴더, 설정의 `ignore_paths`.

값은 **절대 그대로 출력하지 않는다.** 발췌는 `AKIA…PLE (20자)` 처럼 마스킹된다. 예외 대조는
내부적으로 원문과 하지만 리포트·JSON 에는 원문이 남지 않는다.

---

## 지금 당장

하나라도 있으면 종료 코드 1, push 게이트가 막는다.

| 규칙 | 잡는 것 | 오탐 | 고치기 |
|---|---|---|---|
| `SECRET` | AWS·GitHub·Anthropic·OpenAI·Slack·Google·Stripe·Twilio·Sendgrid·Resend·Supabase·npm 토큰, 개인키 블록, JWT, `user:pw@host` DB URL, URL 속 비밀번호 | AWS 공식 예시 키(`AKIAIOSFODNN7EXAMPLE`)·Turnstile 테스트 키·`PROJECT:PASSWORD@` 템플릿·6자 미만 비밀번호는 자동 제외. JWT 는 Supabase anon 키도 잡는다 — anon 키는 공개 값이니 예외 등록 | 값을 환경변수로. **이미 커밋됐으면 재발급** |
| `SECRET_ASSIGN` | `SOMETHING_SECRET = "긴값"` 이름+값 조합 | 이름에 example/sample/dummy/test/mock 이 있으면 제외. `${VAR}`·`process.env` 참조 제외 | 같음 |
| `HISTORY_SECRET` | 과거 커밋 diff 의 시크릿 (`--history`, `push` 모드) | 위와 같은 제외 규칙 | **재발급.** 이력 정리(filter-repo)는 선택 |
| `BUILD_LEAK` | `.next/static` 의 시크릿·`service_role`·내 정보 (`--build`) | 없음 | 출처(NEXT_PUBLIC_, 클라이언트 import)를 찾아 서버로 |
| `FILE_ENV_TRACKED` | 추적되는 `.env`, `.env.local`, `.env.prod` 등 | `.env.example/.sample/.template` 제외 | `git rm --cached` + .gitignore + 안의 키 전부 재발급 |
| `FILE_KEY` | `.pem .key .p12 .pfx .jks`, `id_rsa`, `service-account*.json`, `firebase-adminsdk*.json`, `credentials.json`, `.netrc .npmrc .pypirc` | `.pub`, `public.pem` 제외 | 저장소에서 빼고 재발급 |
| `FILE_DUMP` | `.sql.gz .dump .bak`, `backups/ exports/ dumps/` 아래 데이터 | 없음 | 빼고 .gitignore. 이미 나갔으면 유출 사고 |
| `FILE_TOOL_CONFIG` | `.claude/settings.local.json`, `.mcp.json`, `.cursor/`, `.codex/`, `.vercel/`, `.idea/` | `.claude/settings.json`(공유용)과 `launch.json` 은 잡지 않는다 | 추적 끊고 .gitignore |
| `IDENTITY` | 설정 '내 정보' 목록의 값 (이메일·전화·이름·OS 계정명) | 공개돼도 되는 값이면 목록에서 빼거나 예외 등록 | 문서·주석·테스트에서 뺀다 |
| `IDENTITY_SECRET` | '내 정보'에 **시크릿 값**으로 등록한 것. 값은 저장하지 않고 SHA-256 해시만 두며, 파일 속 12자 이상 토큰을 해시해 대조한다 | 토큰 경계(`=`·`.` 끝)는 보정한다. 공백이 섞인 값은 못 잡는다 | 재발급하고 해시도 새 값으로 |
| `ENV_VALUE_LEAK` | **gitignore 된 `.env.local`·`.env.prod` 의 값**이 공개될 파일·이력·번들에 그대로 있다. 등록 없이 점검 때마다 자동 대조. DB URL 은 비밀번호 부분도 따로 본다 | 12자 미만, `NEXT_PUBLIC_`·`VITE_` 키, `.env.example` 에 같은 값, 호스트명·URL·이메일·경로·단어만인 값(`ADMIN_HOST=admin.example.com`)은 시크릿이 아니라 뺀다 | 값을 빼고 재발급. 예시 값이면 `.env.example` 에 같은 값을 두어 템플릿임을 드러낸다 |
| `PII_RRN` | 주민등록번호 형태 (`YYMMDD-[1-4]NNNNNN`) | 날짜 검증까지 하므로 오탐 드묾 | 즉시 제거. 이력에 있었으면 사고 |
| `RLS_OPEN_SQL` | `disable row level security`, `grant … to anon/authenticated` | 주석 줄(`--`)은 제외 | RLS 켜고 anon 회수. anon REST 직접 호출로 검증 |
| `SERVICE_ROLE_CLIENT` | `"use client"` 파일에 `service_role` | 없음 | 즉시 제거. 번들에 들어갔으면 재발급 |
| `PUBLIC_SECRET_VAR` | `NEXT_PUBLIC_*SECRET/SERVICE_ROLE/PRIVATE/PASSWORD` | `NEXT_PUBLIC_SUPABASE_ANON_KEY` 는 잡지 않는다 (공개 값) | 접두사 떼고 서버에서만 |

---

## 이번 주

| 규칙 | 잡는 것 | 오탐·판단 | 고치기 |
|---|---|---|---|
| `PII_EMAIL` | 이메일 주소 (테스트 파일 밖) | `noreply@`, `info@`·`support@` 같은 역할 주소, example.com, 수탁자 도메인(amazon·cloudflare·google·vercel·supabase…), URL 자격증명(`pw@host`)은 자동 제외. **회사 공식 도메인은 편집기 '공개 도메인'에 한 번 등록**하면 전부 사라진다 | 개인 주소면 제거 |
| `PII_PHONE` | `010-XXXX-XXXX` 형태 | `010-****-1234`, `0000`, `1234-5678` 제외 | 실제면 제거, 예시면 명백한 더미로 |
| `PII_ADDRESS` | 도로명 주소 형태 (`서울 … 로 12`) | 약관·푸터의 사업장 주소는 공개 의도 → 예외 등록 | 실제 거주지면 제거 |
| `GITIGNORE_MISSING` | `.env / .env.local`, `.claude/settings.local.json`, `.vercel`, `.mcp.json` 중 빠진 것 | `.env*` 한 줄이면 전부 커버 | 추가 |
| `RLS_MISSING_SQL` | `create table` 은 있는데 어느 SQL 에도 `enable row level security` 가 없는 표 | public 스키마만 본다. 뷰·임시표 아님. 마이그레이션 사본이 `references/` 에 있으면 두 번 잡힌다 | 같은 파일에서 RLS enable |
| `RLS_TRUE_POLICY` | `using (true)`, `with check (true)` | **공개 카탈로그 표(지역·요금제·정책 문서)는 정상.** 개인정보 표(leads, users)면 열린 것 | 표 내용을 보고 결정 |
| `CRON_NO_SECRET` | `vercel.json` 크론 라우트 파일에 `CRON_SECRET` 없음 | 라우트 파일을 못 찾으면 LOW "확인 불가" | Bearer 비교 + 없으면 401 |
| `ADMIN_NO_AUTH` | `app/admin/**`, `api/admin/**`, `pages/admin/**` 에 인증 흔적 없음 (middleware·layout 포함) | **휴리스틱.** 식별자(`session`, `requireAdmin`, `redirect(` …)만 본다. 통과해도 시크릿 창에서 직접 열어 본다 | middleware / layout 에서 세션 검사 |
| `LOG_PII` | `console.log(user.email)`, `` `${token}` `` 처럼 식별자를 로그에 | 한국어 문자열 안의 단어는 잡지 않는다. dev 전용 스크립트면 `NODE_ENV` 가드로 | 마스킹 또는 제거 |
| `OPEN_REDIRECT` | `redirect(req.query.next)`, `.get("url")` 처럼 파라미터 출처가 명백 | 없음 | 허용 목록 |
| `SERVICE_ROLE_MENTION` | 코드의 `service_role` 참조 (서버 파일) | 서버 전용 파일이면 정상. 어느 파일인지만 확인 | — |
| `FILE_DATA_EXPORT` | `.csv .xlsx` (fixtures/seed/public 밖) | 샘플이면 fixtures 로 옮겨 의도를 드러낸다 | 실제 명단이면 제거 |
| `GA_PII` | `gtag('event', …{email: …})` | — | 식별 정보 제거 |

---

## 나중에

| 규칙 | 의미 |
|---|---|
| `PII_LOCAL_PATH` | `C:\Users\<이름>`, `/Users/<이름>` — OS 계정명이 드러난다. `user`, `runner` 같은 범용 이름은 제외. 상대 경로로 |
| `GIT_AUTHOR_EMAIL` | 커밋 작성자 이메일이 noreply 가 아니다. 과거는 못 바꾼다. 내 정보 목록과 같으면 HIGH 로 올라간다 |
| `PII_EMAIL_TEST` | 테스트·시드·픽스처 파일의 이메일. `hong@gmail.com` 이 실제 사람이 아니면 넘긴다 |
| `PII_BIZNO` | `123-45-67890` 사업자번호 형태. 약관 푸터면 공개 의도 |
| `PII_IP` | 공인 IPv4. 사설·문서용 대역(192.0.2.x, 198.51.100.x, 203.0.113.x)·테스트 파일 제외 |
| `OPEN_REDIRECT_CHECK` | `redirect(target)` — 변수의 출처를 본다. DB 에서 오면 정상 |
| `DANGEROUS_HTML` | `dangerouslySetInnerHTML`. 주석 줄 제외. 운영자가 넣는 HTML 이면 sanitize 여부 |

---

## 예외 등록 요령

예외는 `{rule, pattern, file, reason}` 이다. rule 이 같고(`*` 면 전부), file glob 에 맞고(비우면
전부), pattern 이 발견 텍스트에 **포함**되면 제외된다.

- 편집기 결과 카드의 "예외 등록"이 rule·pattern·file 을 채워 준다. **사유만 적으면 된다**
- 이메일 한 주소를 전체에서 넘기려면 rule `PII_EMAIL`, pattern 주소, file 비움
- 회사 도메인 전체는 예외가 아니라 '공개 도메인'에 넣는다
- `using (true)` 인 공개 표는 rule `RLS_TRUE_POLICY`, file `supabase/migrations/0001*.sql`
- 사유 없는 예외는 등록되지 않는다 (편집기가 막는다). 나중에 왜 넘겼는지 아무도 기억 못 한다

예외는 값이 **다른 파일에 새로 생기면 다시 잡힌다** (file 을 비우지 않은 경우). 그게 의도다.

---

## 모드별 차이

| 모드 | 언제 | 보는 것 |
|---|---|---|
| `tree` | 평소, 저장소 공개 전환 전 | 추적 + 미추적 파일 전체 + 구조 검사(.gitignore, RLS, 크론, 어드민, 작성자 이메일) |
| `staged` | 커밋 직전 (`secret_scan.py` 훅과 겹치지만 내 정보·PII 까지 본다) | 스테이지된 추가 줄만. 구조 검사 없음 |
| `push` | push 직전, 게이트 훅이 쓰는 모드 | tree + `@{upstream}..HEAD` 커밋들의 diff. upstream 이 없으면 전체 이력 |
| `--history` | 처음 공개할 때 한 번 | 전체 커밋 diff. 고신뢰 시크릿 패턴과 내 정보(이메일·전화)만. 큰 저장소는 수십 초 |
| `--build` | `next build` 뒤 | `.next/static` 번들 |

---

## 스캐너가 못 보는 것

리포트 끝에 항상 붙는 "직접 확인할 것" 다섯 줄. 통과처럼 보이면 안 된다.

- Vercel 환경변수 범위 (Production / Preview)
- Supabase Data API 상태, anon 키 REST 직접 호출 결과, Storage 공개 버킷
- 어드민을 시크릿 창에서 열어 본 결과 (vercel.app 주소도)
- 처리방침 항목 = 실제 폼 항목, 동의 체크박스 분리
- `npm audit` (네트워크 필요), 의존성의 알려진 취약점
- 코드가 *하는 일*의 취약점 (입력 검증 누락, 레이스) — `/security-review` 담당
