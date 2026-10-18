"""harness CLI（DESIGN.md §25 三层视图 + 人工裁决入口）。

用法：
  harness run --evidence <dir> [--provider mock] [--split dev]
  harness gate <run_id>      交互式裁决（y/n/u + 可选一句话原因）
  harness report <run_id>    重新生成并打印 report.md
  harness show <run_id> <check_id>
  harness call <run_id> <call_id>
  harness distill <run_id>   重新生成规则草稿
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from .advisor.consult import advise
from .config import load_config, project_root
from .evaluation import review as review_mod
from .evaluation.generate import generate
from .evaluation.loader import SPLITS
from .evaluation.schema import Verdict
from .pipeline.runner import Runner
from .providers.mock import MockAdapter
from .providers.openai_compat import OpenAICompatAdapter
from .providers.router import Router
from .report import generate_report
from .update_check import check_for_update, current_version, notice_text


def _update_notice(root: Path) -> None:
    """每个命令执行后静默检查更新；失败不打扰（DESIGN.md §28）。"""
    try:
        text = notice_text(check_for_update(root))
    except Exception:  # noqa: BLE001 —— 失败静默是设计纪律
        return
    if text:
        print(f"\n{text}", file=sys.stderr)


def _build_runner(root: Path, provider: str) -> Runner:
    config = load_config(root)
    if provider == "mock":
        adapter = MockAdapter(root / "examples" / "mock_responses.yaml")
    else:
        adapter = OpenAICompatAdapter(vendor=provider,
                                      connect_s=config.timeouts.connect_s)
    return Runner(root, Router(config, adapter))


def cmd_run(args: argparse.Namespace) -> None:
    root = project_root()
    runner = _build_runner(root, args.provider)
    run_id = asyncio.run(runner.run(Path(args.evidence), split=args.split))
    print(f"run 完成: {run_id}")
    print(f"待裁决: {root / 'runs' / run_id / 'pending_verdicts.json'}")
    print(f"下一步: harness gate {run_id}")


def cmd_gate(args: argparse.Namespace) -> None:
    root = project_root()
    runner = _build_runner(root, "mock")  # gate 不需要真实模型
    verdicts = runner.read_verdicts(args.run_id)
    pending = [v for v in verdicts if v["human_verdict"] is None]
    if not pending:
        print("没有待裁决项。")
        return
    keymap = {"y": Verdict.PASS.value, "n": Verdict.FAIL.value, "u": Verdict.UNABLE.value}
    print(f"共 {len(pending)} 项待裁决。输入 y=pass / n=fail / u=unable / s=跳过\n")
    for v in pending:
        print(f"[{v['check_id']}] {v['check']}")
        print(f"  AI 判定: {v['ai_verdict']}  理由: {v['ai_reason']}")
        print(f"  证据: {', '.join(v.get('evidence_refs') or [])}")
        choice = input("  你的裁决 (y/n/u/s): ").strip().lower()
        if choice == "s" or choice not in keymap:
            continue
        v["human_verdict"] = keymap[choice]
        note = input("  一句话原因（可空，fail 时强烈建议填）: ").strip()
        if note:
            v["human_note"] = note
        print()
    runner.write_verdicts(args.run_id, verdicts)
    drafts = runner.distill(args.run_id)
    if drafts:
        print(f"已生成 {len(drafts)} 份规则草稿（rules/pending/，待你确认）：")
        for d in drafts:
            print(f"  {d.name}")
    print(generate_report(runner, args.run_id))


def cmd_report(args: argparse.Namespace) -> None:
    runner = Runner(project_root(), None)  # type: ignore[arg-type]
    print(generate_report(runner, args.run_id))


def cmd_show(args: argparse.Namespace) -> None:
    runner = Runner(project_root(), None)  # type: ignore[arg-type]
    for v in runner.read_verdicts(args.run_id):
        if v["check_id"] == args.check_id:
            print(json.dumps(v, ensure_ascii=False, indent=2))
            return
    print(f"未找到检查项 {args.check_id}", file=sys.stderr)
    sys.exit(1)


def cmd_call(args: argparse.Namespace) -> None:
    path = project_root() / "runs" / args.run_id / "calls" / f"{args.call_id}.json"
    if not path.exists():
        print(f"未找到调用记录 {path}", file=sys.stderr)
        sys.exit(1)
    print(path.read_text(encoding="utf-8"))


def cmd_distill(args: argparse.Namespace) -> None:
    runner = Runner(project_root(), None)  # type: ignore[arg-type]
    drafts = runner.distill(args.run_id)
    print(f"生成 {len(drafts)} 份规则草稿。")


def cmd_advise(args: argparse.Namespace) -> None:
    """单次咨询：真实调 LLM 出方案，产物落盘为 eval 证据。"""
    root = project_root()
    runner = _build_runner(root, args.provider)
    evidence_dir = asyncio.run(advise(root, runner.router, args.idea))
    print(f"方案: {evidence_dir / 'recommendation.md'}")
    print(f"槽位: {evidence_dir / 'slots.json'}")
    print(f"\n用 A 类题库评估它: harness run --evidence {evidence_dir} --provider {args.provider}")


def cmd_gen_cases(args: argparse.Namespace) -> None:
    """LLM 生成候选用例（草稿，待 review 审批）。"""
    root = project_root()
    runner_builder = _build_runner(root, args.provider)
    run_dir = root / "runs" / "gen"
    run_dir.mkdir(parents=True, exist_ok=True)
    written = asyncio.run(
        generate(root, runner_builder.router, args.topic, args.n)
    )
    print(f"已生成 {len(written)} 个候选用例（eval/testbank/candidates/）：")
    for p in written:
        print(f"  {p.name}")
    print("\n下一步: harness review  （逐条审批，y=入库 / n=拒绝）")


def cmd_review(_args: argparse.Namespace) -> None:
    """审批候选用例：审的是用例和期望答案本身是否合格（DESIGN.md §14.1）。"""
    root = project_root()
    drafts = review_mod.list_drafts(root)
    if not drafts:
        print("没有待审候选用例。用 harness gen-cases 生成。")
        return
    approved = rejected = 0
    print(f"共 {len(drafts)} 条待审。y=入库 / n=拒绝 / s=跳过")
    print("审批标准：① 可证伪（有明确判据）② method 恰当 ③ 证据拿得到 ④ expect 合理\n")
    method_cn = {"auto": "auto（脚本客观检测）", "ai": "ai（AI 看证据判）",
                 "human": "human（必须人判）"}
    for idx, path in enumerate(drafts, 1):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        print(f"[{idx}/{len(drafts)}] {data['id']} · {data['target']}")
        print(f"  判定内容: {data['check']}")
        print(f"  判定方式: {method_cn.get(data['method'], data['method'])}"
              f"   证据要求: {', '.join(data.get('evidence') or []) or '无'}")
        print(f"  期望答案: {data['expect']}")
        choice = input("  审批 (y/n/s): ").strip().lower()
        if choice == "y":
            review_mod.approve(root, path)
            approved += 1
        elif choice == "n":
            note = input("  拒绝原因（一句话）: ").strip()
            review_mod.reject(root, path, note)
            rejected += 1
        print()
    print(f"审批完成：入库 {approved}，拒绝 {rejected}，跳过 {len(drafts) - approved - rejected}")


def cmd_doctor(_args: argparse.Namespace) -> None:
    """环境与版本体检：当前版本、更新、缓存目录位置。"""
    root = project_root()
    print(f"harness 版本: {current_version(root)}")
    info = check_for_update(root, ttl_s=0)  # doctor 强制联网刷新
    if info is None:
        print("更新检查: 网络不可达（已静默跳过）")
    else:
        state = "有新版本可用！" if info.update_available else "已是最新"
        print(f"远端版本: {info.latest}（{state}）")
    venv = root / ".venv"
    print(f"虚拟环境: {venv}（{'存在' if venv.exists() else '缺失'}）")
    print("缓存纪律: UV_CACHE_DIR/PIP_CACHE_DIR 应指向 D:\\dev\\cache\\（见 AGENTS.md）")


def main() -> None:
    parser = argparse.ArgumentParser(prog="harness")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="跑五阶段流水线")
    p.add_argument("--evidence", required=True, help="证据目录（阶段1为模拟证据）")
    p.add_argument("--provider", default="mock", help="mock 或 openai 等厂商名")
    p.add_argument("--split", default="dev", choices=SPLITS)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("gate", help="交互式人工裁决")
    p.add_argument("run_id")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("report", help="生成报告")
    p.add_argument("run_id")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("show", help="单案例详情")
    p.add_argument("run_id")
    p.add_argument("check_id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("call", help="单次调用完整 prompt/response")
    p.add_argument("run_id")
    p.add_argument("call_id")
    p.set_defaults(func=cmd_call)

    p = sub.add_parser("distill", help="生成规则草稿")
    p.add_argument("run_id")
    p.set_defaults(func=cmd_distill)

    p = sub.add_parser("advise", help="单次咨询：想法 → 方案（真实 LLM）")
    p.add_argument("idea", help="你的游戏想法和要求")
    p.add_argument("--provider", default="deepseek")
    p.set_defaults(func=cmd_advise)

    p = sub.add_parser("gen-cases", help="LLM 生成候选用例")
    p.add_argument("--topic", default="通用游戏质量", help="出题主题")
    p.add_argument("--n", type=int, default=12, help="生成数量")
    p.add_argument("--provider", default="openai", help="mock 或厂商名")
    p.set_defaults(func=cmd_gen_cases)

    p = sub.add_parser("review", help="审批候选用例")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("doctor", help="环境与版本体检")
    p.set_defaults(func=cmd_doctor)

    args = parser.parse_args()
    args.func(args)
    _update_notice(project_root())


if __name__ == "__main__":
    main()
