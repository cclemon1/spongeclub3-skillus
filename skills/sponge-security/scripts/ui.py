#!/usr/bin/env python3
"""스폰지클럽3기 보안편집기 — 로컬 전용 웹 UI.

  python ui.py [--project <경로>] [--port 8765] [--no-browser]

127.0.0.1 에만 묶이고, 외부 리소스를 하나도 불러오지 않는다 (보안 도구가 CDN 을
부르면 그게 공격면이다). 페이지에 심은 토큰이 없으면 API 는 거절한다 — 같은
PC 의 다른 사이트가 이 서버를 몰래 부르지 못하게.

할 수 있는 것:
  · 내 정보 / 예외 / 사용자 규칙 / 공개 도메인 편집   → ~/.claude/sponge-security/config.json
  · 공개 전 점검 · 스킬 심사 실행, 결과에서 바로 예외 등록
  · 지난 리포트 열람
"""

import argparse
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import publish_check  # noqa: E402
import skill_check  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(os.path.dirname(HERE), "assets", "editor.html")
TOKEN = secrets.token_urlsafe(18)
LOCK = threading.Lock()
PROJECT = os.getcwd()


class Handler(BaseHTTPRequestHandler):
    server_version = "sponge-security/1"

    def log_message(self, fmt, *args):  # quiet
        pass

    # ---- helpers
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                         "img-src data:; connect-src 'self'; form-action 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def _local_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _auth_ok(self):
        return secrets.compare_digest(self.headers.get("X-Sponge-Token") or "", TOKEN)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 5_000_000:
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except ValueError:
            return None

    # ---- routes
    def do_GET(self):
        if not self._local_ok():
            return self._send(403, {"error": "local only"})
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            if q.get("t", [""])[0] != TOKEN:
                return self._send(403, ("<h1>403</h1><p>터미널에 출력된 주소(토큰 포함)로 여세요.</p>"
                                        "<p>토큰을 붙였는데도 이 화면이면, 다른 편집기 서버가 이 포트에 먼저 떠 있는 것입니다. "
                                        "터미널에 찍힌 포트 번호를 다시 확인하세요.</p>").encode("utf-8"),
                                  "text/html; charset=utf-8")
            with open(PAGE, "r", encoding="utf-8") as fh:
                html = fh.read()
            html = html.replace("__TOKEN__", TOKEN).replace("__PROJECT__", json.dumps(PROJECT))
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if not self._auth_ok():
            return self._send(403, {"error": "token"})
        if u.path == "/api/config":
            return self._send(200, common.load_config())
        if u.path == "/api/history":
            return self._send(200, common.load_history())
        if u.path == "/api/report":
            rid = q.get("id", [""])[0]
            if not rid or "/" in rid or "\\" in rid or ".." in rid:
                return self._send(400, {"error": "id"})
            md = os.path.join(common.REPORTS, rid + ".md")
            js = os.path.join(common.REPORTS, rid + ".json")
            if not os.path.exists(md):
                return self._send(404, {"error": "없음"})
            with open(md, "r", encoding="utf-8") as fh:
                text = fh.read()
            data = {}
            if os.path.exists(js):
                with open(js, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            return self._send(200, {"id": rid, "markdown": text, "data": data})
        if u.path == "/api/seed":
            return self._send(200, common.seed_identity_candidates())
        if u.path == "/api/rules":
            return self._send(200, {
                "skill": [{"id": r[0], "severity": r[1], "category": r[2], "why": r[4]} for r in skill_check.RULES],
                "publish": [{"id": r[0], "severity": r[1], "why": r[4]} for r in publish_check.CODE_RULES]
                + [{"id": r[0], "severity": r[1], "why": r[4]} for r in publish_check.FILE_RULES]
                + [{"id": k, "severity": "-", "why": v} for k, v in publish_check.FIX.items()
                   if k not in {r[0] for r in publish_check.CODE_RULES + publish_check.FILE_RULES}],
            })
        return self._send(404, {"error": "not found"})

    def do_PUT(self):
        if not self._local_ok() or not self._auth_ok():
            return self._send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        body = self._body()
        if body is None:
            return self._send(400, {"error": "JSON 이 아닙니다"})
        if u.path == "/api/config":
            cfg = common.load_config()
            for k in ("identity", "allow", "rules", "ignore_paths", "public_email_domains"):
                if k in body:
                    cfg[k] = body[k]
            common.seal_secrets(cfg)  # 시크릿 값은 해시만 남긴다
            problems = common.validate_config(cfg)
            if problems:
                return self._send(400, {"error": "설정 오류", "problems": problems})
            common.save_config(cfg)
            return self._send(200, {"ok": True, "config": cfg})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._local_ok() or not self._auth_ok():
            return self._send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        body = self._body()
        if body is None:
            return self._send(400, {"error": "JSON 이 아닙니다"})
        if u.path == "/api/scan":
            kind = body.get("kind", "publish")
            target = (body.get("target") or PROJECT).strip()
            if not LOCK.acquire(timeout=1):
                return self._send(409, {"error": "이미 점검이 돌고 있습니다"})
            try:
                if kind == "skill":
                    data = skill_check.run(target, save=True)
                else:
                    data = publish_check.run(target, body.get("mode", "tree"), bool(body.get("history")),
                                             bool(body.get("build")), save=True)
            except RuntimeError as exc:
                return self._send(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                return self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
            finally:
                LOCK.release()
            return self._send(200, data)
        if u.path == "/api/allow":
            cfg = common.load_config()
            entry = {"rule": str(body.get("rule", "*")).upper() or "*", "pattern": str(body.get("pattern", "")).strip(),
                     "file": str(body.get("file", "")).strip(), "reason": str(body.get("reason", "")).strip(),
                     "added": common.now()}
            if not entry["pattern"]:
                return self._send(400, {"error": "pattern 이 비어 있습니다"})
            cfg["allow"].append(entry)
            common.save_config(cfg)
            return self._send(200, {"ok": True, "allow": cfg["allow"]})
        if u.path == "/api/test-rule":
            import re
            try:
                rx = re.compile(body.get("regex", ""), re.IGNORECASE)
            except re.error as exc:
                return self._send(400, {"error": f"정규식 오류: {exc}"})
            sample = body.get("sample", "")
            hits = [{"line": i, "text": ln, "match": m.group(0)}
                    for i, ln in enumerate(sample.splitlines(), 1) for m in [rx.search(ln)] if m]
            return self._send(200, {"hits": hits})
        return self._send(404, {"error": "not found"})


class Server(ThreadingHTTPServer):
    # Windows 에서 allow_reuse_address=True(기본값) 면 이미 쓰는 포트에 또 묶인다. 그러면 두 번째
    # 편집기의 주소로 열어도 요청이 첫 번째 서버로 가서 토큰이 안 맞아 403 이 난다. 끈다.
    allow_reuse_address = False


def port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    global PROJECT
    ap = argparse.ArgumentParser(description="스폰지보안 편집기 (로컬 전용)")
    ap.add_argument("--project", default=os.getcwd(), help="기본 점검 대상 폴더")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    PROJECT = os.path.abspath(args.project)
    common.ensure_dirs()
    common.save_config(common.load_config())

    port = args.port
    httpd = None
    for p in range(port, port + 20):
        if port_in_use(p):  # 이미 다른 편집기가 쓰는 포트는 건너뛴다
            continue
        try:
            httpd = Server(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue
    if httpd is None:
        print("포트를 열 수 없습니다", file=sys.stderr)
        return 2
    url = f"http://127.0.0.1:{port}/?t={TOKEN}"
    print("스폰지클럽3기 보안편집기")
    print(f"  주소   : {url}")
    print(f"  프로젝트: {PROJECT}")
    print(f"  설정   : {common.CONFIG}")
    print("  종료   : Ctrl+C")
    sys.stdout.flush()
    if not args.no_browser:
        opened = False
        try:
            opened = webbrowser.open(url)
        except Exception:  # noqa: BLE001
            opened = False
        if not opened and os.name == "nt":  # Windows 에서 webbrowser 가 조용히 실패하는 경우가 있다
            try:
                os.startfile(url)  # noqa: S606 - 로컬 주소를 기본 브라우저로
                opened = True
            except OSError:
                pass
        if not opened:
            print("  (브라우저가 자동으로 열리지 않았습니다. 위 주소를 직접 붙여 넣으세요.)")
        sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
