"""顾问层 v0 测试：extractor + advisor 两调用链，产物落盘（DESIGN.md §6）。"""

import asyncio
import json

from tests.conftest import scaffold_root

from harness_core.advisor.consult import advise
from harness_core.config import load_config
from harness_core.providers.base import ChatResponse
from harness_core.providers.router import Router


class StubAdapter:
    """按顺序返回罐装响应的测试适配器。"""

    name = "stub"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    async def chat(self, req):
        content = self.responses.pop(0)
        return ChatResponse(content=content, model=f"stub/{req.model}")


def _router(root, responses):
    return Router(load_config(root), StubAdapter(responses))


def test_advise_full_chain(tmp_path):
    root = scaffold_root(tmp_path)
    router = _router(root, [
        json.dumps({"game_type": "平台跳跃", "team_size": 1, "skill_code": "无基础"},
                   ensure_ascii=False),
        (
            "## 核心循环\n跑跳。\n\n## 引擎推荐\nUnity。\n\n## 体量评估\n小。\n\n"
            "## 风险清单\n无参考。\n\n## 里程碑\n两周原型。"
        ),
    ])
    evidence = asyncio.run(advise(root, router, "我想一个人做平台跳跃游戏"))

    # 三件证据落盘
    assert (evidence / "idea.txt").read_text(encoding="utf-8") == "我想一个人做平台跳跃游戏"
    slots = json.loads((evidence / "slots.json").read_text(encoding="utf-8"))
    assert slots["game_type"] == "平台跳跃"
    assert slots["team_size"] == 1
    rec = (evidence / "recommendation.md").read_text(encoding="utf-8")
    assert "引擎推荐" in rec

    # 两次调用都留痕（extractor + advisor）
    calls = list((evidence.parent / "calls").glob("call-*.json"))
    assert len(calls) == 2


def test_advise_extractor_garbage_fallback(tmp_path):
    root = scaffold_root(tmp_path)
    router = _router(root, ["这不是 JSON", "## 核心循环\n……"])
    evidence = asyncio.run(advise(root, router, "随便"))
    slots = json.loads((evidence / "slots.json").read_text(encoding="utf-8"))
    assert "_extract_error" in slots  # 提取失败如实记录，不崩不编


def test_enum_violation_coerced_to_null(tmp_path):
    """修复验证：枚举槽位输出自由文本 → 置 null + 记违规（漏报修复）。"""
    root = scaffold_root(tmp_path)
    router = _router(root, [
        json.dumps({"game_type": "横版动作游戏", "skill_code": "会一点编程",
                    "team_size": 1}, ensure_ascii=False),
        "## 核心循环\n……",
    ])
    evidence = asyncio.run(advise(root, router, "我想一个人做横版动作游戏"))
    slots = json.loads((evidence / "slots.json").read_text(encoding="utf-8"))
    assert slots["game_type"] is None       # 非枚举值被拦下
    assert slots["skill_code"] is None
    assert slots["team_size"] == 1          # 合法值不受影响
    assert len(slots["_violations"]) == 2   # 违规如实记录（eval 证据）


def test_scope_signals_deterministic(tmp_path):
    """修复验证：危险信号词表匹配，LLM 语义判断只存档不采用（误报修复）。"""
    root = scaffold_root(tmp_path)
    router = _router(root, [
        json.dumps({"scope_signals": ["三个月", "一个人"]}, ensure_ascii=False),
        "## 核心循环\n……",
    ])
    evidence = asyncio.run(advise(root, router, "我想三个月一个人做个游戏"))
    slots = json.loads((evidence / "slots.json").read_text(encoding="utf-8"))
    assert slots["scope_signals"] == []                      # 普通描述不是危险信号
    assert slots["_llm_scope_signals"] == ["三个月", "一个人"]  # LLM 判断存档备查

    router2 = _router(root, [json.dumps({}, ensure_ascii=False), "## 核心循环\n……"])
    evidence2 = asyncio.run(advise(root, router2, "我想一个人做个开放世界游戏"))
    slots2 = json.loads((evidence2 / "slots.json").read_text(encoding="utf-8"))
    assert slots2["scope_signals"] == ["开放世界"]           # 词表命中正常登记
