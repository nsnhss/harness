"""测试公共工具：在 tmp_path 搭一个最小项目根。"""

import shutil
from pathlib import Path

REAL_ROOT = Path(__file__).resolve().parents[1]


def scaffold_root(tmp_path: Path) -> Path:
    """复制运行所需的最小目录结构到临时根。"""
    root = tmp_path / "proj"
    for rel in [
        "pyproject.toml",
        "config/models.yaml",
        "config/slots_schema.yaml",
        "eval/testbank/dev",
        "eval/testbank/golden",
        "eval/testbank/canary",
        "scripts/checks",
        "prompts",
        "rules",
        "game_analysis",
        "examples/mock_responses.yaml",
    ]:
        src = REAL_ROOT / rel
        dst = root / rel
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return root
