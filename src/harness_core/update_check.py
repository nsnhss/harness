"""版本更新检查（DESIGN.md §28）。

策略：启动时检查 + 24h TTL 缓存 + 失败静默。
- 数据源：GitHub Releases（无 release 时退回 main 分支 pyproject.toml 的 version）
- 网络失败（含 github.com 间歇性阻断）一律静默，绝不阻塞 CLI
- 仓库地址可用环境变量 HARNESS_REPO 覆盖（默认 nsnhss/harness）
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

DEFAULT_REPO = "nsnhss/harness"
TTL_S = 24 * 3600
FETCH_TIMEOUT_S = 3.0


@dataclass
class UpdateInfo:
    current: str
    latest: str
    url: str
    update_available: bool
    error: str | None = None


def parse_version(text: str) -> tuple[int, ...]:
    """'v0.2.1' -> (0, 2, 1)。无法解析的部分按 0 处理。"""
    nums = []
    for part in text.lstrip("vV").split("."):
        digits = "".join(c for c in part if c.isdigit())
        nums.append(int(digits) if digits else 0)
    return tuple(nums)


def current_version(root: Path) -> str:
    for line in (root / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


def _fetch_latest(repo: str) -> tuple[str, str]:
    """返回 (latest_version, url)。失败抛异常，由上层静默。"""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=FETCH_TIMEOUT_S) as client:
        resp = client.get(
            f"https://api.github.com/repos/{repo}/releases/latest", headers=headers
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["tag_name"].lstrip("vV"), data["html_url"]
        # 无 release：退回 main 分支 pyproject.toml
        # 用 contents API 而非 raw.githubusercontent.com（后者在部分网络不可达）
        resp = client.get(
            f"https://api.github.com/repos/{repo}/contents/pyproject.toml",
            headers={**headers, "Accept": "application/vnd.github.raw"},
        )
        resp.raise_for_status()
        for line in resp.text.splitlines():
            if line.strip().startswith("version"):
                ver = line.split("=", 1)[1].strip().strip('"')
                return ver, f"https://github.com/{repo}"
    raise RuntimeError("无法解析远端版本")


def check_for_update(root: Path, *, ttl_s: int = TTL_S) -> UpdateInfo | None:
    """主入口。缓存新鲜直接返回缓存；任何网络错误静默返回 None。"""
    cache_path = root / "runs" / ".update_check.json"
    cache: dict = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache = {}
    current = current_version(root)

    if time.time() - cache.get("checked_at", 0) < ttl_s and "latest" in cache:
        latest, url = cache["latest"], cache["url"]
        return UpdateInfo(current, latest, url, parse_version(latest) > parse_version(current))

    repo = os.environ.get("HARNESS_REPO", DEFAULT_REPO)
    try:
        latest, url = _fetch_latest(repo)
    except Exception:  # noqa: BLE001 —— 失败静默是设计纪律
        # 记录检查时间，避免网络不通时每次启动都卡 3 秒
        cache["checked_at"] = time.time()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        return None
    cache.update({"checked_at": time.time(), "latest": latest, "url": url})
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return UpdateInfo(current, latest, url, parse_version(latest) > parse_version(current))


def notice_text(info: UpdateInfo | None) -> str | None:
    if info and info.update_available:
        return (
            f"💡 harness 有新版本：{info.current} → {info.latest} "
            f"（{info.url}）。拉取更新: git pull"
        )
    return None
