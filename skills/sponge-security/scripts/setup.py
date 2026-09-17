#!/usr/bin/env python3
"""스폰지보안 초기 설정.

  python setup.py                  설정 폴더 만들고 상태 출력
  python setup.py --seed           git 이름·이메일, OS 계정을 '내 정보' 후보로 넣는다 (중복 제외)
  python setup.py --install-hook   ~/.claude/settings.json 에 push/배포 게이트 훅을 추가 (변경 내용을 먼저 보여 주고 --yes 일 때만 쓴다)
  python setup.py --remove-hook    훅 제거
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SETTINGS = os.path.join(common.HOME, ".claude", "settings.json")
GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "push_gate.py").replace("\\", "/")
# Mac 은 `python` 이 없을 수 있다. 지금 setup 을 돌린 인터프리터 경로를 그대로 쓴다.
PY = sys.executable.replace("\\", "/")
HOOK = {"type": "command", "command": f'"{PY}" "{GATE}"', "timeout": 90, "statusMessage": "스폰지보안: push 전 점검 중..."}


def load_settings():
    if not os.path.exists(SETTINGS):
        return {}
    with open(SETTINGS, "r", encoding="utf-8") as fh:
        return json.load(fh)


def has_hook(settings):
    for grp in settings.get("hooks", {}).get("PreToolUse", []):
        for h in grp.get("hooks", []):
            if "push_gate.py" in h.get("command", ""):
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--install-hook", action="store_true")
    ap.add_argument("--remove-hook", action="store_true")
    ap.add_argument("--yes", action="store_true", help="설정 파일을 실제로 쓴다")
    args = ap.parse_args()

    cfg = common.load_config()
    common.save_config(cfg)
    print(f"설정: {common.CONFIG}")
    print(f"리포트: {common.REPORTS}")
    print(f"내 정보 {len(cfg['identity'])}개 · 예외 {len(cfg['allow'])}개 · 사용자 규칙 {len(cfg['rules'])}개")

    if args.seed:
        have = {str(e.get("value", "")).lower() for e in cfg["identity"]}
        added = 0
        for c in common.seed_identity_candidates():
            if c["value"].lower() not in have:
                cfg["identity"].append(c)
                added += 1
        common.save_config(cfg)
        print(f"내 정보 후보 {added}개 추가 (편집기에서 확인·수정)")

    settings = load_settings()
    if args.install_hook or args.remove_hook:
        hooks = settings.setdefault("hooks", {})
        pre = hooks.setdefault("PreToolUse", [])
        if args.install_hook:
            if has_hook(settings):
                print("훅이 이미 있습니다.")
                return 0
            new = {"matcher": "Bash", "hooks": [HOOK]}
            print("settings.json 의 hooks.PreToolUse 에 추가할 항목:")
            print(json.dumps(new, ensure_ascii=False, indent=2))
            if not args.yes:
                print("\n(실제로 쓰려면 --yes 를 붙이세요. 사용자에게 먼저 보여 주고 승인받은 뒤에.)")
                return 0
            pre.append(new)
        else:
            for grp in pre:
                grp["hooks"] = [h for h in grp.get("hooks", []) if "push_gate.py" not in h.get("command", "")]
            hooks["PreToolUse"] = [g for g in pre if g.get("hooks")]
            if not args.yes:
                print("훅을 제거하려면 --yes 를 붙이세요.")
                return 0
        tmp = SETTINGS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS)
        print("settings.json 갱신 완료. 새 세션부터 적용됩니다.")
    else:
        print("push/배포 게이트 훅: " + ("설치됨" if has_hook(settings) else "없음 (setup.py --install-hook)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
