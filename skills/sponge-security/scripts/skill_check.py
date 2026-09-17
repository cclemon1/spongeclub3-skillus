#!/usr/bin/env python3
"""스폰지보안 · 모드 A — 외부 스킬 정적 심사.

Reads a skill directory / .skill archive / git URL WITHOUT executing anything
in it, and reports candidates grouped by severity. Two layers:

  1. 일반 위협 규칙   — 유출·자격증명·실행·난독화·프롬프트 인젝션 (skill-audit 계열)
  2. 스폰지클럽 규범  — SP_* 규칙. 스폰지클럽에서 정한 "스킬이 절대 하지 않는 것"
                        (키를 채팅으로 요청, 입력창에 타이핑, 데이터·배포 삭제, 결제·플랜,
                        화면 속 지시문 따르기, 운영 DB 직접 조작, 승인 없는 push,
                        NEXT_PUBLIC_ 에 시크릿, RLS 개방)

The scanner finds candidates. Whether a candidate is malicious or benign is
decided by reading SKILL.md — see SKILL.md of this skill.

Usage:
    python skill_check.py <dir | file.skill | https://github.com/...> [--json] [--no-save]

Exit code: 1 if verdict is BLOCK, else 0.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

MAX_FILE_BYTES = 2_000_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}
BINARY_EXT = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".class", ".jar",
    ".pyc", ".pyd", ".wasm", ".msi", ".tar", ".gz", ".7z", ".rar",
    ".pkg", ".deb", ".rpm", ".apk", ".scr", ".com",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".woff", ".woff2", ".ttf"}
ARCHIVE_EXT = {".skill", ".zip", ".plugin"}
MAX_ARCHIVE_DEPTH = 2
RANK = common.RANK


def _r(p):
    return re.compile(p, re.IGNORECASE)


# 한국어 부정 어미. "삭제하지 않는다", "요청하지 말 것", "금지" 가 뒤따르면 그 문장은
# 규칙을 *지키라는* 말이지 어기라는 말이 아니다.
# 창을 24자로 둔 이유: "데이터·표·배포 삭제, 대시보드 설정 변경을 하지 않는다" 처럼 목록 뒤에 부정이 오는
# 문장이 규범 문서에 흔하다. 악의적 지시문이 24자 안에 부정어를 두는 경우는 드물다.
NEG = r"(?![^\n]{0,24}(않|말\s|말것|말고|안\s*된|안\s*됨|금지|없다|없음|never|not\b|don't|do not))"

RULES = [
    # --- 유출: 스킬 안에서 밖으로 나가는 통신 --------------------------------
    ("NET_PIPE_EXEC", "CRITICAL", "network",
     _r(r"\b(curl|wget)\b[^\n|]*\|\s*(ba)?sh\b"),
     "원격 스크립트를 받아 즉시 실행(curl|bash). 임의 코드 실행 경로."),
    ("NET_SHELL", "HIGH", "network",
     _r(r"\b(curl|wget)\s+(?!--help)"),
     "셸에서 외부 네트워크 호출. 유출 또는 2차 페이로드 다운로드에 쓰임."),
    ("NET_CODE", "HIGH", "network",
     _r(r"(requests\.(get|post|put)|urllib\.request|http\.client|axios\.|fetch\s*\(|Invoke-WebRequest|Invoke-RestMethod|Net\.WebClient)"),
     "코드에서 외부 HTTP 호출. 무엇을 어디로 보내는지 확인."),
    ("NET_RAWSOCK", "HIGH", "network",
     _r(r"\b(nc|ncat|netcat|socat)\s+-|socket\.socket\("),
     "원시 소켓 / 리버스 셸에 쓰일 수 있는 명령."),
    ("NET_URL", "MEDIUM", "network",
     _r(r"https?://(?!(?:github\.com|raw\.githubusercontent\.com|gist\.github\.com"
        r"|gist\.githubusercontent\.com|docs\.anthropic\.com|www\.anthropic\.com"
        r"|api\.anthropic\.com|claude\.ai|localhost|127\.0\.0\.1|example\.com"
        r"|developer\.mozilla\.org|pypi\.org|npmjs\.com|www\.npmjs\.com"
        r"|schema\.org|www\.w3\.org|fonts\.googleapis\.com|fonts\.gstatic\.com"
        r"|cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com|vercel\.com|supabase\.com"
        r")(?=[/\s\"'),;:]|$))[a-z0-9.-]+"),
     "낯선 외부 도메인 하드코딩. 유출 대상일 수 있음."),
    ("GIT_REMOTE", "MEDIUM", "network",
     _r(r"git\s+(push|remote\s+add)\b"),
     "코드를 외부 저장소로 내보낼 수 있음."),

    # --- 자격증명 -------------------------------------------------------------
    ("CRED_CLAUDE", "CRITICAL", "credentials",
     _r(r"\.credentials\.json|CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY"),
     "Claude Code 자격증명/API 키 접근. 정당한 이유가 거의 없음."),
    ("CRED_SSH", "CRITICAL", "credentials",
     _r(r"\.ssh[/\\]|id_rsa|id_ed25519|authorized_keys"),
     "SSH 개인키 접근."),
    ("CRED_CLOUD", "CRITICAL", "credentials",
     _r(r"\.aws[/\\]credentials|AWS_SECRET_ACCESS_KEY|gcloud[/\\]credentials|AZURE_CLIENT_SECRET|\.kube[/\\]config"),
     "클라우드 자격증명 접근."),
    ("CRED_BROWSER", "CRITICAL", "credentials",
     _r(r"Login Data|cookies\.sqlite|Local State|browser[^\n]{0,20}(cookie|password)"),
     "브라우저에 저장된 비밀번호/쿠키 접근."),
    ("CRED_STORE", "HIGH", "credentials",
     _r(r"\.git-credentials|\.npmrc|\.pypirc|\.netrc|security\s+find-generic-password|Get-Credential|cmdkey"),
     "자격증명 저장소 접근."),
    ("CRED_DOTENV", "HIGH", "credentials",
     _r(r"(^|[\s'\"/\\(])\.env(\.[a-z]+)?([\s'\"),]|$)|dotenv"),
     ".env 파일 접근. 시크릿이 모여 있는 곳. 읽는지 만드는지 구분."),
    ("CRED_GENERIC", "MEDIUM", "credentials",
     _r(r"\b(api[_-]?key|secret[_-]?key|access[_-]?token|private[_-]?key|password\s*=)"),
     "시크릿 관련 식별자. 읽는 쪽인지 만드는 쪽인지 구분 필요."),

    # --- 실행·난독화 ---------------------------------------------------------
    ("EXEC_DYNAMIC", "HIGH", "execution",
     _r(r"\beval\s*\(|\bexec\s*\(|new\s+Function\s*\(|Invoke-Expression|(^|[\s;|])iex(\s|$)"),
     "동적 코드 실행. 난독화된 페이로드를 돌리는 전형적 수단."),
    ("EXEC_SHELL", "MEDIUM", "execution",
     _r(r"os\.system\(|subprocess\.(run|call|Popen|check_output)|child_process|execSync|spawnSync|Start-Process"),
     "하위 프로세스 실행. 무엇을 실행하는지 확인."),
    ("OBF_BASE64_CALL", "HIGH", "obfuscation",
     _r(r"base64\s+(-d|--decode)|b64decode|atob\s*\(|FromBase64String"),
     "base64 디코딩. 숨긴 명령을 푸는 용도일 수 있음."),
    ("OBF_HEX", "MEDIUM", "obfuscation",
     _r(r"(\\x[0-9a-f]{2}){6,}|chr\(\d+\)\s*\+\s*chr\("),
     "문자열 난독화 흔적."),

    # --- 프롬프트 인젝션 (자연어) ---------------------------------------------
    ("PI_HIDE", "CRITICAL", "prompt-injection",
     _r(r"(do not|do n't|don't|never)\s+(tell|inform|mention|show|notify|reveal|display)[^\n]{0,40}\buser\b|"
        r"hide[^\n]{0,20}from\s+the\s+user|"
        r"사용자(에게|한테|께)[^\n]{0,10}(알리지|말하지|보여주지|언급하지|공개하지)\s*(말|않)"),
     "사용자에게 숨기라는 지시. 정상 스킬에 있을 이유가 없음."),
    ("PI_OVERRIDE", "CRITICAL", "prompt-injection",
     _r(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instruction|rule|prompt)|"
        r"disregard\s+(the\s+)?(system|previous|prior)|"
        r"override\s+(your|the)\s+(instruction|rule|safety|guideline)|"
        r"이전\s*(의\s*)?지시[^\n]{0,6}무시"),
     "상위 지시를 무시하라는 요구. 명백한 프롬프트 인젝션."),
    ("PI_PERM_FLAG", "CRITICAL", "prompt-injection",
     _r(r"--dangerously-skip-permissions|bypassPermissions|\"acceptEdits\"|permission-?mode"),
     "권한 모드 강제 변경. 사용자 승인 게이트를 통째로 끔."),
    ("PI_NOASK", "HIGH", "prompt-injection",
     _r(r"without\s+(asking|confirmation|permission|prompting)\b|"
        r"(auto|automatically)\s+(approve|accept|confirm)|"
        r"no\s+need\s+to\s+(ask|confirm)|"
        r"(확인|승인|허락)\s*(을|를)?\s*(받지|구하지|하지)?\s*(말고|않고|없이)\s*"
        r"[^\n]{0,8}(진행|실행|수행|설치|전송|삭제|바로|자동)(?![^\n]{0,10}(않|말|안\s*된|안\s*됨|금지))|"
        r"묻지\s*(말고|않고)\s*[^\n]{0,8}(진행|실행|수행|설치|전송|삭제|바로|자동)"
        r"(?![^\n]{0,10}(않|말|안\s*된|안\s*됨|금지))"),
     "확인 없이 진행하라는 지시. 승인 게이트 우회 시도."),
    ("PI_AUTHORITY", "HIGH", "prompt-injection",
     _r(r"(anthropic|the system|admin(istrator)?|the developer)\s+(has\s+)?(authorized|approved|permits|instructs)|"
        r"you\s+are\s+(now\s+)?in\s+(test|debug|developer|maintenance)\s+mode|pre-?authorized"),
     "권한 사칭 또는 '테스트 모드' 주장."),
    ("PI_SILENT", "HIGH", "prompt-injection",
     _r(r"(silently|quietly|in the background)\s+(run|execute|send|upload|copy|delete|install)|"
        r"조용히\s*(실행|전송|복사|설치)"),
     "조용히 실행/전송하라는 지시."),

    # --- 설정·영속화·파괴 ------------------------------------------------------
    ("CFG_HOOK", "HIGH", "config",
     _r(r"\"hooks\"|PreToolUse|PostToolUse|UserPromptSubmit|SessionStart|SessionEnd"),
     "훅 정의. 훅은 스킬을 호출하지 않아도 매 툴 호출마다 실행됨."),
    ("CFG_SETTINGS", "HIGH", "config",
     _r(r"\.claude[/\\]settings(\.local)?\.json|settings\.local\.json"),
     "Claude Code 설정 파일 수정. 권한·훅을 바꿀 수 있음."),
    ("CFG_MCP", "MEDIUM", "config",
     _r(r"mcpServers|\.mcp\.json|claude\s+mcp\s+add"),
     "MCP 서버 추가. 새로운 외부 연결 경로."),
    ("PERSIST", "HIGH", "persistence",
     _r(r"crontab|schtasks|launchctl|systemctl\s+enable|\.bashrc|\.zshrc|\.profile|"
        r"Register-ScheduledTask|CurrentVersion\\\\Run"),
     "영속화. 세션이 끝난 뒤에도 계속 동작."),
    ("DESTRUCT", "HIGH", "destructive",
     _r(r"rm\s+-rf\s+[/~$*]|['\"]rm['\"]\s*,\s*['\"]-[rf]{2}['\"]|"
        r"Remove-Item[^\n]{0,40}-Recurse[^\n]{0,20}-Force|"
        r"git\s+push\s+--force|git\s+reset\s+--hard|DROP\s+TABLE|shutil\.rmtree"),
     "파괴적 명령."),

    # --- 스폰지클럽 규범 (SP_*) ------------------------------------------------
    # 스폰지클럽 5회차 어드민 키트가 정한 "절대 하지 않는 것" 을 지시문에서 찾는다.
    ("SP_ASK_SECRET", "HIGH", "sponge",
     _r(r"(ask|prompt|request)[^\n]{0,20}\buser\b[^\n]{0,20}\b(for|to)\b[^\n]{0,30}\b(api[ _-]?key|password|secret|token|service[ _-]?role)\b" + NEG + r"|"
        r"(paste|enter|type|send|share)[^\n]{0,12}\b(your|the|me)\b[^\n]{0,20}\b(api[ _-]?key|password|secret|token|service[ _-]?role)\b" + NEG + r"|"
        r"(api\s*키|키|비밀번호|시크릿|토큰|암호|service[ _-]?role)(값)?(를|을|이|가)?\s*[^\n]{0,10}"
        r"(입력하세요|입력해\s*주세요|알려\s*주세요|알려주세요|보내\s*주세요|붙여\s*넣(어|으)|채팅(으로|에)\s*(달라|요청|입력))" + NEG),
     "키·비밀번호를 채팅으로 받으라는 지시. 스폰지클럽 규범: 키는 사용자가 직접 넣는다."),
    ("SP_TYPE_SECRET", "HIGH", "sponge",
     _r(r"(type|enter|fill|input)[^\n]{0,25}\b(password|api[ _-]?key|secret|token|card\s*number)\b[^\n]{0,30}\b(field|input|form|browser|dashboard|console)\b" + NEG + r"|"
        r"(비밀번호|api\s*키|키|시크릿|토큰|카드\s*번호)(를|을)?[^\n]{0,15}(입력창|폼|필드|브라우저|대시보드|콘솔)[^\n]{0,12}(입력|타이핑|채워|넣)" + NEG),
     "브라우저 입력창에 키·비밀번호를 타이핑하라는 지시. 키가 필요한 화면은 사용자에게 넘겨야 한다."),
    ("SP_DELETE_DATA", "HIGH", "sponge",
     _r(r"\btruncate\s+table\b|\bdelete\s+from\s+[a-z_\".]+\s*(;|$)|"
        r"\bvercel\s+(rm|remove|projects?\s+rm)\b|\bsupabase\s+projects\s+delete\b|\bgh\s+repo\s+delete\b|"
        r"\bfirebase\s+(firestore:delete|projects:delete)\b|"
        r"(표|테이블|데이터|배포|프로젝트|저장소|레포)(를|을)?\s*(전부|모두|통째로)?\s*(삭제|지우|드롭|날리)" + NEG),
     "데이터·표·배포·프로젝트 삭제 지시. 스폰지클럽 규범: 삭제는 사용자가 한다."),
    ("SP_PAYMENT", "MEDIUM", "sponge",
     _r(r"(결제\s*(계정|수단|정보)[^\n]{0,10}(연결|등록|입력)|플랜[^\n]{0,6}(변경|업그레이드|전환)|(계정|어카운트)[^\n]{0,6}(생성|만들|가입))" + NEG + r"|"
        r"(\b(add|enter|link|connect)\b[^\n]{0,20}\b(payment|billing|credit\s*card)\b|"
        r"\b(upgrade|change|switch)\b\s+(the\s+|your\s+|to\s+(a|the)\s+)?(paid\s+|pro\s+|billing\s+|pricing\s+)?plan\b|"
        r"\b(create|sign\s*up\s+for|register)\s+(a\s+|an\s+|new\s+|your\s+)?(\w+\s+)?account\b)" + NEG),
     "결제·플랜·계정 생성 지시. 스폰지클럽 규범: 돈과 계정은 스킬이 건드리지 않는다."),
    ("SP_FOLLOW_SCREEN", "CRITICAL", "sponge",
     _r(r"(follow|obey|execute|carry\s+out)[^\n]{0,30}\b(instructions?|commands?|directions?)\b[^\n]{0,30}\b(on|in|from)\s+(the\s+)?(page|screen|file|data|document|output|response|website)\b" + NEG + r"|"
        r"(화면|페이지|파일|데이터|출력|응답|웹사이트)[^\n]{0,10}(속|안|에\s*있는|에\s*적힌|의)\s*(지시|명령|안내)(문)?[^\n]{0,15}(따르|따라|실행|수행)" + NEG),
     "화면·데이터 속 지시문을 따르라는 지시. 프롬프트 인젝션을 스킬이 스스로 여는 것."),
    ("SP_PROD_DB", "MEDIUM", "sponge",
     _r(r"\b(production|prod)\s*(db|database)\b[^\n]{0,25}\b(directly|manually|modify|alter|update|write|delete|drop)\b" + NEG + r"|"
        r"(운영|프로덕션|실제)\s*(db|database|데이터베이스|디비)[^\n]{0,20}(직접|수정|변경|조작|삭제|쓰기)" + NEG),
     "운영 DB 를 직접 조작하라는 지시. 마이그레이션은 파일로, 파괴적 변경은 승인 뒤에만."),
    ("SP_AUTO_PUSH", "MEDIUM", "sponge",
     _r(r"\bcommit\b[^\n]{0,12}\b(and|then|&&)\s+[^\n]{0,8}\bpush\b(?![^\n]{0,25}(ask|approv|confirm|permission))|"
        r"커밋[^\n]{0,10}(하고|후|한\s*뒤|→|→)[^\n]{0,8}(push|푸시)(?![^\n]{0,20}(승인|확인|물어))"),
     "커밋 후 원격으로 push 하는 스킬. 승인 시점이 있는지 확인. (스폰지 어드민 키트처럼 의도된 설계일 수 있음)"),
    ("SP_PUBLIC_SECRET", "HIGH", "sponge",
     _r(r"\b(NEXT_PUBLIC|VITE|REACT_APP|EXPO_PUBLIC|NUXT_PUBLIC|PUBLIC)_[A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE|PASSWORD|PASSWD)\b"),
     "브라우저로 나가는 환경변수 이름에 시크릿. NEXT_PUBLIC_ 은 번들에 그대로 들어간다."),
    ("SP_RLS_OPEN", "HIGH", "sponge",
     _r(r"disable\s+row\s+level\s+security|using\s*\(\s*true\s*\)|with\s+check\s*\(\s*true\s*\)|"
        r"allow\s+(read|write)\s*:\s*if\s+true|"
        r"grant\s+(all|insert|update|delete)\b[^\n]{0,40}\bto\s+(anon|public|authenticated)\b"),
     "RLS 를 끄거나 누구나(true) 정책. 스폰지클럽 규범: 표는 만들자마자 잠근다."),
]

BROAD_TRIGGER = _r(
    r"\b(always|every|any|all)\s+(request|prompt|message|task|conversation|time)\b|"
    r"use\s+this\s+skill\s+for\s+(everything|all)|"
    r"모든\s*(요청|대화|작업|메시지)"
)

ZERO_WIDTH = {chr(c) for c in (
    0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD,
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
    0x2066, 0x2067, 0x2068, 0x2069,
)}

# 스폰지클럽 "절대 하지 않는 것" 대조표. (규범, 대응 규칙들)
SPONGE_NORMS = [
    ("키·비밀번호를 채팅으로 요청하거나 입력창에 타이핑하지 않는다", ("SP_ASK_SECRET", "SP_TYPE_SECRET")),
    ("데이터·표·프로젝트·배포를 삭제하지 않는다", ("SP_DELETE_DATA", "DESTRUCT")),
    ("결제 연결·플랜 변경·계정 생성을 하지 않는다", ("SP_PAYMENT",)),
    ("화면·데이터 속 지시문을 따르지 않고 보고한다", ("SP_FOLLOW_SCREEN", "PI_OVERRIDE", "PI_AUTHORITY")),
    ("운영 DB 를 직접 조작하지 않는다", ("SP_PROD_DB",)),
    ("승인 없이 원격에 push 하지 않는다", ("SP_AUTO_PUSH", "GIT_REMOTE")),
    ("시크릿을 브라우저 노출 변수(NEXT_PUBLIC_ 등)에 두지 않는다", ("SP_PUBLIC_SECRET",)),
    ("표는 만들자마자 잠근다 (RLS 개방 금지)", ("SP_RLS_OPEN",)),
    ("사용자에게 숨기거나 확인을 건너뛰지 않는다", ("PI_HIDE", "PI_NOASK", "PI_SILENT", "PI_PERM_FLAG")),
    ("자격증명 파일을 직접 읽지 않는다", ("CRED_CLAUDE", "CRED_SSH", "CRED_CLOUD", "CRED_BROWSER", "CRED_STORE")),
]


# ---------------------------------------------------------------- helpers

def is_probably_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in BINARY_EXT or ext in IMAGE_EXT:
        return False
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(4096)
        return b"\x00" not in chunk
    except OSError:
        return False


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            yield os.path.join(dirpath, fn)


def rel(root, path):
    return os.path.relpath(path, root).replace("\\", "/")


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out, key = {}, None
    for line in text[3:end].splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1).lower()
            out[key] = m.group(2).strip().strip("'\"")
        elif key and line[:1] in (" ", "\t", "-"):
            out[key] += " " + line.strip().lstrip("- ")
    return out


def safe_extract(archive_path, dest):
    unsafe = []
    with zipfile.ZipFile(archive_path) as zf:
        for member in zf.infolist():
            name = member.filename
            if name.startswith("/") or ".." in name.replace("\\", "/").split("/"):
                unsafe.append(name)
                continue
            target = os.path.realpath(os.path.join(dest, name))
            if not target.startswith(os.path.realpath(dest) + os.sep):
                unsafe.append(name)
                continue
            zf.extract(member, dest)
    return unsafe


def add(findings, severity, rule, category, file, line, excerpt, why, raw=""):
    findings.append({"severity": severity, "rule": rule, "category": category,
                     "file": file, "line": line, "excerpt": excerpt, "why": why,
                     "_raw": raw or excerpt})


# ---------------------------------------------------------------- scanning

def scan(root, rules, context_chars=110, depth=0):
    findings, inventory = [], []
    total_bytes = 0
    skill_md = None
    archives = []

    for path in walk(root):
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        total_bytes += size
        r = rel(root, path)
        ext = os.path.splitext(path)[1].lower()
        textual = is_probably_text(path)
        # Windows 는 X_OK 가 의미가 없다 (모든 파일이 실행 가능으로 나온다). 확장자로만 본다.
        if os.name == "nt":
            executable = ext in {".sh", ".bash", ".ps1", ".bat", ".cmd", ".py", ".js", ".cjs", ".mjs", ".rb", ".pl"}
        else:
            executable = os.access(path, os.X_OK) and ext in {".sh", ".bash", ".py", ".ps1", ".js", ".rb", ".pl", ""}
        inventory.append({"path": r, "bytes": size, "text": textual, "executable": bool(executable)})

        if ext in ARCHIVE_EXT and zipfile.is_zipfile(path):
            archives.append((r, path))
            continue
        if not textual:
            if ext in IMAGE_EXT:
                continue
            add(findings, "CRITICAL" if ext in BINARY_EXT else "HIGH", "BINARY_FILE",
                "inventory", r, 0, f"<binary/opaque, {size} bytes>",
                "내용을 읽어 검증할 수 없는 파일. 스킬에 바이너리가 필요한 경우는 거의 없음.")
            continue
        if size > MAX_FILE_BYTES:
            add(findings, "MEDIUM", "HUGE_FILE", "inventory", r, 0, f"<{size} bytes, skipped>",
                "너무 커서 자동 검사를 건너뜀. 직접 확인 필요.")
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            continue

        if os.path.basename(path).lower() == "skill.md" and skill_md is None:
            skill_md = (r, content)
        lines = content.splitlines()

        for rule_id, sev, cat, rx, why in rules:
            seen = set()
            for m in rx.finditer(content):
                ln = content.count("\n", 0, m.start()) + 1
                if ln in seen:
                    continue
                seen.add(ln)
                raw = lines[ln - 1] if ln <= len(lines) else m.group(0)
                add(findings, sev, rule_id, cat, r, ln, raw.strip()[:context_chars], why, raw)

        for i, line in enumerate(lines, 1):
            hidden = [c for c in line if c in ZERO_WIDTH]
            if hidden:
                names = ", ".join(sorted({unicodedata.name(c, hex(ord(c))) for c in hidden}))
                add(findings, "CRITICAL", "HIDDEN_UNICODE", "obfuscation", r, i,
                    f"{len(hidden)}개 [{names}]",
                    "사람 눈에는 안 보이고 모델은 읽는 문자. 지시문을 숨기는 수법.")
            if len(line) > 1200:
                add(findings, "MEDIUM", "LONG_LINE", "obfuscation", r, i, line[:80] + " ...",
                    f"{len(line)}자짜리 단일 행. 인코딩된 페이로드가 숨을 수 있음.")
            if re.search(r"[A-Za-z0-9+/]{200,}={0,2}", line):
                add(findings, "HIGH", "BASE64_BLOB", "obfuscation", r, i, line.strip()[:80] + " ...",
                    "긴 base64 덩어리. 디코딩해서 내용을 확인해야 함.")

        if ext in {".md", ".markdown"}:
            for m in re.finditer(r"<!--(.*?)-->", content, re.DOTALL):
                body = m.group(1).strip()
                if len(body) > 120:
                    ln = content.count("\n", 0, m.start()) + 1
                    add(findings, "HIGH", "HTML_COMMENT", "obfuscation", r, ln,
                        body[:context_chars].replace("\n", " "),
                        "렌더링하면 안 보이지만 모델은 읽는 긴 주석. 인젝션 은닉처.")

    archive_meta = {}
    for arc_rel, arc_path in archives:
        if depth >= MAX_ARCHIVE_DEPTH:
            add(findings, "HIGH", "ARCHIVE_NESTED", "inventory", arc_rel, 0,
                "<중첩 압축>", "압축 안의 압축. 자동 검사를 멈춤 - 직접 풀어서 확인 필요.")
            continue
        tmp = tempfile.mkdtemp(prefix="sponge-security-")
        sub = None
        try:
            for name in safe_extract(arc_path, tmp):
                add(findings, "CRITICAL", "ZIP_SLIP", "obfuscation", arc_rel, 0, name,
                    "압축을 풀 때 대상 디렉터리 밖으로 파일을 쓰려는 경로. 명백한 공격 시도.")
            sub = scan(tmp, rules, context_chars, depth + 1)
        except (zipfile.BadZipFile, OSError) as exc:
            add(findings, "HIGH", "ARCHIVE_UNREADABLE", "inventory", arc_rel, 0,
                str(exc)[:110], "압축 파일을 열 수 없음. 손상되었거나 확장자를 위장한 파일.")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if sub is None:
            continue
        sub_f, sub_i, sub_meta, sub_bytes = sub
        for f in sub_f:
            f["file"] = f"{arc_rel}!/{f['file']}"
            findings.append(f)
        for i in sub_i:
            i["path"] = f"{arc_rel}!/{i['path']}"
            inventory.append(i)
        total_bytes += sub_bytes
        if not archive_meta and sub_meta:
            archive_meta = sub_meta

    meta = {}
    if skill_md:
        r, content = skill_md
        meta = parse_frontmatter(content)
        desc = meta.get("description", "")
        if not desc:
            add(findings, "MEDIUM", "NO_DESCRIPTION", "trigger", r, 1, "(description 없음)",
                "트리거 조건을 알 수 없음.")
        elif BROAD_TRIGGER.search(desc):
            add(findings, "HIGH", "BROAD_TRIGGER", "trigger", r, 1, desc[:200],
                "트리거 범위가 지나치게 넓음. 의도하지 않은 순간에 자동 발동함.")
        if "allowed-tools" in meta:
            at = meta["allowed-tools"]
            sev = "HIGH" if re.search(r"\*|Bash\s*$", at) else "MEDIUM"
            add(findings, sev, "ALLOWED_TOOLS", "config", r, 1, f"allowed-tools: {at[:160]}",
                "스킬이 요구하는 툴 권한. 작업에 필요한 최소 범위인지 확인.")
    elif archive_meta:
        meta = archive_meta
    else:
        add(findings, "MEDIUM", "NO_SKILL_MD", "inventory", ".", 0, "SKILL.md 없음",
            "스킬 디렉터리가 맞는지 확인 필요.")

    return condense(findings), inventory, meta, total_bytes


DENSE_MIN_RULES = 6
NEVER_FOLD = {"HIDDEN_UNICODE", "ZIP_SLIP", "BINARY_FILE", "ARCHIVE_NESTED", "ARCHIVE_UNREADABLE", "HUGE_FILE"}


def fold_dense(findings):
    """한 파일에서 서로 다른 규칙이 6종 이상 걸리면 그 파일은 거의 항상 규칙 카탈로그·보안 문서·스캐너 코드다
    (이 스킬 자신이 그렇다). 페이로드는 보통 한두 규칙만 건드린다. 그런 파일은 규칙별 수십 건 대신
    HIGH 하나로 접어 "이 파일을 통째로 읽어라"라고만 말한다. 접혀도 목록에 남고 판정에 HIGH 로 들어간다 —
    숨기는 게 아니라 소음을 줄이는 것이다. 은닉·압축 계열은 내용과 무관하게 절대 접지 않는다."""
    by_file = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)
    out = []
    for file, items in by_file.items():
        foldable = [i for i in items if i["rule"] not in NEVER_FOLD]
        rules = {i["rule"] for i in foldable}
        if len(rules) >= DENSE_MIN_RULES:
            worst = max(foldable, key=lambda i: RANK[i["severity"]])
            out.append({"severity": "HIGH", "rule": "PATTERN_DENSE", "category": "meta", "file": file,
                        "line": worst["line"], "count": len(foldable),
                        "excerpt": f"규칙 {len(rules)}종 {len(foldable)}건이 한 파일에 — 보안 문서·규칙 카탈로그·스캐너 코드로 보임 "
                                   f"(가장 센 것: {worst['rule']} {worst['file']}:{worst['line']})",
                        "why": "패턴이 이렇게 몰린 파일은 대개 규칙을 *설명*하는 파일이다. 그래도 설명이 맞는지, 그 사이에 진짜 지시가 끼어 있지 않은지 이 파일을 통째로 읽는다.",
                        "_raw": file, "folded_rules": sorted(rules)})
            out.extend(i for i in items if i["rule"] in NEVER_FOLD)
        else:
            out.extend(items)
    return out


def condense(findings):
    findings = fold_dense(findings)
    domain_rx = re.compile(r"https?://([a-z0-9.-]+)", re.IGNORECASE)
    groups = {}
    for f in findings:
        if f["rule"] == "NET_URL":
            m = domain_rx.search(f["excerpt"])
            key = ("NET_URL", m.group(1).lower() if m else f["file"])
        else:
            key = (f["rule"], f["file"])
        groups.setdefault(key, []).append(f)
    out = []
    for key, items in groups.items():
        head = dict(items[0])
        if key[0] == "NET_URL":
            files = sorted({i["file"] for i in items})
            head["excerpt"] = f"{key[1]} - {len(items)}회 참조, {len(files)}개 파일"
            head["why"] = "이 스킬이 통신하려는 외부 도메인. 무엇을 보내는지 확인 필요."
        elif len(items) > 1:
            head["excerpt"] = f"{head['excerpt']}   (같은 파일에 {len(items) - 1}건 더)"
        head["count"] = len(items)
        out.append(head)
    out.sort(key=lambda f: (-RANK[f["severity"]], f["file"], f["line"]))
    return out


def verdict(findings):
    counts = {s: 0 for s in common.SEVERITIES}
    for f in findings:
        counts[f["severity"]] += 1
    if counts["CRITICAL"] or counts["HIGH"] >= 3:
        return "BLOCK", counts
    if counts["HIGH"] or counts["MEDIUM"] >= 5:
        return "REVIEW", counts
    return "LIKELY-OK", counts


VERDICT_KO = {"BLOCK": "설치 비권장 후보", "REVIEW": "조건부 — 본문 정독 필요", "LIKELY-OK": "설치 권장 후보"}


# ---------------------------------------------------------------- fetch

def fetch_repo(url):
    """Clone into the sponge quarantine (never ~/.claude/skills). Read-only afterwards."""
    common.ensure_dirs()
    name = re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1]) or "repo"
    dest = os.path.join(common.QUARANTINE, name)
    if os.path.exists(dest):
        shutil.rmtree(dest, ignore_errors=True)
    out = common.git(["clone", "--depth", "1", "--no-checkout", url, dest])
    if out is None:
        # fallback: plain clone (some hosts dislike --no-checkout)
        shutil.rmtree(dest, ignore_errors=True)
        out = common.git(["clone", "--depth", "1", url, dest])
        if out is None:
            raise RuntimeError(f"clone 실패: {url}")
    else:
        # checkout files but never run anything (no hooks: core.hooksPath to empty dir)
        if common.git(["-c", "core.hooksPath=/dev/null", "checkout", "HEAD", "--", "."], cwd=dest) is None:
            common.git(["checkout", "HEAD", "--", "."], cwd=dest)
    return dest


# ---------------------------------------------------------------- report

def render(root, findings, allowed, inventory, meta, total_bytes, target_label):
    v, counts = verdict(findings)
    out = [f"# 스폰지보안 · 스킬 심사: {os.path.basename(os.path.abspath(root))}", ""]
    out.append(f"- 대상: `{target_label}`")
    out.append(f"- 심사 시각: {common.now()}")
    out.append(f"- 파일 {len(inventory)}개 / {total_bytes:,} bytes")
    if meta.get("name"):
        out.append(f"- name: `{meta['name']}`")
    if meta.get("description"):
        out.append(f"- description: {meta['description'][:300]}")
    out.append(f"- 자동 판정: **{v}** ({VERDICT_KO[v]}) — CRITICAL {counts['CRITICAL']} / HIGH {counts['HIGH']} / "
               f"MEDIUM {counts['MEDIUM']} / LOW {counts['LOW']}")
    if allowed:
        out.append(f"- 예외 목록으로 제외: {len(allowed)}건")
    out.append("")
    out.append("> 자동 판정은 분류 힌트다. 설치 여부는 SKILL.md 본문을 읽고 사람이 정한다.")
    out.append("")

    out.append("## 스폰지클럽 규범 대조")
    out.append("")
    out.append("| 규범 | 결과 | 근거 |")
    out.append("|---|---|---|")
    by_rule = {}
    folded = {}
    for f in findings:
        by_rule.setdefault(f["rule"], []).append(f)
        for r in f.get("folded_rules", []):
            folded.setdefault(r, []).append(f["file"])
    for norm, rules in SPONGE_NORMS:
        hits = [f for r in rules for f in by_rule.get(r, [])]
        infolded = sorted({fn for r in rules for fn in folded.get(r, [])})
        if hits:
            locs = ", ".join(f"`{h['file']}:{h['line']}`" for h in hits[:3])
            out.append(f"| {norm} | ⚠ 확인 필요 ({len(hits)}건) | {locs} |")
        elif infolded:
            out.append(f"| {norm} | 📄 접힌 파일에서 언급 | {', '.join('`' + x + '`' for x in infolded[:3])} — 통째로 읽기 |")
        else:
            out.append(f"| {norm} | 통과 | 패턴 없음 |")
    dense = [f for f in findings if f["rule"] == "PATTERN_DENSE"]
    if dense:
        out.append("")
        out.append(f"> 규칙이 6종 이상 몰린 파일 {len(dense)}개는 규칙별로 나열하지 않고 PATTERN_DENSE 하나로 접었다. "
                   "보안 문서·스캐너 코드가 대개 이렇다. 접힌 파일은 통째로 읽어 설명인지 지시인지 가른다.")
    out.append("")

    notable = [i for i in inventory if i["executable"] or not i["text"]]
    if notable:
        out.append("## 실행 가능 / 비텍스트 파일")
        for i in notable:
            tag = "스크립트" if i["executable"] else "비텍스트"
            out.append(f"- `{i['path']}` ({i['bytes']:,} bytes, {tag})")
        out.append("")

    out.append("## 발견 사항")
    if not findings:
        out.append("")
        out.append("패턴 기준 특이사항 없음. 패턴은 알려진 수법만 잡으므로 SKILL.md 본문은 여전히 읽어야 한다.")
    current = None
    for f in findings:
        if f["severity"] != current:
            current = f["severity"]
            out.append("")
            out.append(f"### {current}")
        loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
        out.append(f"- **[{f['rule']}]** `{loc}`")
        out.append(f"  - 발췌: `{f['excerpt']}`")
        out.append(f"  - 의미: {f['why']}")
    if allowed:
        out.append("")
        out.append("## 예외 목록으로 제외된 항목")
        for f in allowed:
            out.append(f"- [{f['rule']}] `{f['file']}:{f['line']}` — 사유: {f.get('allow_reason') or '(없음)'}")
    out.append("")
    out.append("## 다음 단계")
    out.append("1. SKILL.md 전문을 읽는다. 설명과 지시가 일치하는지, 참조 파일·외부 URL 로 한 단계 숨겼는지.")
    out.append("2. 스크립트·비텍스트 파일을 본다. 읽어서 검증할 수 없는 파일은 그 자체가 거절 사유.")
    out.append("3. 출처를 본다 (`git log --oneline -20 --stat`). 신뢰는 커밋 단위다.")
    out.append("4. 설치는 사용자가 리포트를 납득했을 때만. `~/.claude/skills/` 로 복사하는 것은 사용자가 직접 한다.")
    return "\n".join(out), v, counts


def run(target, save=True, context=110):
    cfg = common.load_config()
    label = target
    root = target
    pre = []
    if re.match(r"^(https?://|git@)", target):
        root = fetch_repo(target)
    elif os.path.isfile(target) and os.path.splitext(target)[1].lower() in ARCHIVE_EXT:
        tmp = tempfile.mkdtemp(prefix="sponge-security-")
        try:
            unsafe = safe_extract(target, tmp)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError(f"압축 파일을 열 수 없음: {exc}")
        root = tmp
        pre = [{"severity": "CRITICAL", "rule": "ZIP_SLIP", "category": "obfuscation", "file": os.path.basename(target),
                "line": 0, "excerpt": n, "why": "압축을 풀 때 대상 디렉터리 밖으로 쓰려는 경로.", "_raw": n} for n in unsafe]
    elif not os.path.isdir(target):
        raise RuntimeError(f"디렉터리가 아닙니다: {target}")

    rules = RULES + common.custom_rules(cfg, "skill")
    findings, inventory, meta, total = scan(root, rules, context)
    findings = pre + findings
    findings, allowed = common.apply_allowlist(findings, cfg)
    text, v, counts = render(root, findings, allowed, inventory, meta, total, label)
    common.strip_private(findings)
    common.strip_private(allowed)
    data = {"kind": "skill", "target": label, "root": os.path.abspath(root), "verdict": v,
            "counts": counts, "summary": {"verdict": v, **counts, "allowed": len(allowed)},
            "meta": meta, "findings": findings, "allowed": allowed, "inventory": inventory, "at": common.now()}
    rid = None
    if save:
        rid = common.save_report("skill", meta.get("name") or os.path.basename(os.path.abspath(root)), text, data)
        common.remember_target(cfg, label)
        common.save_config(cfg)
    if root != target and root.startswith(tempfile.gettempdir()):
        shutil.rmtree(root, ignore_errors=True)
    data["report_id"] = rid
    data["markdown"] = text
    return data


def main():
    ap = argparse.ArgumentParser(description="스폰지보안 — 외부 스킬 정적 심사 (실행 없이 읽기만)")
    ap.add_argument("target", help="스킬 디렉터리, .skill/.zip 파일, 또는 git URL")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    ap.add_argument("--no-save", action="store_true", help="리포트를 저장하지 않음")
    ap.add_argument("--context", type=int, default=110)
    args = ap.parse_args()
    try:
        data = run(args.target, save=not args.no_save, context=args.context)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        md = data.pop("markdown")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data["markdown"])
        if data.get("report_id"):
            print(f"\n(리포트 저장: {os.path.join(common.REPORTS, data['report_id'] + '.md')})")
    return 1 if data["verdict"] == "BLOCK" else 0


if __name__ == "__main__":
    sys.exit(main())
