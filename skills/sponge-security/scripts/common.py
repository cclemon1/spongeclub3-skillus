#!/usr/bin/env python3
"""Shared plumbing for sponge-security: config, allowlist, report store.

Everything lives under ~/.claude/sponge-security/ so the skill directory
itself stays read-only and shareable. Nothing here talks to the network.
"""

import datetime as _dt
import fnmatch
import json
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, ".claude", "sponge-security")
CONFIG = os.path.join(BASE, "config.json")
REPORTS = os.path.join(BASE, "reports")
HISTORY = os.path.join(BASE, "history.json")
QUARANTINE = os.path.join(BASE, "quarantine")

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
RANK = {s: i for i, s in enumerate(reversed(SEVERITIES))}

DEFAULT_CONFIG = {
    "version": 1,
    # 내 정보. 값이 파일에 그대로 있으면 잡는다. kind: email|phone|name|username|domain|other
    "identity": [],
    # 예외. rule 이 같고(또는 "*"), 파일이 glob 에 맞고, pattern 이 발견 텍스트에 들어 있으면 제외.
    "allow": [],
    # 사용자 규칙. scope: skill|publish|both
    "rules": [],
    # 추가로 건너뛸 경로 glob
    "ignore_paths": [],
    # 이메일 도메인 중 공개돼도 되는 것 (예: 회사 공식 도메인)
    "public_email_domains": [],
    "recent_targets": [],
}


def ensure_dirs():
    for d in (BASE, REPORTS, QUARANTINE):
        os.makedirs(d, exist_ok=True)


def now():
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def stamp():
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def load_config():
    ensure_dirs()
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for k, v in data.items():
                    cfg[k] = v
        except (OSError, ValueError):
            pass
    return cfg


def save_config(cfg):
    ensure_dirs()
    tmp = CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG)


def hash_value(v):
    import hashlib
    return hashlib.sha256(v.strip().encode("utf-8")).hexdigest()


def seal_secrets(cfg):
    """kind=secret 항목은 값을 저장하지 않는다. 해시만 남기고 value 를 비운다."""
    for e in cfg.get("identity", []):
        if not isinstance(e, dict) or e.get("kind") != "secret":
            continue
        v = str(e.get("value", "")).strip()
        if v:
            e["hash"] = hash_value(v)
            e["length"] = len(v)
            e["value"] = ""
    return cfg


def validate_config(cfg):
    """Return a list of human-readable problems. Empty list means OK."""
    problems = []
    if not isinstance(cfg, dict):
        return ["설정은 객체여야 합니다"]
    for i, e in enumerate(cfg.get("identity", [])):
        if not isinstance(e, dict):
            problems.append(f"identity[{i}]: 객체가 아닙니다")
            continue
        if e.get("kind") == "secret":
            if not e.get("hash") and not str(e.get("value", "")).strip():
                problems.append(f"identity[{i}]: 시크릿 값이 비어 있습니다")
            continue
        if not str(e.get("value", "")).strip():
            problems.append(f"identity[{i}]: value 가 비어 있습니다")
    for i, e in enumerate(cfg.get("allow", [])):
        if not isinstance(e, dict) or not str(e.get("pattern", "")).strip():
            problems.append(f"allow[{i}]: pattern 이 비어 있습니다")
    ids = set()
    for i, r in enumerate(cfg.get("rules", [])):
        if not isinstance(r, dict):
            problems.append(f"rules[{i}]: 객체가 아닙니다")
            continue
        rid = str(r.get("id", "")).strip()
        if not rid:
            problems.append(f"rules[{i}]: id 가 없습니다")
        elif rid in ids:
            problems.append(f"rules[{i}]: id 중복 ({rid})")
        ids.add(rid)
        if r.get("severity", "MEDIUM") not in SEVERITIES:
            problems.append(f"rules[{i}]: severity 는 {'/'.join(SEVERITIES)} 중 하나")
        try:
            re.compile(r.get("regex", ""), re.IGNORECASE)
        except re.error as exc:
            problems.append(f"rules[{i}]: 정규식 오류 - {exc}")
        if r.get("scope", "both") not in ("skill", "publish", "both"):
            problems.append(f"rules[{i}]: scope 는 skill/publish/both")
    return problems


