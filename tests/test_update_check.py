"""版本更新检查测试（DESIGN.md §28）。"""

import json
import time

from tests.conftest import scaffold_root

from harness_core.update_check import (
    UpdateInfo,
    check_for_update,
    notice_text,
    parse_version,
)


def test_parse_version():
    assert parse_version("v0.2.1") == (0, 2, 1)
    assert parse_version("1.0") == (1, 0)
    assert parse_version("0.2.0") > parse_version("0.1.9")


def test_notice_only_when_newer():
    older = UpdateInfo("0.1.0", "0.2.0", "http://x", True)
    same = UpdateInfo("0.1.0", "0.1.0", "http://x", False)
    assert "0.2.0" in notice_text(older)
    assert notice_text(same) is None
    assert notice_text(None) is None


def test_cache_fresh_skips_network(tmp_path):
    root = scaffold_root(tmp_path)
    cache = root / "runs" / ".update_check.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({
        "checked_at": time.time(), "latest": "99.0.0", "url": "http://x",
    }), encoding="utf-8")
    # 缓存新鲜：不联网直接返回（即使 github.com 不通也能拿到结果）
    info = check_for_update(root)
    assert info is not None
    assert info.latest == "99.0.0"
    assert info.update_available


def test_network_failure_silent(tmp_path, monkeypatch):
    root = scaffold_root(tmp_path)
    # 指向必然不存在的仓库：releases 404 → raw 404 → 静默 None，不抛异常
    monkeypatch.setenv("HARNESS_REPO", "nsnhss/definitely-not-exist-harness-xxx")
    info = check_for_update(root, ttl_s=0)
    assert info is None
    # 失败后也写入了 checked_at，避免每次启动都卡 3 秒
    cache = json.loads((root / "runs" / ".update_check.json").read_text(encoding="utf-8"))
    assert "checked_at" in cache
