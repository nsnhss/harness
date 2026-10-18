"""TC-0015 auto-check：方案明确给出主引擎名称。

扫描 recommendation.md 中的已知引擎名，至少出现一次即 pass。
退出码: 0=pass 1=fail 2=unable
"""

import sys
from pathlib import Path

ENGINES = ["Unity", "Unreal", "Godot", "Ren'Py", "RPG Maker", "GameMaker",
           "Cocos", "Phaser", "Defold", "Bevy", "LayaAir"]


def main() -> int:
    path = Path(sys.argv[1]) / "recommendation.md"
    if not path.exists():
        print("证据缺失: recommendation.md")
        return 2
    text = path.read_text(encoding="utf-8", errors="replace")
    found = [e for e in ENGINES if e.lower() in text.lower()]
    if found:
        print(f"pass: 检测到引擎名 {found}")
        return 0
    print("fail: 方案未出现任何已知引擎名称")
    return 1


if __name__ == "__main__":
    sys.exit(main())