def custom_rules(cfg, scope):
    """Compiled user rules for a scope, as (id, severity, category, regex, why)."""
    out = []
    for r in cfg.get("rules", []):
        if r.get("scope", "both") not in ("both", scope):
            continue
        if not r.get("enabled", True):
            continue
        try:
            rx = re.compile(r["regex"], re.IGNORECASE)
        except (re.error, KeyError):
            continue
        out.append((str(r.get("id", "CUSTOM")).upper(), r.get("severity", "MEDIUM"),
                    "custom", rx, r.get("why", "사용자 정의 규칙")))
    return out


def git(args, cwd=None):
    try:
        res = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout


def seed_identity_candidates():
    """Values a person usually forgets are 'theirs': git identity, OS login."""
    cands = []
    name = (git(["config", "--global", "user.name"]) or "").strip()
    email = (git(["config", "--global", "user.email"]) or "").strip()
    if email and "noreply" not in email.lower():  # noreply 주소는 공개용이라 내 정보가 아니다
        cands.append({"value": email, "label": "git 이메일", "kind": "email"})
    if name and len(name) >= 2:
        cands.append({"value": name, "label": "git 이름", "kind": "name"})
    try:
        login = os.getlogin()
    except OSError:
        login = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if login and len(login) >= 3 and login.lower() not in {"user", "admin", "root"}:
        cands.append({"value": login, "label": "OS 로그인 이름", "kind": "username"})
    return cands


# ------------------------------------------------------------------ allowlist

def _allow_matches(entry, finding):
    rule = str(entry.get("rule", "*")).upper()
    if rule not in ("*", "") and rule != finding.get("rule"):
        return False
    fpat = entry.get("file") or ""
    if fpat and not fnmatch.fnmatch(finding.get("file", ""), fpat):
        return False
    pat = str(entry.get("pattern", ""))
    if not pat:
        return False
    hay = " ".join([finding.get("_raw", ""), finding.get("excerpt", ""), finding.get("file", "")])
    return pat.lower() in hay.lower()


def apply_allowlist(findings, cfg):
    """Split findings into (kept, allowed). Allowed ones keep the reason for the report."""
    kept, allowed = [], []
    entries = cfg.get("allow", [])
    for f in findings:
        hit = next((e for e in entries if _allow_matches(e, f)), None)
        if hit:
            g = dict(f)
            g["allow_reason"] = hit.get("reason", "")
            allowed.append(g)
        else:
            kept.append(f)
    return kept, allowed


def strip_private(findings):
    """Drop raw matches before anything is written to disk or printed."""
    for f in findings:
        f.pop("_raw", None)
    return findings


# ------------------------------------------------------------------ reports

def _slug(s):
    s = re.sub(r"[^A-Za-z0-9가-힣._-]+", "-", s).strip("-")
    return s[:48] or "target"


def save_report(kind, target_name, markdown, data):
    """Persist a report and index it. Returns the report id."""
    ensure_dirs()
    rid = f"{kind}-{_slug(target_name)}-{stamp()}"
    md_path = os.path.join(REPORTS, rid + ".md")
    js_path = os.path.join(REPORTS, rid + ".json")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    with open(js_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    hist = load_history()
    hist.insert(0, {
        "id": rid, "kind": kind, "target": data.get("target", target_name),
        "verdict": data.get("verdict"), "summary": data.get("summary", {}),
        "at": now(), "md": md_path, "json": js_path,
    })
    with open(HISTORY, "w", encoding="utf-8") as fh:
        json.dump(hist[:300], fh, ensure_ascii=False, indent=2)
    return rid


def load_history():
    if not os.path.exists(HISTORY):
        return []
    try:
        with open(HISTORY, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def remember_target(cfg, target):
    lst = [t for t in cfg.get("recent_targets", []) if t != target]
    lst.insert(0, target)
    cfg["recent_targets"] = lst[:10]


def redact(s):
    s = (s or "").strip()
    if len(s) <= 8:
        return s[:2] + "…"
    return f"{s[:4]}…{s[-3:]} ({len(s)}자)"
