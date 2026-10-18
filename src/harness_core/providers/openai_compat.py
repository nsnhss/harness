"""OpenAI 兼容协议适配器（DESIGN.md §15.1）。

覆盖所有兼容 OpenAI chat/completions 协议的厂商（OpenAI/DeepSeek/Kimi/本地 vLLM）。
凭证走环境变量：<VENDOR>_API_KEY / <VENDOR>_BASE_URL，兜底 OPENAI_API_KEY / OPENAI_BASE_URL。
judge 一律非流式（DESIGN.md §15.5）。
"""

from __future__ import annotations

import os
import time

import httpx

from .base import ChatRequest, ChatResponse, ModelError, classify_status


class OpenAICompatAdapter:
    name = "openai_compat"

    def __init__(self, vendor: str = "openai", connect_s: int = 10):
        env = vendor.upper()
        self.base_url = (
            os.environ.get(f"{env}_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self.api_key = os.environ.get(f"{env}_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        self.connect_s = connect_s

    async def chat(self, req: ChatRequest) -> ChatResponse:
        if not self.api_key:
            raise ModelError(f"缺少 API key（{self.name}）", kind="fatal", status=401)
        payload = {
            "model": req.model,
            "messages": req.messages,
            "temperature": req.temperature,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        timeout = httpx.Timeout(req.timeout_s, connect=self.connect_s)
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            raise ModelError(f"网络/超时错误: {e}", kind="retryable") from e
        if resp.status_code != 200:
            raise ModelError(
                f"HTTP {resp.status_code}: {resp.text[:300]}",
                kind=classify_status(resp.status_code),
                status=resp.status_code,
            )
        data = resp.json()
        usage = data.get("usage") or {}
        return ChatResponse(
            content=data["choices"][0]["message"]["content"],
            model=req.model,
            latency_ms=int((time.monotonic() - started) * 1000),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
