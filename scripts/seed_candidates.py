"""首批候选用例播种（由 CLI 外壳 LLM 生成，等效于 harness gen-cases 的产物）。

所有用例 status=draft，等用户 harness review 审批后才激活。
"""

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from harness_core.evaluation.generate import next_check_ids

ROOT = Path(__file__).resolve().parents[1]

# (target, check, method, evidence)
ITEMS = [
    ("帧率稳定性", "目标场景连续运行 5 分钟，平均帧率 ≥60 且 1% low ≥50", "ai", ["fps_log"]),
    ("内存泄漏", "反复切换场景 10 次后，内存增长 ≤5%", "ai", ["memory_log"]),
    ("存档健壮性", "存档写入过程中强制退出，重启后存档可读且不损坏", "human", ["save_files", "crash_log"]),
    ("UI 可读性", "1080p 分辨率下所有正文文本字号 ≥14px", "ai", ["screenshots"]),
    ("新手引导", "首次启动游戏 3 分钟内出现操作引导", "human", ["screen_recording"]),
    ("加载性能", "从启动到主菜单可操作 ≤5 秒", "ai", ["boot_log"]),
    ("跳跃预输入", "落地前 100ms 内按下跳跃，落地后立即起跳", "human", ["screen_recording", "input_log"]),
    ("土狼时间", "走出平台边缘后 100ms 内仍可成功起跳", "human", ["screen_recording", "input_log"]),
    ("碰撞完整性", "角色以最大速度移动时不穿透任何墙体", "ai", ["physics_log", "screen_recording"]),
    ("音频反馈", "跳跃、受伤、拾取三类关键交互均有音效", "human", ["screen_recording"]),
    ("运行稳定性", "连续运行 30 分钟无崩溃无死机", "auto", ["crash_log"]),
    ("分辨率适配", "16:9 与 21:9 分辨率下无 UI 元素溢出屏幕", "ai", ["screenshots"]),
]


def main() -> None:
    ids = next_check_ids(ROOT, len(ITEMS))
    out_dir = ROOT / "eval" / "testbank" / "candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    for new_id, (target, check, method, evidence) in zip(ids, ITEMS, strict=True):
        item = {
            "id": new_id, "target": target, "check": check, "method": method,
            "evidence": evidence, "expect": "pass", "status": "draft",
            "source": "LLM生成（kimi-cli 外壳，待审）",
        }
        slug = re.sub(r"[^\w一-鿿]+", "_", target)[:20]
        path = out_dir / f"{new_id}_{slug}.yaml"
        path.write_text(yaml.safe_dump(item, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
        print(f"  {path.name}")
    print(f"已生成 {len(ITEMS)} 个候选用例。审批: harness review")


if __name__ == "__main__":
    main()
