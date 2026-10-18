"""题库加载器（DESIGN.md §16）。

- 加载 eval/testbank/{dev,golden,canary} 下的 YAML 检查项并校验
- 每个 split 计算 sha256 manifest（内容寻址，run 元信息里记录）
- golden 强制只读：写入守卫，任何写 golden 的尝试直接抛异常
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel

from .schema import CheckItem

SPLITS = ("dev", "golden", "canary", "candidates")


class GoldenReadOnlyError(PermissionError):
    pass


def is_golden_path(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return "golden" in parts


def assert_writable(path: Path) -> None:
    """任何对题库文件的写入都必须经过此守卫。"""
    if is_golden_path(path):
        raise GoldenReadOnlyError(f"golden 集只读，禁止写入: {path}")


class Dataset(BaseModel):
    split: str
    items: dict[str, CheckItem]
    sha256: str


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_split(root: Path, split: str) -> Dataset:
    if split not in SPLITS:
        raise ValueError(f"未知 split: {split}，合法值 {SPLITS}")
    split_dir = root / "eval" / "testbank" / split
    items: dict[str, CheckItem] = {}
    hashes: list[str] = []
    for path in sorted(split_dir.glob("*.yaml")):
        item = CheckItem.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if item.status == "active":
            items[item.id] = item
        hashes.append(_file_sha256(path))
    manifest = hashlib.sha256("".join(sorted(hashes)).encode()).hexdigest()
    return Dataset(split=split, items=items, sha256=manifest)


def load_all(root: Path) -> dict[str, Dataset]:
    return {split: load_split(root, split) for split in SPLITS}
