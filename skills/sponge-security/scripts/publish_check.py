#!/usr/bin/env python3
"""스폰지보안 · 모드 B — 공개 전 점검 (GitHub push · Vercel 배포 전).

저장소를 읽기만 하고, 밖으로 나가면 곤란한 것을 찾는다:

  시크릿      API 키·토큰·개인키·DB 접속 문자열 (고신뢰 패턴 + 이름·값 조합)
  내 정보     설정의 identity 목록 (이메일·전화·이름·OS 계정), 주민번호, 휴대폰, 이메일,
              로컬 경로(사용자명 노출), 사업자번호, 공인 IP, 주소
  파일        추적되는 .env·도구 설정(.claude/settings.local.json, .mcp.json, .vercel)·
              키 파일(.pem 등)·덤프/백업, .gitignore 누락
  코드        NEXT_PUBLIC_ 에 시크릿, "use client" 에서 service_role, RLS 개방/누락,
              CRON_SECRET 없는 크론 라우트, 인증 없는 어드민(휴리스틱), 로그에 PII,
              오픈 리다이렉트, dangerouslySetInnerHTML, GA 이벤트에 PII
  이력        커밋 작성자 이메일, (--history) 과거 커밋 diff 의 시크릿
  빌드        (--build) .next/static 번들에 시크릿·내 정보

스폰지클럽 5회차 "보안 1차 점검" 과 스폰지 어드민 키트 12-spec-security B절을
자동화할 수 있는 만큼 옮긴 것이다. 대시보드에서만 보이는 것(Vercel 환경변수
범위, Supabase Data API 상태)은 여기서 못 본다 — 보고서의 "직접 확인" 절에 남긴다.

Usage:
    python publish_check.py <repo-dir> [--mode tree|staged|push] [--history] [--build] [--json] [--no-save]

Exit code: 1 if there is anything in "지금 당장", else 0.
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

MAX_FILE_BYTES = 2_000_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build", "out", "coverage", ".turbo"}
SKIP_FILE = re.compile(
    r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|go\.sum|composer\.lock|bun\.lockb)$"
    r"|\.(min\.js|min\.css|map|snap|lock)$"
)
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".woff", ".woff2", ".ttf", ".otf", ".eot",
              ".pdf", ".zip", ".gz", ".tar", ".7z", ".exe", ".dll", ".so", ".dylib", ".pyc", ".mp4", ".mp3",
              ".mov", ".webm", ".hwp", ".docx", ".xlsx", ".pptx", ".psd", ".ai", ".sketch", ".fig"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro"}


def _r(p, flags=re.IGNORECASE):
    return re.compile(p, flags)


# ---------------------------------------------------------------- 시크릿 (고신뢰)
SECRET_PATTERNS = [
    ("AWS 액세스 키", _r(r"\b(A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b", 0), "AWS 계정 접근"),
    ("AWS 시크릿 키", _r(r"aws.{0,20}?(secret|private).{0,20}?['\"][A-Za-z0-9/+=]{40}['\"]"), "AWS 계정 접근"),
    ("개인키 블록", _r(r"-----BEGIN\s+(RSA|DSA|EC|OPENSSH|PGP|ENCRYPTED)?\s*PRIVATE KEY", 0), "SSH/TLS/서명 개인키"),
    ("GitHub 토큰", _r(r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b", 0), "저장소 접근"),
    ("Anthropic API 키", _r(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b", 0), "API 과금 계정"),
    ("OpenAI API 키", _r(r"\bsk-(proj-)?[A-Za-z0-9]{32,}\b", 0), "API 과금 계정"),
    ("Slack 토큰", _r(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", 0), "워크스페이스 접근"),
    ("Google API 키", _r(r"\bAIza[A-Za-z0-9_-]{35}\b", 0), "GCP 서비스 접근"),
    ("Stripe 키", _r(r"\b[sr]k_(live|test)_[A-Za-z0-9]{20,}\b", 0), "결제 계정"),
    ("Twilio 키", _r(r"\bSK[a-f0-9]{32}\b", 0), "통신 계정"),
    ("Sendgrid 키", _r(r"\bSG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b", 0), "메일 발송 계정"),
    ("Resend 키", _r(r"\bre_[A-Za-z0-9]{20,}\b", 0), "메일 발송 계정"),
    ("Supabase 액세스 토큰", _r(r"\bsbp_[a-f0-9]{30,}\b", 0), "Supabase 계정 관리 권한"),
    ("npm 토큰", _r(r"\bnpm_[A-Za-z0-9]{36}\b", 0), "패키지 배포 권한"),
    ("Vercel 토큰 변수", _r(r"VERCEL_TOKEN\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}"), "배포 계정"),
    ("JWT", _r(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b", 0),
     "세션/인증 토큰 (Supabase service_role 키도 이 형태)"),
    ("DB 접속 문자열", _r(r"\b(postgres|postgresql|mysql|mongodb(\+srv)?|redis|amqp)://[^\s:@/{}$<>]+:[^\s:@/{}$<>]+@"),
     "데이터베이스 자격증명"),
    ("URL 에 박힌 비밀번호", _r(r"https?://[^\s/:{}$<>]+:[^\s/@{}$<>]{8,}@"), "URL 문자열에 담긴 비밀번호"),
]
ASSIGN = re.compile(
    r"""(?P<name>[A-Za-z_][A-Za-z0-9_]*(secret|token|passwd|password|api[_-]?key|
        access[_-]?key|private[_-]?key|credential|service[_-]?role)[A-Za-z0-9_]*)
        \s*[:=]\s*['"](?P<val>[^'"\n]{16,})['"]""",
    re.I | re.X,
)
PLACEHOLDER = re.compile(
    r"^(\s*)?(x{3,}|\*{3,}|\.{3,}|<[^>]+>|\{\{.*\}\}|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|"
    r"your[-_ ]?|my[-_ ]?|test|dummy|sample|example|placeholder|changeme|redacted|"
    r"none|null|true|false|process\.env|os\.environ|import\.meta\.env|env\(|"
    r"[A-Z_]{4,}$)", re.I,
)
LOW_ENTROPY = re.compile(r"^[A-Za-z]+$|^[0-9]+$|^[A-Za-z]+[_-][A-Za-z]+$")
PLACEHOLDER_WORDS = {"password", "passwd", "pass", "pwd", "user", "username", "project", "host", "secret",
                     "token", "key", "xxx", "xxxx", "your_password", "your-password", "yourpassword", "changeme",
                     "example", "sample", "placeholder", "postgres", "root", "admin", "db_password", "dbpassword",
                     "your_user", "your-user", "user_name", "pw", "encoded_password", "url_encoded_password"}
# 공식 문서의 예시 키. 실제 키가 아니다.
KNOWN_EXAMPLE_VALUES = {
    "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "AKIAI44QH8DHBEXAMPLE",
    "1x0000000000000000000000000000000AA", "2x0000000000000000000000000000000AA", "3x0000000000000000000000000000000AA",
    "1x00000000000000000000AA", "2x00000000000000000000AB", "3x00000000000000000000FF",
}
EXAMPLE_NAME = re.compile(r"example|sample|dummy|fake|mock|placeholder|test_|_test|fixture", re.I)
REPEATED = re.compile(r"(.)\1{9,}")


def looks_fake(val):
    v = val.strip("'\"` ")
    return v in KNOWN_EXAMPLE_VALUES or bool(REPEATED.search(v)) or "EXAMPLE" in v.upper()


def is_placeholder_url(m):
    """postgresql://postgres.PROJECT:PASSWORD@host - template, not a leak."""
    s = m.group(0)
    try:
        creds = s.split("://", 1)[1].rsplit("@", 1)[0]
        user, pw = creds.split(":", 1)
    except (IndexError, ValueError):
        return False
    if len(pw) < 6:
        return True
    for part in (user.split(".")[-1], pw):
        p = part.strip("[]<>{}$").lower()
        if p in PLACEHOLDER_WORDS or PLACEHOLDER.match(part) or re.fullmatch(r"[A-Z_]{4,}", part):
            return True
    return False


