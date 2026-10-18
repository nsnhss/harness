"""候选用例审批（DESIGN.md §14.1）：LLM 出题，人定答案。

approve → 移入 dev 激活；reject → 标 rejected 留在 candidates（只增不删铁律，
 rejected 也保留，未来能回溯"什么样的题不合格"）。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .generate import CANDIDATES_DIR
from .loader import assert_writable


def list_drafts(root: Path) -> list[Path]:
    """所有待审候选（status: draft）。"""
    drafts = []
    for path in sorted((root / CANDIDATES_DIR).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("status") == "draft":
            drafts.append(path)
    return drafts


def approve(root: Path, path: Path, note: str = "") -> Path:
    """审批通过：status→active，移入 dev 题库。"""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["status"] = "active"
    if note:
        data["review_note"] = note
    dest = root / "eval" / "testbank" / "dev" / path.name
    assert_writable(dest)
    dest.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    path.unlink()
    return dest


def reject(root: Path, path: Path, note: str = "") -> None:
    """审批拒绝：标 rejected 留在原地（不删除，留档）。"""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["status"] = "rejected"
    data["review_note"] = note
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
