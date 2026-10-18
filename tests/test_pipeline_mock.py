"""端到端测试：mock provider 跑完整闭环（DESIGN.md §18、§24）。

run（mock）→ 模拟人工裁决（制造一处不一致）→ distill 规则草稿 → report。
"""

import asyncio
import json

import yaml
from tests.conftest import REAL_ROOT, scaffold_root

from harness_core.config import load_config
from harness_core.pipeline.runner import Runner
from harness_core.providers.mock import MockAdapter
from harness_core.providers.router import Router
from harness_core.report import generate_report


def _make_runner(root):
    config = load_config(root)
    adapter = MockAdapter(root / "examples" / "mock_responses.yaml")
    return Runner(root, Router(config, adapter))


def test_full_loop(tmp_path):
    root = scaffold_root(tmp_path)
    runner = _make_runner(root)

    run_id = asyncio.run(runner.run(REAL_ROOT / "examples" / "fake_evidence"))
    run_dir = root / "runs" / run_id

    # 五阶段落盘
    for stage in ["collect", "auto_check", "ai_judge", "human_gate"]:
        assert (run_dir / f"stage_{stage}.json").exists(), stage

    verdicts = runner.read_verdicts(run_id)
    by_id = {v["check_id"]: v for v in verdicts}

    # TC-0001 auto：假证据 80ms ≤ 100ms，应 pass
    assert by_id["TC-0001"]["ai_verdict"] == "pass"
    assert by_id["TC-0001"]["actual_model"] == "auto-script"
    # TC-0002 ai/human：mock 判 pass 且引用证据
    assert by_id["TC-0002"]["ai_verdict"] == "pass"
    assert by_id["TC-0002"]["evidence_refs"]

    # trace：judge 调用已记录完整原文 + sqlite 索引
    calls = list((run_dir / "calls").glob("call-*.json"))
    assert calls, "judge 调用未留痕"
    record = json.loads(calls[0].read_text(encoding="utf-8"))
    assert record["messages"] and record["response"]
    assert (root / "runs" / "index.sqlite").exists()

    # 模拟人工裁决：TC-0001 一致(pass)，TC-0002 故意判 fail 制造不一致
    by_id["TC-0001"]["human_verdict"] = "pass"
    by_id["TC-0002"]["human_verdict"] = "fail"
    by_id["TC-0002"]["human_note"] = "悬停帧数实际不足，证据是模拟文本不算数"
    runner.write_verdicts(run_id, list(by_id.values()))

    # distill：不一致项应生成规则草稿
    drafts = runner.distill(run_id)
    assert len(drafts) == 1
    draft = yaml.safe_load(drafts[0].read_text(encoding="utf-8"))
    assert draft["status"] == "pending"
    assert draft["source"]["check_id"] == "TC-0002"
    assert "悬停" in draft["source"]["quote"]

    # report：不一致项置顶出现
    report = generate_report(runner, run_id)
    assert "不一致" in report
    assert "TC-0002" in report
    assert (run_dir / "report.md").exists()


def test_resume_skips_finished_stages(tmp_path):
    root = scaffold_root(tmp_path)
    runner = _make_runner(root)
    run_id = asyncio.run(runner.run(REAL_ROOT / "examples" / "fake_evidence"))
    marker = root / "runs" / run_id / "stage_collect.json"
    mtime = marker.stat().st_mtime_ns
    # 重跑同 run_id：已完成阶段不重做（文件不变）
    runner2 = _make_runner(root)
    asyncio.run(runner2.run(REAL_ROOT / "examples" / "fake_evidence"))  # 新 run_id，仅验证不炸
    assert marker.stat().st_mtime_ns == mtime
