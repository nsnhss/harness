"""Mock 适配器：离线测试/demo 用，不花钱。

从 YAML 读取罐装响应，按 prompt 中出现的检查项 ID（如 TC-0002）匹配，无匹配用 default。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import yaml

from .base import ChatRequest, ChatResponse

_ID_RE = re.compile(r"TC-\d+")


class MockAdapter:
    name = "mock"

    def __init__(self, responses_path: str | Path):
        self.responses: dict[str, dict] = yaml.safe_load(
            Path(responses_path).read_text(encoding="utf-8")
        )

    async def chat(self, req: ChatRequest) -> ChatResponse:
        started = time.monotonic()
        full_text = "\n".join(m.get("content", "") for m in req.messages)
        match = _ID_RE.search(full_text)
        key = match.group(0) if match else "default"
        entry = self.responses.get(key) or self.responses["default"]
        content = entry if isinstance(entry, str) else json.dumps(entry, ensure_ascii=False)
        return ChatResponse(
            content=content,
            model=f"mock/{req.model}",
            latency_ms=int((time.monotonic() - started) * 1000),
        )
