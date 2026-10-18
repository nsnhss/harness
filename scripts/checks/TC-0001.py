"""TC-0001 auto-check：验证 press_jump → player_airborne ≤ 100ms。

用法: python TC-0001.py <evidence_dir>
退出码: 0=pass 1=fail 2=unable（证据缺失/格式错误）
"""

import json
import sys
from pathlib import Path

THRESHOLD_MS = 100


def main() -> int:
    evidence_dir = Path(sys.argv[1])
    log_path = evidence_dir / "input_log.json"
    if not log_path.exists():
        print("证据缺失: input_log.json")
        return 2
    try:
        events = json.loads(log_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"证据格式错误: {e}")
        return 2

    presses = [e for e in events if e.get("event") == "press_jump"]
    airbornes = [e for e in events if e.get("event") == "player_airborne"]
    if not presses or not airbornes:
        print("证据不足: 缺少 press_jump 或 player_airborne 事件")
        return 2

    for press in presses:
        later = [a for a in airbornes if a["t_ms"] >= press["t_ms"]]
        if not later:
            continue
        delta = min(later, key=lambda a: a["t_ms"])["t_ms"] - press["t_ms"]
        if delta <= THRESHOLD_MS:
            print(f"pass: 离地延迟 {delta}ms ≤ {THRESHOLD_MS}ms")
            return 0
        print(f"fail: 离地延迟 {delta}ms > {THRESHOLD_MS}ms")
        return 1
    print("fail: 存在按下后未离地的记录")
    return 1


if __name__ == "__main__":
    sys.exit(main())
