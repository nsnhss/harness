"""题库加载器测试（DESIGN.md §16）。"""

import pytest
from tests.conftest import scaffold_root

from harness_core.evaluation.loader import (
    GoldenReadOnlyError,
    assert_writable,
    load_split,
)


def test_load_dev_split(tmp_path):
    root = scaffold_root(tmp_path)
    ds = load_split(root, "dev")
    assert ds.split == "dev"
    assert "TC-0001" in ds.items
    assert "TC-0002" in ds.items
    assert len(ds.sha256) == 64  # sha256 hex


def test_manifest_stable(tmp_path):
    root = scaffold_root(tmp_path)
    assert load_split(root, "dev").sha256 == load_split(root, "dev").sha256


def test_golden_readonly_guard(tmp_path):
    root = scaffold_root(tmp_path)
    with pytest.raises(GoldenReadOnlyError):
        assert_writable(root / "eval" / "testbank" / "golden" / "TC-9999.yaml")
    # dev 目录可写，不抛异常
    assert_writable(root / "eval" / "testbank" / "dev" / "TC-9999.yaml")


def test_unknown_split_rejected(tmp_path):
    root = scaffold_root(tmp_path)
    with pytest.raises(ValueError):
        load_split(root, "prod")