TEST_PATH = re.compile(r"(^|/)(__tests__|tests?|fixtures?|__mocks__|e2e|spec)/|\.(test|spec|stories)\.[a-z]+$|(^|/)seed[^/]*\.(ts|js|py|sql)$", re.I)
COMMENT_LINE = re.compile(r"^\s*(//|/\*|\*|#|--|<!--)")


# ---------------------------------------------------------------- 개인정보
EMAIL_RX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
EMAIL_SKIP_LOCAL = {"noreply", "no-reply", "donotreply", "do-not-reply", "user", "you", "your", "name", "email",
                    "foo", "bar", "someone", "example", "test", "sample", "mail", "me", "a", "b", "x", "xxx",
                    "hello", "info", "support", "contact", "help", "admin", "team", "sales", "office", "cs",
                    "privacy", "security", "legal", "postmaster", "abuse", "webmaster", "dev", "developer",
                    "notifications", "bounce", "bounces", "events", "event", "news", "newsletter", "marketing"}
EMAIL_SKIP_DOMAIN = re.compile(r"(^|\.)(example\.(com|org|net)|test|localhost|invalid|local|users\.noreply\.github\.com|"
                               r"noreply\.github\.com|sentry\.io|vercel\.app|amazonses\.com|supabase\.io|"
                               r"googlegroups\.com|w3\.org|schema\.org|npmjs\.com|apache\.org|mozilla\.org|"
                               # 개인정보처리방침에 적는 수탁자 연락처. 개인 주소가 아니다.
                               r"amazon\.com|aws\.amazon\.com|cloudflare\.com|google\.com|vercel\.com|supabase\.com|"
                               r"github\.com|apple\.com|microsoft\.com|meta\.com|facebook\.com|kakao\.com|kakaocorp\.com|"
                               r"navercorp\.com|linecorp\.com|stripe\.com|anthropic\.com|openai\.com|resend\.com|sendgrid\.com|"
                               r"twilio\.com|slack\.com|notion\.so|channel\.io|toss\.im|tosspayments\.com)$", re.I)
PHONE_RX = re.compile(r"(?<![\d-])01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?![\d-])")
PHONE_SKIP = re.compile(r"\*|0000|1234[-. ]?5678|1111|9999|0{3,}")
RRN_RX = re.compile(r"(?<!\d)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])-[1-4]\d{6}(?!\d)")
BIZNO_RX = re.compile(r"(?<![\d-])\d{3}-\d{2}-\d{5}(?![\d-])")
LOCAL_PATH_RX = re.compile(r"(?:[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}|/Users/|/home/)([A-Za-z0-9._-]{2,})")
GENERIC_USERS = {"user", "users", "admin", "root", "runner", "ubuntu", "ec2-user", "vercel", "node", "app",
                 "username", "your-name", "yourname", "me", "public", "default", "administrator", "guest", "test"}
IPV4_RX = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
ADDRESS_RX = re.compile(r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
                        r"[가-힣\s]{0,14}(로|길|대로)\s?\d{1,4}(-\d{1,4})?(?![\d-])")


def public_ipv4(m):
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if a in (0, 10, 127) or a > 223 or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31) or (a == 169 and b == 254):
        return False
    # 문서용 예시 대역 (TEST-NET-1/2/3) 과 흔한 더미
    if (a, b, c) in ((192, 0, 2), (198, 51, 100), (203, 0, 113)) or m.group(0) in ("1.2.3.4", "1.1.1.1", "8.8.8.8", "8.8.4.4", "255.255.255.255"):
        return False
    if any(int(m.group(i)) > 255 for i in range(1, 5)):
        return False
    return True


# ---------------------------------------------------------------- 코드 규칙
CODE_RULES = [
    ("PUBLIC_SECRET_VAR", "HIGH", None,
     _r(r"\b(NEXT_PUBLIC|VITE|REACT_APP|EXPO_PUBLIC|NUXT_PUBLIC|PUBLIC)_[A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE|PASSWORD|PASSWD)\b", 0),
     "브라우저로 나가는 환경변수 이름에 시크릿. 번들에 그대로 들어간다.",
     "변수에서 공개 접두사를 떼고 서버 코드에서만 읽는다. 이미 배포됐다면 값을 재발급한다."),
    ("RLS_OPEN_SQL", "HIGH", {".sql"},
     _r(r"disable\s+row\s+level\s+security|"
        r"grant\s+(all|insert|update|delete|select)\b[^\n]{0,60}\bto\s+(anon|public|authenticated)\b"),
     "RLS 를 끄거나 anon·authenticated 에 표 권한 부여. anon 키만으로 표를 읽고 쓸 수 있다.",
     "RLS 를 켜고 anon 권한을 회수한다. 배포된 사이트의 anon 키로 REST 를 직접 호출해 401/빈 배열을 확인한다."),
    ("RLS_TRUE_POLICY", "MEDIUM", {".sql"},
     _r(r"(using|with\s+check)\s*\(\s*true\s*\)"),
     "누구나(true) 통과하는 정책. 공개 카탈로그 표면 정상이지만, 개인정보 표라면 열린 것.",
     "이 표에 개인정보가 없는지 확인한다. 있으면 tenant/user 조건으로 바꾼다. 공개 표면 예외 등록."),
    ("LOG_PII", "MEDIUM", CODE_EXT | {".py"},
     _r(r"(console\.(log|info|debug|warn)|logger\.(info|debug|warn)|print)\([^\n]{0,80}(\$\{|[.{(,\[])\s*(email|phone|password|passcode|token|body|req\.body|request\.body|user|lead|entry|form)\s*[\s,)}\]\.]"),
     "로그에 이메일·전화·토큰·요청 본문이 찍힐 수 있다. 호스팅 로그는 여러 사람이 본다.",
     "마스킹 시리얼라이저를 거치거나 식별자만 남긴다. 개발 전용이면 NODE_ENV 가드를 건다."),
    ("OPEN_REDIRECT", "MEDIUM", CODE_EXT,
     _r(r"redirect\(\s*(req|request|searchParams|params|query)\.[^\n]{0,40}\)|"
        r"redirect\([^\n]{0,60}\.get\(\s*['\"](url|next|redirect|return|returnTo|to|target|callback)['\"]"),
     "주소 파라미터로 받은 URL 로 리다이렉트. 피싱 링크의 발판이 된다.",
     "DB 에 저장된 우리 목적지로만 보낸다. 외부 URL 은 허용 목록으로 검사한다."),
    ("OPEN_REDIRECT_CHECK", "LOW", CODE_EXT,
     _r(r"\bredirect\(\s*(url|next|returnTo|target|dest|destination|to)\s*[,)]"),
     "리다이렉트 대상이 변수에서 온다. 그 값이 주소 파라미터에서 오면 오픈 리다이렉트.",
     "변수의 출처를 확인한다. DB·상수에서 오면 정상."),
    ("DANGEROUS_HTML", "LOW", CODE_EXT,
     _r(r"dangerouslySetInnerHTML|v-html=|\{@html\b|innerHTML\s*=", 0),
     "HTML 을 직접 주입. 사용자 입력이 섞이면 XSS.",
     "입력 출처를 확인한다. 사용자 입력이면 sanitize 하거나 텍스트로 렌더한다."),
    ("GA_PII", "LOW", CODE_EXT | {".html"},
     _r(r"(gtag|ga|dataLayer\.push|track|logEvent)\(\s*['\"]?(event|send)?[^\n]{0,80}\b(email|phone|name|이메일|전화|이름|token)\s*:"),
     "GA 이벤트 파라미터에 개인정보. GA 약관 위반이고 제3자에게 넘어간다.",
     "파라미터에서 식별 정보를 뺀다. 필요하면 해시된 ID 만."),
    ("SERVICE_ROLE_MENTION", "MEDIUM", CODE_EXT,
     _r(r"SUPABASE_SERVICE_ROLE|service_role", 0),
     "service_role 키 참조. 서버 전용 파일인지 확인 (\"use client\" 파일이면 지금 당장).",
     "서버 코드(route.ts, server action, lib/server) 에서만 읽는다."),
]

