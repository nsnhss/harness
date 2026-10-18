"""report.md 生成（DESIGN.md §19、§25）：不一致清单永远置顶。"""

from __future__ import annotations

from .pipeline.runner import Runner


def generate_report(runner: Runner, run_id: str) -> str:
    verdicts = runner.read_verdicts(run_id)
    total = len(verdicts)
    ai_pass = sum(1 for v in verdicts if v["ai_verdict"] == "pass")
    ai_fail = sum(1 for v in verdicts if v["ai_verdict"] == "fail")
    unable = [v for v in verdicts if v["ai_verdict"] == "unable"]
    judged_human = [v for v in verdicts if v["human_verdict"] is not None]
    disagreements = [
        v for v in judged_human
        if v["ai_verdict"] is not None and v["human_verdict"] != v["ai_verdict"]
    ]

    summary = (
        f"总项数 {total} | AI判 pass {ai_pass} | fail {ai_fail} | unable {len(unable)} "
        f"| 已人工裁决 {len(judged_human)} | 不一致 {len(disagreements)}"
    )
    lines = [f"## Run {run_id} 摘要", "", summary, ""]

    lines += ["### ⚠️ 不一致项（AI判 ≠ 你判）—— 需要你归因", ""]
    if disagreements:
        lines += ["| 检查项 | AI | 你 | AI 的理由 |", "|---|---|---|---|"]
        for v in disagreements:
            lines.append(
                f"| {v['check_id']} {v['check'][:30]} | {v['ai_verdict']} | "
                f"{v['human_verdict']} | {(v['ai_reason'] or '')[:60]} |"
            )
    else:
        lines.append("（无）")

    lines += ["", "### unable 项 —— 需要检查证据采集", ""]
    if unable:
        for v in unable:
            lines.append(f"- {v['check_id']}: {v['ai_reason']}")
    else:
        lines.append("（无）")

    lines += ["", "### 全部判定", ""]
    lines += ["| 检查项 | 方法 | AI | 人 |", "|---|---|---|---|"]
    for v in verdicts:
        lines.append(
            f"| {v['check_id']} {v['check'][:40]} | {v['method']} | "
            f"{v['ai_verdict']} | {v['human_verdict'] or '待裁决'} |"
        )

    text = "\n".join(lines) + "\n"
    (runner.run_dir(run_id) / "report.md").write_text(text, encoding="utf-8")
    return text
