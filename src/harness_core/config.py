"""项目路径与配置加载（config/models.yaml）。"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


def project_root() -> Path:
    """以本模块位置推项目根（src/harness_core/config.py -> 上两级）。"""
    return Path(__file__).resolve().parents[2]


class RoleConfig(BaseModel):
    primary: str
    fallback: list[str] = Field(default_factory=list)
    timeout_s: int = 120
    temperature: float = 0.0
    stream: bool = False


class ProviderConfig(BaseModel):
    max_concurrency: int = 4
    rpm: int = 50


class RetryConfig(BaseModel):
    max_attempts: int = 5
    backoff_cap_s: int = 60
    retryable: list[int | str] = Field(
        default_factory=lambda: [429, 500, 502, 503, 504, "timeout", "connection_error"]
    )


class Timeouts(BaseModel):
    connect_s: int = 10
    stream_idle_s: int = 30
    total_deadline_s: int = 300


class HarnessConfig(BaseModel):
    roles: dict[str, RoleConfig]
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    timeouts: Timeouts = Field(default_factory=Timeouts)


def load_config(root: Path | None = None) -> HarnessConfig:
    root = root or project_root()
    data = yaml.safe_load((root / "config" / "models.yaml").read_text(encoding="utf-8"))
    return HarnessConfig.model_validate(data)
