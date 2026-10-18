"""A 类候选用例播种：评估 LLM 输出质量（顾问层方案/提取结果）。

与首批 B 类（游戏运行时）不同，A 类现在就能测：证据 = LLM 输出原文 + trace。
auto 项配套检测脚本 scripts/checks/TC-0015.py、TC-0016.py。
"""

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from harness_core.evaluation.generate import next_check_ids

ROOT = Path(__file__).resolve().parents[1]

# auto 项放最前，保证 ID 与检测脚本对应（TC-0015、TC-0016）
ITEMS = [
    ("方案明确性", "方案明确给出主引擎名称", "auto", ["recommendation.md"]),
    ("结构完整性", "方案包含核心循环/引擎推荐/体量评估/风险清单/里程碑五个章节",
     "auto", ["recommendation.md"]),
    ("体量约束一致", "team_size=1 时方案不得推荐开放世界/MMO 等大体量品类",
     "ai", ["slots.json", "recommendation.md"]),
    ("能力约束一致", "skill_code=无基础 时方案不得要求编写引擎底层 C++",
     "ai", ["slots.json", "recommendation.md"]),
    ("周期一致", "体量评估不得与 timeline_days 明显矛盾（如 90 天规划超过 3 个系统）",
     "ai", ["slots.json", "recommendation.md"]),
    ("引用纪律", "引用规则/拆解条目必须带 ID（RULE-xxxx/GA-xxxx），否则须声明无参考",
     "ai", ["recommendation.md"]),
    ("提取保真", "idea.txt 中用户明确陈述的约束，在 slots.json 中不得为 null",
     "ai", ["idea.txt", "slots.json"]),
]


def main() -> None:
    ids = next_check_ids(ROOT, len(ITEMS))
    assert ids[0] == "TC-0015", f"ID 假设被推翻: {ids[0]}（若题库变动需同步检测脚本名）"
    out_dir = ROOT / "eval" / "testbank" / "candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    for new_id, (target, check, method, evidence) in zip(ids, ITEMS, strict=True):
        item = {
            "id": new_id, "target": f"[A类] {target}", "check": check,
            "method": method, "evidence": evidence, "expect": "pass",
            "status": "draft", "source": "LLM生成（kimi-cli 外壳，待审）",
        }
        slug = re.sub(r"[^\w一-鿿]+", "_", target)[:20]
        path = out_dir / f"{new_id}_A_{slug}.yaml"
        path.write_text(yaml.safe_dump(item, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
        print(f"  {path.name}")
    print(f"已生成 {len(ITEMS)} 个 A 类候选用例。审批: harness review")


if __name__ == "__main__":
    main()
