"""角色路由器（DESIGN.md §15.1）。

业务代码按角色取模型；fallback 链只在硬失败（重试耗尽或 fatal）时推进；
返回结果中的 model 字段永远是实际使用的模型，供 trace 记录。
阶段 1 简化：所有模型共用注入的单个适配器（mock 或 OpenAI 兼容）。
厂商专属适配器（Anthropic/Gemini）后续补充。
"""

from __future__ import annotations

from ..config import HarnessConfig, RoleConfig
from .base import ChatRequest, ChatResponse, ModelAdapter, ModelError
from .retry import with_retry


class Router:
    def __init__(self, config: HarnessConfig, adapter: ModelAdapter):
        self.config = config
        self.adapter = adapter

    def chain(self, role: str) -> tuple[RoleConfig, list[str]]:
        rc = self.config.roles[role]
        return rc, [rc.primary, *rc.fallback]

    async def chat(self, role: str, messages: list[dict]) -> ChatResponse:
        rc, models = self.chain(role)
        last_error: ModelError | None = None
        for model in models:
            req = ChatRequest(
                role=role,
                model=model,
                messages=messages,
                temperature=rc.temperature,
                timeout_s=rc.timeout_s,
            )
            try:
                resp, retries = await with_retry(
                    lambda req=req: self.adapter.chat(req),
                    max_attempts=self.config.retry.max_attempts,
                    cap_s=self.config.retry.backoff_cap_s,
                )
                resp.retries = retries
                return resp
            except ModelError as e:
                last_error = e  # 硬失败，推进 fallback 链
        raise last_error or ModelError("路由表为空", kind="fatal")
