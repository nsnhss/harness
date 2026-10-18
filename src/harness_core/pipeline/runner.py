"""五阶段流水线（DESIGN.md §18）。

collect → auto_check → ai_judge → human_gate → distill
每阶段落盘 runs/<run_id>/stage_<name>.json，支持断点续跑。
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

from ..evaluation.judge import judge_check
from ..evaluation.loader import Dataset, load_split
from ..evaluation.schema import Verdict
from ..observability.trace import Tracer
from ..providers.router import Router

STAGES = ["collect", "auto_check", "ai_judge", "human_gate", "distill"]


def new_run_id() -> str:
    return time.strftime("%Y-%m-%d_%H%M%S")


class Runner:
    def __init__(self, root: Path, router: Router):
        self.root = root
        self.router = router

    # ---------- 工具 ----------

    def run_dir(self, run_id: str) -> Path:
        return self.root / "runs" / run_id

    def _stage_done(self, run_id: str, stage: str) -> bool:
        return (self.run_dir(run_id) / f"stage_{stage}.json").exists()

    def _mark_done(self, run_id: str, stage: str, extra: dict | None = None) -> None:
        payload = {"stage": stage, "finished_at": time.time(), **(extra or {})}
        (self.run_dir(run_id) / f"stage_{stage}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def read_verdicts(self, run_id: str) -> list[dict]:
        path = self.run_dir(run_id) / "verdicts.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def write_verdicts(self, run_id: str, verdicts: list[dict]) -> None:
        path = self.run_dir(run_id) / "verdicts.jsonl"
        path.write_text(
            "\n".join(json.dumps(v, ensure_ascii=False) for v in verdicts) + "\n",
            encoding="utf-8",
        )

    # ---------- 阶段 ----------

    def _collect(self, run_id: str, evidence_src: Path) -> None:
        dest = self.run_dir(run_id) / "evidence"
        dest.mkdir(parents=True, exist_ok=True)
        for f in evidence_src.glob("*"):
            if f.is_file():
                shutil.copy2(f, dest / f.name)
        self._mark_done(run_id, "collect", {"source": str(evidence_src)})

    def _auto_check(self, run_id: str, dataset: Dataset) -> list[dict]:
        verdicts = []
        for item in dataset.items.values():
            if item.method != "auto":
                continue
            script = self.root / "scripts" / "checks" / f"{item.id}.py"
            entry = {"check_id": item.id, "target": item.target, "check": item.check,
                     "method": "auto", "ai_verdict": None, "ai_reason": None,
                     "evidence_refs": item.evidence, "human_verdict": None, "human_note": None}
            if not script.exists():
                entry.update(auto_exit=2, ai_verdict=Verdict.UNABLE.value,
                             ai_reason=f"检测脚本缺失: {script}")
            else:
                env = {**os.environ, "PYTHONIOENCODING": "utf-8"}  # 统一子进程输出编码
                proc = subprocess.run(
                    [sys.executable, str(script), str(self.run_dir(run_id) / "evidence")],
                    capture_output=True, timeout=60, check=False,
                    encoding="utf-8", errors="replace", env=env,
                )
                code = proc.returncode
                verdict = {0: Verdict.PASS, 1: Verdict.FAIL}.get(code, Verdict.UNABLE)
                entry.update(auto_exit=code, ai_verdict=verdict.value,
                             ai_reason=(proc.stdout or proc.stderr).strip()[:200],
                             actual_model="auto-script")
            verdicts.append(entry)
        return verdicts

    async def _ai_judge(self, run_id: str, dataset: Dataset) -> list[dict]:
        tracer = Tracer(self.root, self.run_dir(run_id))
        evidence_dir = self.run_dir(run_id) / "evidence"
        sem = asyncio.Semaphore(4)
        targets = [i for i in dataset.items.values() if i.method in ("ai", "human")]

        async def one(item):
            async with sem:
                result = await judge_check(item, evidence_dir, self.router, tracer, run_id, self.root)
            return {"check_id": item.id, "target": item.target, "check": item.check,
                    "method": item.method, "ai_verdict": result.verdict.value,
                    "ai_reason": result.reason, "evidence_refs": result.evidence_refs,
                    "actual_model": result.actual_model, "call_id": result.call_id,
                    "human_verdict": None, "human_note": None}

        return list(await asyncio.gather(*(one(i) for i in targets)))

    def _human_gate(self, run_id: str) -> None:
        pending = [v for v in self.read_verdicts(run_id) if v["human_verdict"] is None]
        out = self.run_dir(run_id) / "pending_verdicts.json"
        out.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
        self._mark_done(run_id, "human_gate", {"pending": len(pending)})

    def distill(self, run_id: str) -> list[Path]:
        """对人判 fail 或人机不一致的项生成规则草稿（rules/pending/，待用户确认）。"""
        pending_dir = self.root / "rules" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for v in self.read_verdicts(run_id):
            human, ai = v["human_verdict"], v["ai_verdict"]
            disagree = human is not None and ai is not None and human != ai
            if human != Verdict.FAIL.value and not disagree:
                continue
            draft = {
                "id": f"RULE-DRAFT-{v['check_id']}",
                "rule": f"[待提炼] 检查项「{v['check']}」的判定分歧/失败需要沉淀规则",
                "scope": ["judge"],
                "source": {"run_id": run_id, "check_id": v["check_id"],
                           "quote": v.get("human_note") or ""},
                "created": time.strftime("%Y-%m-%d"),
                "status": "pending",  # 用户确认后改 active 并移入 rules/
                "context": {"ai_verdict": ai, "ai_reason": v.get("ai_reason"),
                            "human_verdict": human},
            }
            path = pending_dir / f"RULE-DRAFT-{v['check_id']}.yaml"
            path.write_text(yaml.safe_dump(draft, allow_unicode=True, sort_keys=False),
                            encoding="utf-8")
            written.append(path)
        return written

    # ---------- 主流程 ----------

    async def run(self, evidence_src: Path, split: str = "dev") -> str:
        run_id = new_run_id()
        self.run_dir(run_id).mkdir(parents=True, exist_ok=True)
        dataset = load_split(self.root, split)

        # run 元信息：题库哈希等（DESIGN.md §24 可回放的前提）
        meta = {"run_id": run_id, "split": split, "dataset_sha256": dataset.sha256,
                "created_at": time.time()}
        (self.run_dir(run_id) / "run.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        if not self._stage_done(run_id, "collect"):
            self._collect(run_id, evidence_src)
        if not self._stage_done(run_id, "auto_check"):
            verdicts = self._auto_check(run_id, dataset)
            self.write_verdicts(run_id, verdicts)
            self._mark_done(run_id, "auto_check", {"auto_items": len(verdicts)})
        if not self._stage_done(run_id, "ai_judge"):
            judged = await self._ai_judge(run_id, dataset)
            verdicts = self.read_verdicts(run_id) + judged
            self.write_verdicts(run_id, verdicts)
            self._mark_done(run_id, "ai_judge", {"judged_items": len(judged)})
        if not self._stage_done(run_id, "human_gate"):
            self._human_gate(run_id)
        return run_id
