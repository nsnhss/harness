"""重试：指数退避 + 全抖动（DESIGN.md §15.3）。

sleep = random(0, min(2^attempt, cap))，最多 max_attempts 次。
fatal 错误不重试，直接抛出。
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .base import ModelError

T = TypeVar("T")


def backoff_s(attempt: int, cap_s: int = 60, *, rand: Callable[[], float] = random.random) -> float:
    """第 attempt 次重试（从 0 开始）的等待秒数，全抖动。"""
    return rand() * min(2**attempt, cap_s)


async def with_retry[T](
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 5,
    cap_s: int = 60,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> tuple[T, int]:
    """执行 fn，遇 retryable 错误退避重试。返回 (结果, 实际重试次数)。"""
    retries = 0
    while True:
        try:
            return await fn(), retries
        except ModelError as e:
            if e.kind == "fatal" or retries >= max_attempts - 1:
                raise
            await sleep(backoff_s(retries, cap_s))
            retries += 1
