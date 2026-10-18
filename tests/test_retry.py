"""重试策略测试（DESIGN.md §15.3）。"""

import asyncio

import pytest

from harness_core.providers.base import ModelError, classify_status
from harness_core.providers.retry import backoff_s, with_retry


def test_status_classification():
    assert classify_status(429) == "retryable"
    assert classify_status(503) == "retryable"
    assert classify_status(400) == "fatal"
    assert classify_status(401) == "fatal"


def test_backoff_bounded_and_jittered():
    # attempt 很大时也不超过 cap
    assert backoff_s(100, 60) <= 60
    # 全抖动：固定随机源时上界为 2^attempt
    assert backoff_s(3, 60, rand=lambda: 1.0) == 8


async def _noop_sleep(_: float) -> None:
    return None


def test_retry_succeeds_after_transient():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ModelError("boom", kind="retryable", status=429)
        return "ok"

    result, retries = asyncio.run(with_retry(flaky, sleep=_noop_sleep))
    assert result == "ok"
    assert retries == 2


def test_fatal_not_retried():
    calls = {"n": 0}

    async def fatal():
        calls["n"] += 1
        raise ModelError("bad request", kind="fatal", status=400)

    with pytest.raises(ModelError):
        asyncio.run(with_retry(fatal, sleep=_noop_sleep))
    assert calls["n"] == 1
