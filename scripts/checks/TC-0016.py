"""TC-0016 auto-check：方案结构完整性（五章节齐全）。

退出码: 0=pass 1=fail 2=unable
"""

import sys
from pathlib import Path

REQUIRED = ["核心循环", "引擎推荐", "体量评估", "风险清单", "里程碑"]


def main() -> int:
    path = Path(sys.argv[1]) / "recommendation.md"
    if not path.exists():
        print("证据缺失: recommendation.md")
        return 2
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [h for h in REQUIRED if h not in text]
    if missing:
        print(f"fail: 缺少章节 {missing}")
        return 1
    print("pass: 五章节齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
