"""模型接入层基础类型与错误分类（DESIGN.md §15）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


@dataclass
class ChatRequest:
    role: str  # judge / advisor / extractor / challenger
    model: str
    messages: list[dict]
    temperature: float = 0.0
    timeout_s: int = 120


@dataclass
class ChatResponse:
    content: str
    model: str  # 实际使用的模型（fallback 后与请求可能不同）
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    retries: int = 0
    extra: dict = field(default_factory=dict)


class ModelError(Exception):
    """kind: 'retryable' 可重试 / 'fatal' 不可重试。"""

    def __init__(self, message: str, *, kind: str, status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status


def classify_status(status: int) -> str:
    return "retryable" if status in RETRYABLE_STATUSES else "fatal"


class ModelAdapter(Protocol):
    name: str

    async def chat(self, req: ChatRequest) -> ChatResponse: ...
