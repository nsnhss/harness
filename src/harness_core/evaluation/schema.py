"""Eval 数据契约（DESIGN.md §8、§20）。

二元判断铁律：verdict 只有 pass / fail / unable，禁止评级。
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNABLE = "unable"  # 证据不足/解析失败时的合法出口，路由给人工


class CheckItem(BaseModel):
    """原子检查项：一句话、可证伪、二元判断。"""

    id: str
    target: str
    check: str
    method: Literal["auto", "ai", "human"]
    evidence: list[str] = Field(default_factory=list)
    expect: Verdict = Verdict.PASS
    status: Literal["active", "deprecated", "draft", "rejected"] = "active"
    source: str = ""


class JudgeResult(BaseModel):
    """judge 输出契约：判定 + 证据引用 + 一句话理由。无证据引用的 pass/fail 无效。"""

    verdict: Verdict
    evidence_refs: list[str] = Field(default_factory=list)
    reason: str = Field(default="", max_length=200)  # prompt 要求 ≤50 字，此处为硬上限
    actual_model: str = ""
    call_id: str = ""