# 경로만으로 판단하는 파일 규칙
FILE_RULES = [
    ("FILE_ENV_TRACKED", "CRITICAL", _r(r"(^|/)\.env(\.[A-Za-z0-9_.-]+)?$", 0),
     _r(r"\.env\.(example|sample|template|dist|schema)$", 0),
     ".env 파일이 저장소에 들어간다. 안의 모든 값이 공개된다.",
     "git rm --cached 로 추적을 끊고 .gitignore 에 넣는다. 이미 push 됐다면 안의 키를 전부 재발급한다."),
    ("FILE_TOOL_CONFIG", "HIGH", _r(r"(^|/)(\.claude/settings\.local\.json|\.mcp\.json|\.cursor/.*|\.codex/.*|\.vercel/.*|\.idea/.*|\.vscode/settings\.json)$", 0),
     None,
     "AI 도구·배포 도구의 로컬 설정. 토큰·DB 연결·프로젝트 ID 가 들어갈 수 있다.",
     "추적을 끊고 .gitignore 에 넣는다. .claude/settings.json(공유용) 과 launch.json 은 두어도 된다."),
    ("FILE_KEY", "CRITICAL", _r(r"\.(pem|key|p12|pfx|jks|keystore|ppk|asc)$|(^|/)(id_rsa|id_ed25519|id_ecdsa)(\.pub)?$|"
                                r"(service[-_]?account|firebase[-_]?adminsdk|google[-_]?credentials|gcp[-_]?key)[^/]*\.json$|"
                                r"(^|/)credentials\.json$|(^|/)\.netrc$|(^|/)\.npmrc$|(^|/)\.pypirc$", 0),
     _r(r"\.pub$|(^|/)public\.pem$", 0),
     "개인키·서비스 계정 파일. 파일 하나로 계정 전체를 넘겨준다.",
     "저장소에서 빼고 키를 재발급한다. 키는 환경변수나 시크릿 매니저로."),
    ("FILE_DUMP", "HIGH", _r(r"\.(sql\.gz|dump|bak|backup)$|(^|/)(backups?|exports?|dumps?)/.+\.(json|csv|sql|ndjson)$", 0),
     None,
     "DB 백업·내보내기 파일. 고객 데이터가 통째로 들어 있을 수 있다.",
     "추적을 끊고 경로를 .gitignore 에 넣는다. 이미 push 됐다면 유출 사고로 다룬다."),
    ("FILE_DATA_EXPORT", "MEDIUM", _r(r"\.(csv|xlsx|xls|ndjson)$", 0),
     _r(r"(^|/)(fixtures?|seeds?|samples?|examples?|test|tests|__tests__|public|content|docs)/", 0),
     "데이터 파일. 실제 고객 명단인지 샘플인지 확인.",
     "실제 데이터면 저장소에서 뺀다. 샘플이면 fixtures/ 같은 폴더로 옮겨 의도를 드러낸다."),
]

FIX = {
    "SECRET": "값을 코드에서 빼고 환경변수로 옮긴다. 이미 커밋됐다면 그 키를 폐기·재발급한다 — 이력에서 지워도 복제본에는 남는다.",
    "SECRET_ASSIGN": "값을 환경변수로 옮기고, 이 값이 실제 키였다면 재발급한다.",
    "IDENTITY": "내 정보를 문서·주석·테스트 데이터에서 뺀다. 공개돼도 되는 값이면 편집기에서 예외로 등록한다.",
    "IDENTITY_SECRET": "이 값은 공개된 것으로 본다. 파일에서 빼고 재발급한다. 재발급했으면 '내 정보'의 해시도 새 값으로 바꾼다.",
    "ENV_VALUE_LEAK": "운영 시크릿이 공개될 파일에 있다. 값을 빼고, 이미 커밋됐다면 재발급한다. 예시 값이면 .env.example 에 같은 값을 두어 템플릿임을 드러낸다.",
    "PII_RRN": "주민등록번호는 어떤 형태로도 저장소에 두지 않는다. 즉시 제거하고 이력에 있었다면 사고로 다룬다.",
    "PII_PHONE": "실제 번호면 제거. 예시라면 010-0000-0000 같은 명백한 더미로 바꾼다.",
    "PII_EMAIL": "개인 이메일이면 제거하거나 noreply/공식 주소로 바꾼다. 회사 공식 주소면 편집기 '공개 도메인' 에 등록한다.",
    "PII_LOCAL_PATH": "절대 경로를 상대 경로나 <프로젝트 루트> 로 바꾼다. OS 계정 이름이 드러난다.",
    "PII_BIZNO": "사업자등록번호 형태. 공개 의도가 아니면 뺀다 (푸터 고지용이면 예외 등록).",
    "PII_IP": "공인 IP. 서버·사무실 IP 라면 뺀다.",
    "PII_ADDRESS": "실제 주소인지 확인. 사업장 고지용이면 예외 등록.",
    "GITIGNORE_MISSING": ".gitignore 에 항목을 추가한다.",
    "RLS_MISSING_SQL": "표 생성 SQL 과 같은 파일에서 alter table … enable row level security 를 켠다. 스폰지클럽 규범: 표는 만들자마자 잠근다.",
    "CRON_NO_SECRET": "라우트 첫 줄에서 Authorization: Bearer <CRON_SECRET> 을 timingSafeEqual 로 비교하고, 없으면 401.",
    "ADMIN_NO_AUTH": "middleware 나 admin/layout 에서 세션을 검사한다. 화면 숨김은 보안이 아니다.",
    "SERVICE_ROLE_CLIENT": "\"use client\" 파일에서 service_role 참조를 제거한다. 번들에 들어가면 DB 전체가 열린다.",
    "GIT_AUTHOR_EMAIL": "저장소 로컬에서만 git config user.email 을 GitHub noreply 주소로 바꾼다. 과거 커밋은 남는다.",
    "HISTORY_SECRET": "이 키는 이미 공개된 것으로 본다. 재발급이 답이다. 이력 삭제(filter-repo)는 그 다음이고 선택이다.",
    "BUILD_LEAK": "번들에 들어간 값의 출처(NEXT_PUBLIC_ 변수, 클라이언트 import)를 찾아 서버로 옮기고 값을 재발급한다.",
}

PRIORITY_NOW = {"SECRET", "SECRET_ASSIGN", "HISTORY_SECRET", "BUILD_LEAK", "FILE_ENV_TRACKED", "FILE_KEY", "FILE_DUMP",
                "IDENTITY", "IDENTITY_SECRET", "ENV_VALUE_LEAK", "PII_RRN", "RLS_OPEN_SQL", "SERVICE_ROLE_CLIENT", "PUBLIC_SECRET_VAR", "FILE_TOOL_CONFIG"}
PRIORITY_WEEK = {"PII_PHONE", "PII_EMAIL", "PII_ADDRESS", "GITIGNORE_MISSING", "CRON_NO_SECRET", "ADMIN_NO_AUTH",
                 "RLS_MISSING_SQL", "RLS_TRUE_POLICY", "LOG_PII", "OPEN_REDIRECT", "GA_PII", "FILE_DATA_EXPORT",
                 "SERVICE_ROLE_MENTION"}
