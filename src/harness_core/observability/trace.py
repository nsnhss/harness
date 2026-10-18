"""观测与追踪（DESIGN.md §19）。

每次模型调用：完整 prompt 原文 + 完整响应写 runs/<run_id>/calls/call-NNNN.json；
同时向 runs/index.sqlite 插入索引行供统计查询。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path


class Tracer:
    def __init__(self, root: Path, run_dir: Path):
        self.calls_dir = run_dir / "calls"
        self.calls_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = root / "runs" / "index.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calls (
                    trace_id TEXT PRIMARY KEY,
                    run_id TEXT, role TEXT, model TEXT,
                    latency_ms INTEGER, tokens INTEGER, retries INTEGER,
                    prompt_sha256 TEXT, created_at REAL
                )
                """
            )

    def _next_call_id(self) -> str:
        existing = sorted(self.calls_dir.glob("call-*.json"))
        return f"call-{len(existing) + 1:04d}"

    @staticmethod
    def prompt_hash(messages: list[dict]) -> str:
        blob = "\n".join(m.get("content", "") for m in messages)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def record(
        self,
        *,
        run_id: str,
        role: str,
        model: str,
        messages: list[dict],
        response: str,
        latency_ms: int,
        tokens: int,
        retries: int,
    ) -> str:
        call_id = self._next_call_id()
        sha = self.prompt_hash(messages)
        payload = {
            "trace_id": f"{run_id}/{call_id}",
            "run_id": run_id,
            "role": role,
            "model": model,  # 实际使用的模型（fallback 后）
            "messages": messages,  # 完整 prompt 原文
            "response": response,  # 完整响应原文
            "latency_ms": latency_ms,
            "tokens": tokens,
            "retries": retries,
            "prompt_sha256": sha,
            "created_at": time.time(),
        }
        (self.calls_dir / f"{call_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?)",
                (payload["trace_id"], run_id, role, model, latency_ms, tokens, retries, sha,
                 payload["created_at"]),
            )
        return call_id
