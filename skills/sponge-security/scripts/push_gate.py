#!/usr/bin/env python3
"""PreToolUse(Bash) 훅 — `git push` · `vercel` 배포 직전에 공개 전 점검을 돌린다.

"지금 당장" 항목이 하나라도 있으면 명령을 막고 이유를 보여 준다. 훅은 조용히
통과시키는 것이 기본이고, 막을 때만 말한다 — 매번 시끄러운 게이트는 일주일
안에 꺼진다.

우회: 명령에 --no-verify 가 있으면 검사하지 않는다. 오탐일 때 사용자가 보고
승인한 뒤에만 붙인다. (secret_scan.py 의 커밋 게이트와 같은 규칙)

설치: python setup.py --install-hook  (사용자 확인 뒤에)
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PUSH = re.compile(r"(^|[;&|]|\s)git(\s+-[^\s]+(\s+[^\s-][^\s]*)?)*\s+push\b")
DEPLOY = re.compile(r"(^|[;&|]|\s)(vercel|npx\s+vercel)(\s+deploy)?(\s|$)(?![^\n]*\b(dev|env|login|link|logs|ls|inspect|whoami|pull)\b)")


def main():
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        payload = {}
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if not (PUSH.search(cmd) or DEPLOY.search(cmd)) or "--no-verify" in cmd or "--dry-run" in cmd or "--help" in cmd:
        print(json.dumps({"suppressOutput": True}))
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    try:
        import publish_check
        data = publish_check.run(cwd, mode="push", save=True)
    except Exception as exc:  # 인프라 문제로는 막지 않는다
        print(json.dumps({"suppressOutput": True, "systemMessage": f"스폰지보안: 점검 실패로 통과시킴 ({exc})"}, ensure_ascii=False))
        return 0

    now = [f for f in data["findings"] if f["priority"] == "now"]
    if not now:
        week = data["summary"]["week"]
        msg = f"스폰지보안: push 전 점검 통과 · {data['summary'].get('calm', '')}" + (f" (이번 주 항목 {week}건은 리포트 참고)" if week else "")
        print(json.dumps({"suppressOutput": True, "systemMessage": msg}, ensure_ascii=False))
        return 0

    lines = []
    for f in now[:12]:
        loc = f"{f['file']}:{f['line']}" if f.get("line") else f["file"]
        lines.append(f"  - [{f['rule']}] {loc} — {f['excerpt']}")
    report = os.path.join(os.path.expanduser("~"), ".claude", "sponge-security", "reports", f"{data['report_id']}.md")
    reason = (
        "공개 전 점검에서 '지금 당장' 항목이 나왔습니다. push/배포하면 밖으로 나갑니다.\n"
        + "\n".join(lines) + ("\n  ... 외 더 있음" if len(now) > 12 else "")
        + f"\n\n전체 리포트: {report}\n"
        "실제 유출이면: 파일에서 값을 빼고, 이미 커밋된 키는 재발급하세요.\n"
        "오탐이면: 사용자에게 위 목록을 그대로 보여주고, 사용자가 승인하면 편집기에서 예외로 등록하거나 "
        "--no-verify 를 붙여 다시 실행하세요. 사용자 확인 없이 --no-verify 를 붙이지 마세요."
    )
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                               "permissionDecisionReason": reason},
        "systemMessage": f"스폰지보안: 지금 당장 {len(now)}건 — push/배포 보류",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