PRIO_LABEL = {"now": "지금 당장", "week": "이번 주", "later": "나중에"}


def priority_of(rule, severity):
    if rule in PRIORITY_NOW:
        return "now"
    if rule in PRIORITY_WEEK:
        return "week"
    if rule.startswith("CUSTOM") or rule not in FIX:
        return {"CRITICAL": "now", "HIGH": "now", "MEDIUM": "week"}.get(severity, "later")
    return "later"


# ---------------------------------------------------------------- 파일 수집

def is_git(root):
    return common.git(["rev-parse", "--show-toplevel"], cwd=root) is not None


def collect_files(root, cfg):
    """(relpath, status) for everything that would leave with `git add -A && git push`."""
    files = []
    if is_git(root):
        tracked = common.git(["ls-files", "-z"], cwd=root) or ""
        others = common.git(["ls-files", "-z", "--others", "--exclude-standard"], cwd=root) or ""
        files += [(p, "tracked") for p in tracked.split("\0") if p]
        files += [(p, "untracked") for p in others.split("\0") if p]
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                files.append((os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/"), "folder"))
    ignore = cfg.get("ignore_paths", [])
    out = []
    for p, st in files:
        parts = p.split("/")
        if any(seg in SKIP_DIRS for seg in parts[:-1]):
            continue
        if any(fnmatch.fnmatch(p, g) for g in ignore):
            continue
        out.append((p, st))
    return out


def read_text(path):
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None
        with open(path, "rb") as fh:
            chunk = fh.read(4096)
        if b"\x00" in chunk:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


# ---------------------------------------------------------------- identity

TOKEN_RX = re.compile(r"[A-Za-z0-9_\-+/=.]{12,}")
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
ENV_PUBLIC_PREFIX = re.compile(r"^(NEXT_PUBLIC|VITE|REACT_APP|EXPO_PUBLIC|NUXT_PUBLIC|PUBLIC)_")
ENV_SKIP_VALUE = re.compile(r"^(true|false|\d+|https?://(localhost|127\.0\.0\.1)[^\s]*|development|production|test|local)$", re.I)
# 설정 값이지 시크릿이 아닌 것: 호스트명, 자격증명 없는 URL, 이메일, 경로, 그냥 단어들
ENV_CONFIG_VALUE = re.compile(
    r"^(\.?[a-z0-9-]+(\.[a-z0-9-]+)+(:\d+)?(/[^\s]*)?"          # host.name[:port][/path]
    r"|https?://[^:@\s]+(:\d+)?(/[^\s]*)?"                        # URL without user:pw@
    r"|[^@\s]+@[^@\s]+\.[a-z]{2,}"                                 # email
    r"|[A-Za-z]:[\\/].*|\.{0,2}/[^\s]*"                            # path
    r"|[A-Za-z가-힣 ,.\-_/]+"                                      # words only
    r"|[a-z]{2}(-[a-z]+)?-\d+|ap-northeast-\d[a-z]?|us-[a-z]+-\d)$", re.I)


def parse_env(text):
    out = {}
    for line in text.splitlines():
        m = ENV_LINE.match(line)
        if not m:
            continue
        v = m.group(2).strip()
        if v[:1] in "\"'" and v[-1:] == v[:1] and len(v) >= 2:
            v = v[1:-1]
        v = v.split(" #")[0].strip() if v[:1] not in "\"'" else v
        out[m.group(1)] = v
    return out


def env_secret_matchers(root, files):
    """Values from the project's *ignored* .env files. Those are the secrets this project
    actually uses, so none of them may appear in anything that leaves. Read at scan time,
    never written anywhere."""
    listed = {p for p, _ in files}
    template = {}
    for name in (".env.example", ".env.sample", ".env.template"):
        t = read_text(os.path.join(root, name))
        if t:
            template.update(parse_env(t))
    template_values = {v for v in template.values() if v}
    out = []
    try:
        names = sorted(n for n in os.listdir(root) if n.startswith(".env") and os.path.isfile(os.path.join(root, n)))
    except OSError:
        return out
    for name in names:
        if name in listed or name in (".env.example", ".env.sample", ".env.template"):
            continue  # 추적되는 .env 는 FILE_ENV_TRACKED 가 따로 잡는다
        text = read_text(os.path.join(root, name))
        if not text:
            continue
        for key, val in parse_env(text).items():
            if len(val) < 12 or ENV_PUBLIC_PREFIX.match(key) or ENV_SKIP_VALUE.match(val) or val in template_values:
                continue
            if PLACEHOLDER.match(val) or looks_fake(val) or ENV_CONFIG_VALUE.match(val):
                continue
            out.append((val, key, name))
            m = re.match(r"^[a-z+]+://[^:/@\s]+:([^@\s]{8,})@", val, re.I)  # DB URL 이면 비밀번호도 따로
            if m and m.group(1) not in template_values:
                out.append((m.group(1), key + " (비밀번호)", name))
    return out


def secret_checks(text, file, line_no, status, ctx, findings):
    """Exact-value checks: ignored .env values and hashed secrets from '내 정보'."""
    for val, key, src in ctx["env_values"]:
        if val in text:
            findings.append(new_finding("CRITICAL", "ENV_VALUE_LEAK", file, line_no,
                                        f"{src} 의 {key} 값 ({common.redact(val)})",
                                        f"gitignore 된 {src} 에 있는 {key} 의 값이 공개될 파일에 그대로 있다.", status, val))
            break
    if ctx["secret_hashes"]:
        for tok in TOKEN_RX.findall(text):
            for cand in (tok, tok.rstrip("=."), tok.strip(".")):
                h = common.hash_value(cand)
                if h in ctx["secret_hashes"]:
                    label = ctx["secret_hashes"][h]
                    findings.append(new_finding("CRITICAL", "IDENTITY_SECRET", file, line_no,
                                                f"내 정보(시크릿 · {label}): {common.redact(cand)}",
                                                "'내 정보'에 해시로 등록한 시크릿 값이 그대로 있다.", status, cand))
                    return


def identity_matchers(cfg):
    out = []
    for e in cfg.get("identity", []):
        val = str(e.get("value", "")).strip()
        if not val:
            continue
        kind = e.get("kind", "other")
        if kind == "secret":
            continue
        if kind == "phone":
            digits = re.sub(r"\D", "", val)
            if len(digits) < 9:
                continue
            rx = re.compile(r"[-. ]?".join(re.escape(d) for d in digits))
        elif kind in ("username", "name") and re.fullmatch(r"[A-Za-z0-9._-]+", val):
            rx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(val) + r"(?![A-Za-z0-9_])", re.I)
        else:
            rx = re.compile(re.escape(val), re.I)
        out.append((rx, e.get("label") or kind, kind, val))
    return out


# ---------------------------------------------------------------- 한 줄 검사

def new_finding(severity, rule, file, line, excerpt, why, status, raw="", fix=None):
    return {"severity": severity, "rule": rule, "file": file, "line": line, "excerpt": excerpt,
            "why": why, "fix": fix or FIX.get(rule, ""), "status": status,
            "priority": priority_of(rule, severity), "_raw": raw or excerpt}


def scan_line(text, file, line_no, status, ctx, findings):
    """Content rules that work per line. ctx carries compiled identity / code rules / config."""
    is_test = bool(TEST_PATH.search(file))
    is_comment = bool(COMMENT_LINE.match(text))
    for label, rx, why in SECRET_PATTERNS:
        for m in rx.finditer(text):
            if label == "DB 접속 문자열" and is_placeholder_url(m):
                continue
            if looks_fake(m.group(0)):
                continue
            findings.append(new_finding("CRITICAL", "SECRET", file, line_no,
                                        f"{label}: {common.redact(m.group(0))}", f"{label} — {why}", status, m.group(0)))
            break
    m = ASSIGN.search(text)
    if m:
        val = m.group("val")
        if (not PLACEHOLDER.match(val) and not LOW_ENTROPY.match(val) and not val.startswith(("http", "/", "."))
                and not looks_fake(val) and not EXAMPLE_NAME.search(m.group("name"))):
            findings.append(new_finding("HIGH", "SECRET_ASSIGN", file, line_no,
                                        f"{m.group('name')} = {common.redact(val)}",
                                        "이름과 값 모두 자격증명 형태.", status, val))
    for rx, label, kind, val in ctx["identity"]:
        m = rx.search(text)
        if m:
            findings.append(new_finding("HIGH", "IDENTITY", file, line_no,
                                        f"내 정보({label}): {val if kind in ('name', 'username') else common.redact(val)}",
                                        "설정의 '내 정보' 목록에 있는 값이 그대로 들어 있다.", status, val))
    secret_checks(text, file, line_no, status, ctx, findings)
    for m in RRN_RX.finditer(text):
        findings.append(new_finding("CRITICAL", "PII_RRN", file, line_no, common.redact(m.group(0)),
                                    "주민등록번호 형태.", status, m.group(0)))
        break
    for m in PHONE_RX.finditer(text):
        if PHONE_SKIP.search(m.group(0)):
            continue
        findings.append(new_finding("MEDIUM", "PII_PHONE", file, line_no, common.redact(m.group(0)),
                                    "휴대폰 번호 형태.", status, m.group(0)))
        break
    for m in EMAIL_RX.finditer(text):
        addr = m.group(0)
        local, domain = addr.rsplit("@", 1)
        if local.lower() in EMAIL_SKIP_LOCAL or EMAIL_SKIP_DOMAIN.search(domain) or "*" in addr:
            continue
        if len(local) < 3 or re.fullmatch(r"[A-Z_]{3,}", local) or re.fullmatch(r"[0-9a-f]{20,}", local):
            continue
        if m.start() > 0 and text[m.start() - 1] in ":/":  # URL 자격증명 user:pw@host 의 pw@host
            continue
        if domain.lower() in {d.lower() for d in ctx["cfg"].get("public_email_domains", [])}:
            continue
        if is_test:
            findings.append(new_finding("LOW", "PII_EMAIL_TEST", file, line_no, addr,
                                        "테스트·시드 파일의 이메일. 실제 사람 주소가 아닌지만 확인.", status, addr,
                                        fix="실제 주소면 example.com 으로 바꾼다."))
        else:
            findings.append(new_finding("MEDIUM", "PII_EMAIL", file, line_no, addr,
                                        "이메일 주소. 개인 주소면 공개 저장소에서 스팸·사칭 대상이 된다.", status, addr))
    for m in LOCAL_PATH_RX.finditer(text):
        name = m.group(1)
        if name.lower() in GENERIC_USERS:
            continue
        findings.append(new_finding("LOW", "PII_LOCAL_PATH", file, line_no, m.group(0),
                                    "로컬 절대 경로. OS 계정 이름이 드러난다.", status, m.group(0)))
        break
    if ctx["file_ext"] not in CODE_EXT:  # 코드에서 x-y-z 형태는 버전·ID 가 많아 문서만 본다
        m = BIZNO_RX.search(text)
        if m and not re.search(r"\d{3}-\d{2}-\d{5}-", text):
            findings.append(new_finding("LOW", "PII_BIZNO", file, line_no, m.group(0),
                                        "사업자등록번호 형태.", status, m.group(0)))
    if not is_test:
        for m in IPV4_RX.finditer(text):
            if public_ipv4(m) and not re.search(r"\d+\.\d+\.\d+\.\d+\.\d+", text):
                findings.append(new_finding("LOW", "PII_IP", file, line_no, m.group(0), "공인 IPv4 주소.", status, m.group(0)))
                break
    m = ADDRESS_RX.search(text)
    if m:
        findings.append(new_finding("LOW", "PII_ADDRESS", file, line_no, m.group(0), "도로명 주소 형태.", status, m.group(0)))
    if is_comment:  # 주석에서 규칙 이름을 언급한 것은 코드가 아니다
        return
    for rule_id, sev, exts, rx, why, fix in ctx["code_rules"]:
        if exts is not None and ctx["file_ext"] not in exts:
            continue
        m = rx.search(text)
        if m:
            findings.append(new_finding(sev, rule_id, file, line_no, text.strip()[:110], why, status, text, fix))


def scan_file_content(root, relpath, status, ctx, findings, passes):
    if SKIP_FILE.search(relpath):
        return
    ext = os.path.splitext(relpath)[1].lower()
    if ext in BINARY_EXT:
        return
    content = read_text(os.path.join(root, relpath))
    if content is None:
        return
    ctx["file_ext"] = ext
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if len(line) > 4000:
            continue
        scan_line(line, relpath, i, status, ctx, findings)
    if ext in CODE_EXT and re.search(r"['\"]use client['\"]", content[:400]) and re.search(r"service_role|SERVICE_ROLE", content):
        findings.append(new_finding("CRITICAL", "SERVICE_ROLE_CLIENT", relpath, 1, "\"use client\" + service_role",
                                    "클라이언트 번들로 가는 파일에서 service_role 을 참조한다.", status))
    if ext == ".sql":
        ctx["sql_files"].append((relpath, content))
    if relpath.endswith(("vercel.json",)):
        ctx["vercel_json"] = (relpath, content)
    if re.search(r"(^|/)middleware\.(ts|js|mjs)$", relpath):
        ctx["middleware"] = (relpath, content)
    if re.search(r"(^|/)app/(\([^/]+\)/)?admin/layout\.(tsx|jsx|ts|js)$", relpath):
        ctx["admin_layouts"].append((relpath, content))
    if re.search(r"(^|/)(app/(\([^/]+\)/)?(api/)?admin(/.*)?/(page|route)\.(tsx|ts|jsx|js)|pages/(api/)?admin(/.*)?\.(tsx|ts|jsx|js))$", relpath):
        ctx["admin_files"].append((relpath, content))
    if re.search(r"(^|/)app/api/cron/.*route\.(ts|js)$", relpath) or "cron" in relpath.lower():
        ctx["cron_files"].append((relpath, content))


# ---------------------------------------------------------------- 구조 검사

AUTH_HINT = re.compile(r"requireAdmin|verifySession|getSession|getServerSession|auth\(|currentUser|withAuth|isAdmin|"
                       r"session|cookies\(|redirect\(|NextAuth|supabase\.auth|getUser\(|totp|2fa|Unauthorized|401", re.I)


def structural_checks(root, files, ctx, findings, passes, cfg):
    tracked = {p for p, st in files if st == "tracked"}
    file_status = dict(files)

    # 경로 규칙
    for p, st in files:
        for rule_id, sev, rx, exempt, why, fix in FILE_RULES:
            if rx.search(p) and not (exempt and exempt.search(p)):
                if rule_id == "FILE_ENV_TRACKED" and st != "tracked":
                    # 미추적 .env 는 정상. 다만 gitignore 가 없으면 git add -A 에 딸려간다 - 아래 gitignore 검사가 잡는다.
                    continue
                findings.append(new_finding(sev, rule_id, p, 0, f"({'추적됨' if st == 'tracked' else '미추적'})", why, st, p, fix))
    if not any(f["rule"] == "FILE_ENV_TRACKED" for f in findings):
        passes.append(".env 계열 파일이 추적되지 않음")
    if not any(f["rule"] == "FILE_KEY" for f in findings):
        passes.append("개인키·서비스 계정 파일 없음")

    # .gitignore
    gi_path = os.path.join(root, ".gitignore")
    if is_git(root):
        gi = read_text(gi_path) or ""
        lines = [l.strip() for l in gi.splitlines() if l.strip() and not l.startswith("#")]

        def covered(*names):
            for n in names:
                for l in lines:
                    pat = l.lstrip("/").rstrip("/")
                    if fnmatch.fnmatch(n, pat) or fnmatch.fnmatch(n, pat + "/*") or pat == n or n.startswith(pat + "/"):
                        return True
            return False
        needs = [
            ((".env", ".env.local"), ".env / .env.local"),
            ((".claude/settings.local.json",), ".claude/settings.local.json"),
            ((".vercel",), ".vercel"),
            ((".mcp.json",), ".mcp.json"),
        ]
        missing = [label for names, label in needs if not covered(*names)]
        for label in missing:
            findings.append(new_finding("MEDIUM", "GITIGNORE_MISSING", ".gitignore", 0, label,
                                        f".gitignore 에 {label} 이 없다. git add -A 한 번에 딸려 들어간다.", "tracked"))
        if not missing:
            passes.append(".gitignore 가 .env·.claude/settings.local.json·.vercel·.mcp.json 을 덮음")

    # RLS 누락
    created, enabled, create_where = set(), set(), {}
    for relpath, content in ctx["sql_files"]:
        for m in re.finditer(r"create\s+table\s+(if\s+not\s+exists\s+)?(\"?(public|[a-z_]+)\"?\s*\.\s*)?\"?([a-z_][a-z0-9_]*)\"?", content, re.I):
            schema = (m.group(3) or "public").lower()
            if schema != "public":
                continue
            t = m.group(4).lower()
            created.add(t)
            create_where.setdefault(t, (relpath, content.count("\n", 0, m.start()) + 1))
        for m in re.finditer(r"alter\s+table\s+(if\s+exists\s+)?(only\s+)?(\"?(public|[a-z_]+)\"?\s*\.\s*)?\"?([a-z_][a-z0-9_]*)\"?\s+enable\s+row\s+level\s+security", content, re.I):
            enabled.add(m.group(5).lower())
    if ctx["sql_files"]:
        missing = sorted(created - enabled)
        for t in missing:
            f, ln = create_where[t]
            findings.append(new_finding("HIGH", "RLS_MISSING_SQL", f, ln, f"create table {t}",
                                        f"표 {t} 에 enable row level security 가 어느 SQL 에도 없다.", file_status.get(f, "tracked")))
        if created and not missing:
            passes.append(f"SQL 로 만든 표 {len(created)}개 모두 RLS enable 있음")
        if not any(f["rule"] == "RLS_OPEN_SQL" for f in findings):
            passes.append("RLS 개방 정책(using true / anon grant) 없음")

    # 크론 시크릿
    if ctx.get("vercel_json"):
        relpath, content = ctx["vercel_json"]
        try:
            crons = json.loads(content).get("crons", [])
        except ValueError:
            crons = []
        for c in crons:
            path = c.get("path", "")
            cands = [f for f, _ in ctx["cron_files"] if path.strip("/").replace("api/", "") in f]
            if not cands:
                findings.append(new_finding("LOW", "CRON_NO_SECRET", relpath, 0, path,
                                            "크론 라우트 파일을 찾지 못해 CRON_SECRET 검사를 확인할 수 없다.", "tracked",
                                            fix="라우트 파일 위치를 확인하고 직접 본다."))
                continue
            for f in cands:
                content_f = dict(ctx["cron_files"])[f]
                if "CRON_SECRET" not in content_f:
                    findings.append(new_finding("HIGH", "CRON_NO_SECRET", f, 1, path,
                                                "vercel.json 크론 라우트에 CRON_SECRET 검사가 없다. 누구나 부를 수 있는 주소.", "tracked"))
                else:
                    passes.append(f"크론 {path} 에 CRON_SECRET 검사 있음")

    # 어드민 보호 (휴리스틱)
    if ctx["admin_files"]:
        protected = False
        where = ""
        if ctx.get("middleware") and re.search(r"admin", ctx["middleware"][1], re.I) and AUTH_HINT.search(ctx["middleware"][1]):
            protected, where = True, ctx["middleware"][0]
        for lp, lc in ctx["admin_layouts"]:
            if AUTH_HINT.search(lc):
                protected, where = True, lp
        if protected:
            passes.append(f"어드민 보호가 {where} 에서 확인됨 (세션 검사 여부는 직접 한 번 더 본다)")
        else:
            unprotected = [f for f, c in ctx["admin_files"] if not AUTH_HINT.search(c)]
            for f in unprotected[:12]:
                findings.append(new_finding("MEDIUM", "ADMIN_NO_AUTH", f, 1, "admin 라우트에 인증 흔적 없음",
                                            "middleware·layout·파일 어디에도 세션 검사가 보이지 않는다 (휴리스틱).", file_status.get(f, "tracked")))
            if not unprotected:
                passes.append("어드민 라우트마다 인증 관련 코드가 있음 (휴리스틱)")

    # 커밋 작성자 이메일
    if is_git(root):
        log = common.git(["log", "--all", "--format=%ae|%an", "-n", "2000"], cwd=root) or ""
        seen = {}
        for line in log.splitlines():
            if "|" in line:
                e, n = line.split("|", 1)
                seen.setdefault(e.strip(), n.strip())
        personal = {e: n for e, n in seen.items() if e and "noreply" not in e.lower()}
        for e, n in list(personal.items())[:10]:
            sev = "HIGH" if any(e.lower() == str(i.get("value", "")).lower() for i in cfg.get("identity", [])) else "LOW"
            findings.append(new_finding(sev, "GIT_AUTHOR_EMAIL", "(git history)", 0, f"{e} ({n})",
                                        "커밋 작성자 이메일은 공개 저장소에서 누구나 본다.", "history", e))
        if seen and not personal:
            passes.append("커밋 작성자 이메일이 모두 noreply 주소")


# ---------------------------------------------------------------- diff / history

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def scan_diff_text(diff, status, ctx, findings, commit_label=None):
    current, line_no, skip = "?", 0, False
    ext = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            skip = bool(SKIP_FILE.search(current)) or os.path.splitext(current)[1].lower() in BINARY_EXT
            ext = os.path.splitext(current)[1].lower()
            continue
        if line.startswith("commit ") and commit_label is not None:
            commit_label[0] = line.split()[1][:10]
            continue
        m = HUNK.match(line)
        if m:
            line_no = int(m.group(1)) - 1
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        line_no += 1
        if skip or len(line) > 4000:
            continue
        ctx["file_ext"] = ext
        before = len(findings)
        scan_line(line[1:], current, line_no, status, ctx, findings)
        if commit_label is not None:
            for f in findings[before:]:
                f["commit"] = commit_label[0]


def scan_history(root, ctx, findings, rev_range):
    """Only high-confidence secret patterns + identity — history is big and noisy."""
    args = ["log", "-p", "--unified=0", "--no-color", "--diff-filter=AM", "--format=commit %H"]
    if rev_range:
        args.append(rev_range)
    else:
        args.append("--all")
    try:
        proc = subprocess.Popen(["git"] + args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding="utf-8", errors="replace")
    except OSError:
        return
    commit = "?"
    current, skip, read = "?", False, 0
    for line in proc.stdout:
        read += len(line)
        if read > 200_000_000:
            break
        if line.startswith("commit "):
            commit = line.split()[1][:10]
            continue
        if line.startswith("+++ b/"):
            current = line[6:].rstrip("\n")
            skip = bool(SKIP_FILE.search(current))
            continue
        if skip or not line.startswith("+") or line.startswith("+++") or len(line) > 4000:
            continue
        text = line[1:]
        for label, rx, why in SECRET_PATTERNS:
            m = rx.search(text)
            if m and not (label == "DB 접속 문자열" and is_placeholder_url(m)) and not looks_fake(m.group(0)):
                findings.append(new_finding("CRITICAL", "HISTORY_SECRET", current, 0,
                                            f"{label}: {common.redact(m.group(0))} @ {commit}",
                                            f"과거 커밋에 {label}. 지금 지워도 이력에 남아 있다.", "history", m.group(0)))
                break
        for rx, label, kind, val in ctx["identity"]:
            if kind in ("email", "phone") and rx.search(text):
                findings.append(new_finding("MEDIUM", "HISTORY_SECRET", current, 0,
                                            f"내 정보({label}) @ {commit}", "과거 커밋에 내 정보.", "history", val,
                                            fix="이력에 남은 개인정보. 공개 저장소면 filter-repo 로 정리하거나 감수한다."))
        before = len(findings)
        secret_checks(text, current, 0, "history", ctx, findings)
        for f in findings[before:]:
            f["rule"], f["commit"] = "HISTORY_SECRET", commit
            f["excerpt"] += f" @ {commit}"
            f["priority"] = "now"
    proc.stdout.close()
    proc.wait(timeout=10)


def scan_build(root, ctx, findings, passes):
    bdir = os.path.join(root, ".next", "static")
    if not os.path.isdir(bdir):
        return
    hits = 0
    for dirpath, _, filenames in os.walk(bdir):
        for fn in filenames:
            if not fn.endswith((".js", ".json", ".txt")):
                continue
            content = read_text(os.path.join(dirpath, fn))
            if not content:
                continue
            relp = os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/")
            for label, rx, why in SECRET_PATTERNS:
                m = rx.search(content)
                if m and not (label == "DB 접속 문자열" and is_placeholder_url(m)) and not looks_fake(m.group(0)):
                    findings.append(new_finding("CRITICAL", "BUILD_LEAK", relp, 0, f"{label}: {common.redact(m.group(0))}",
                                                "브라우저 번들에 시크릿.", "build", m.group(0)))
                    hits += 1
            if re.search(r"service_role|SUPABASE_SERVICE", content):
                findings.append(new_finding("CRITICAL", "BUILD_LEAK", relp, 0, "service_role 문자열",
                                            "브라우저 번들에 service_role 참조.", "build"))
                hits += 1
            for rx, label, kind, val in ctx["identity"]:
                if rx.search(content):
                    findings.append(new_finding("HIGH", "BUILD_LEAK", relp, 0, f"내 정보({label})",
                                                "브라우저 번들에 내 정보.", "build", val))
                    hits += 1
            before = len(findings)
            for i, line in enumerate(content.splitlines(), 1):
                secret_checks(line, relp, i, "build", ctx, findings)
            for f in findings[before:]:
                f["rule"] = "BUILD_LEAK"
                f["why"] = "브라우저 번들에 " + f["why"]
            hits += len(findings) - before
    if not hits:
        passes.append(".next/static 번들에 시크릿·service_role·내 정보·.env 값 없음")


# ---------------------------------------------------------------- 정리 · 보고서

def condense(findings):
    """Group repeats: same rule+file → one line with count; PII_EMAIL/IDENTITY → by value across files."""
    groups = {}
    for f in findings:
        if f["rule"] in ("PII_EMAIL", "IDENTITY", "IDENTITY_SECRET", "ENV_VALUE_LEAK", "GIT_AUTHOR_EMAIL", "HISTORY_SECRET"):
            key = (f["rule"], f.get("_raw", f["excerpt"]).lower())
        else:
            key = (f["rule"], f["file"])
        groups.setdefault(key, []).append(f)
    out = []
    for key, items in groups.items():
        head = dict(items[0])
        head["count"] = len(items)
        files = sorted({i["file"] for i in items})
        if len(items) > 1:
            if len(files) > 1:
                head["file"] = f"{files[0]} 외 {len(files) - 1}개 파일"
                head["files"] = files[:20]
            head["excerpt"] = f"{head['excerpt']}   (총 {len(items)}곳)"
        out.append(head)
    out.sort(key=lambda f: ({"now": 0, "week": 1, "later": 2}[f["priority"]], -common.RANK[f["severity"]], f["file"], f["line"]))
    return out


CALM = {
    "green": ("🟢 발 뻗고 자도 됩니다", "밖으로 나가면 안 되는 것은 하나도 없다. 남은 건 시간 날 때 다듬는 정리 항목뿐."),
    "yellow": ("🟡 올려도 되지만, 이번 주에 한 번 손봅니다", "지금 당장 항목은 없다. 공개 전에 빼는 편이 싼 것(개인정보·열린 설정)이 있으니 리포트를 훑고 올린다."),
    "red": ("🔴 지금은 올리지 마세요", "시크릿·내 정보·열린 설정이 나간다. 값을 빼고, 이미 커밋된 키는 재발급한 뒤 다시 점검한다."),
}


def calm_level(now, week):
    """불안은 대부분 '모르는 것'에서 온다. 무엇을 봤고 어디까지 괜찮은지를 한 줄로 말해 준다."""
    if now:
        return CALM["red"]
    if week:
        return CALM["yellow"]
    return CALM["green"]


def render(target, mode, files, findings, allowed, passes, cfg, extra):
    by = {"now": [], "week": [], "later": []}
    for f in findings:
        by[f["priority"]].append(f)
    name = os.path.basename(os.path.abspath(target))
    out = [f"# 스폰지보안 · 공개 전 점검: {name}", ""]
    out.append(f"- 대상: `{os.path.abspath(target)}`")
    out.append(f"- 모드: {mode}" + (" + 이력" if extra.get("history") else "") + (" + 빌드" if extra.get("build") else ""))
    out.append(f"- 시각: {common.now()}")
    if extra.get("remote"):
        out.append(f"- 원격: {extra['remote']}")
    if extra.get("branch"):
        out.append(f"- 브랜치: {extra['branch']}")
    out.append(f"- 점검 파일: {len(files)}개 (추적 {sum(1 for _, s in files if s == 'tracked')} / 미추적 {sum(1 for _, s in files if s == 'untracked')})")
    out.append(f"- 내 정보 목록: {len(cfg.get('identity', []))}개 · 예외 {len(cfg.get('allow', []))}개 · 사용자 규칙 {len(cfg.get('rules', []))}개")
    out.append("")
    out.append(f"## 한 줄 요약: **지금 당장 {len(by['now'])} · 이번 주 {len(by['week'])} · 나중에 {len(by['later'])}**"
               + (f" (예외로 제외 {len(allowed)})" if allowed else ""))
    out.append("")
    label, note = calm_level(len(by["now"]), len(by["week"]))
    out.append(f"**안심 등급: {label}** — {note}")
    out.append("")
    if by["now"]:
        out.append("> **지금 당장 항목이 있으면 push·배포를 멈춘다.** 이미 커밋된 시크릿은 지우는 게 아니라 재발급이 답이다.")
    else:
        out.append("> 지금 당장 항목 없음. 이번 주 항목은 공개 후에도 고칠 수 있지만, 개인정보는 공개 전에 빼는 편이 싸다.")
    out.append("")
    for key in ("now", "week", "later"):
        out.append(f"## {PRIO_LABEL[key]} ({len(by[key])})")
        out.append("")
        if not by[key]:
            out.append("- 없음")
            out.append("")
            continue
        for f in by[key]:
            loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
            st = {"tracked": "추적됨", "untracked": "미추적", "staged": "스테이지", "history": "이력", "build": "빌드", "folder": ""}.get(f["status"], f["status"])
            out.append(f"- **[{f['rule']}]** `{loc}`" + (f" ({st})" if st else "") + (f" @ {f['commit']}" if f.get("commit") else ""))
            out.append(f"  - 발췌: `{f['excerpt']}`")
            out.append(f"  - 왜: {f['why']}")
            if f.get("fix"):
                out.append(f"  - 고치기: {f['fix']}")
            if f.get("files"):
                out.append(f"  - 파일: {', '.join('`' + x + '`' for x in f['files'][:8])}" + (" …" if len(f["files"]) > 8 else ""))
        out.append("")
    out.append("## 통과")
    out.append("")
    for p in passes or ["(자동으로 확인할 수 있는 항목이 없었음)"]:
        out.append(f"- {p}")
    out.append("")
    if allowed:
        out.append("## 예외로 제외")
        out.append("")
        for f in allowed:
            out.append(f"- [{f['rule']}] `{f['file']}` — {f.get('allow_reason') or '(사유 없음)'}")
        out.append("")
    out.append("## 저장소 밖에서 직접 확인할 것 (스폰지클럽 5회차 01-4)")
    out.append("")
    out.append("- Vercel: service_role 같은 값이 **Production 에만** 있는가. Preview 배포에서 실제 DB 에 쓰기가 되지 않는가")
    out.append("- Supabase: Data API 가 꺼져 있거나, 켜져 있다면 anon 키로 REST 를 직접 호출해 빈 배열/401 이 나오는가")
    out.append("- Supabase: Storage 버킷 중 public 인 것에 개인정보가 없는가")
    out.append("- 어드민 주소를 시크릿 창에서 열어 로그인 없이 들어가지지 않는가 (vercel.app 주소도)")
    out.append("- 실제로 받는 항목과 개인정보처리방침의 항목이 같은가. 동의 체크박스가 항목별로 분리돼 있는가")
    out.append("")
    out.append("## 역할 나누기")
    out.append("")
    out.append("- **사용자가 직접**: 키 재발급, 결제·플랜, 데이터·배포 삭제, 대시보드 설정 변경")
    out.append("- **AI 가 승인받고**: 코드에서 값 제거, .gitignore 수정, git rm --cached, 마스킹·검증 코드 추가")
    return "\n".join(out), by


def run(target, mode="tree", history=False, build=False, save=True):
    cfg = common.load_config()
    root = os.path.abspath(target)
    if not os.path.isdir(root):
        raise RuntimeError(f"디렉터리가 아닙니다: {target}")
    ctx = {"cfg": cfg, "identity": identity_matchers(cfg), "code_rules": CODE_RULES + [
        (rid, sev, None, rx, why, "") for rid, sev, cat, rx, why in common.custom_rules(cfg, "publish")],
        "sql_files": [], "cron_files": [], "admin_files": [], "admin_layouts": [], "file_ext": "",
        "secret_hashes": {e["hash"]: e.get("label") or "시크릿" for e in cfg.get("identity", [])
                          if e.get("kind") == "secret" and e.get("hash")},
        "env_values": []}
    findings, passes = [], []
    files = []
    # gitignore 된 .env 의 값은 어느 모드에서든 대조한다 — 그 값이 이 프로젝트의 진짜 시크릿이다
    ctx["env_values"] = env_secret_matchers(root, collect_files(root, cfg))
    extra_env = None
    if ctx["env_values"]:
        srcs = sorted({s for _, _, s in ctx["env_values"]})
        extra_env = f"gitignore 된 {', '.join(srcs)} 의 값 {len(ctx['env_values'])}개"
    extra = {"history": history, "build": build}
    if is_git(root):
        extra["remote"] = (common.git(["remote", "get-url", "origin"], cwd=root) or "").strip() or None
        extra["branch"] = (common.git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root) or "").strip() or None

    if mode == "staged":
        diff = common.git(["diff", "--cached", "--unified=0", "--no-color"], cwd=root)
        if diff is None:
            raise RuntimeError("git 저장소가 아니거나 diff 를 읽을 수 없음")
        scan_diff_text(diff, "staged", ctx, findings)
        files = [(p, "staged") for p in re.findall(r"^\+\+\+ b/(.+)$", diff, re.M)]
    else:
        files = collect_files(root, cfg)
        for p, st in files:
            scan_file_content(root, p, st, ctx, findings, passes)
        structural_checks(root, files, ctx, findings, passes, cfg)
        if mode == "push" and is_git(root):
            upstream = common.git(["rev-parse", "--abbrev-ref", "@{u}"], cwd=root)
            rng = "@{u}..HEAD" if upstream else None
            scan_history(root, ctx, findings, rng)
            extra["history"] = True
            extra["history_range"] = rng or "(upstream 없음 → 전체 이력)"
        elif history and is_git(root):
            scan_history(root, ctx, findings, None)
    if build:
        scan_build(root, ctx, findings, passes)

    if extra_env and not any(f["rule"] in ("ENV_VALUE_LEAK", "HISTORY_SECRET", "BUILD_LEAK") and "값" in f["excerpt"] for f in findings):
        passes.append(f"{extra_env} — 공개될 파일 어디에도 없음")
    if ctx["secret_hashes"] and not any(f["rule"] == "IDENTITY_SECRET" for f in findings):
        passes.append(f"'내 정보'의 시크릿 {len(ctx['secret_hashes'])}개 — 공개될 파일 어디에도 없음")
    findings, allowed = common.apply_allowlist(findings, cfg)
    findings = condense(findings)
    allowed = condense(allowed)
    text, by = render(target, mode, files, findings, allowed, passes, cfg, extra)
    common.strip_private(findings)
    common.strip_private(allowed)
    summary = {"now": len(by["now"]), "week": len(by["week"]), "later": len(by["later"]), "allowed": len(allowed),
               "files": len(files)}
    verdict = "STOP" if by["now"] else ("FIX-THIS-WEEK" if by["week"] else "OK")
    summary["calm"], summary["calm_note"] = calm_level(len(by["now"]), len(by["week"]))
    data = {"kind": "publish", "target": root, "mode": mode, "verdict": verdict, "summary": summary,
            "findings": findings, "allowed": allowed, "passes": passes, "extra": extra, "at": common.now()}
    rid = None
    if save:
        rid = common.save_report("publish", os.path.basename(root), text, data)
        common.remember_target(cfg, root)
        common.save_config(cfg)
    data["report_id"] = rid
    data["markdown"] = text
    return data


def main():
    ap = argparse.ArgumentParser(description="스폰지보안 — 공개 전 점검 (push·배포 전에 시크릿·내 정보·설정을 본다)")
    ap.add_argument("target", nargs="?", default=".", help="저장소 경로 (기본: 현재 폴더)")
    ap.add_argument("--mode", choices=["tree", "staged", "push"], default="tree",
                    help="tree: 추적+미추적 파일 전체 / staged: 스테이지된 변경만 / push: tree + 아직 push 안 된 커밋 이력")
    ap.add_argument("--history", action="store_true", help="전체 커밋 이력에서 시크릿·내 정보 찾기 (느릴 수 있음)")
    ap.add_argument("--build", action="store_true", help=".next/static 번들도 본다 (next build 뒤에)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()
    try:
        data = run(args.target, args.mode, args.history, args.build, save=not args.no_save)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        data.pop("markdown")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data["markdown"])
        if data.get("report_id"):
            print(f"\n(리포트 저장: {os.path.join(common.REPORTS, data['report_id'] + '.md')})")
    return 1 if data["summary"]["now"] else 0


if __name__ == "__main__":
    sys.exit(main())
