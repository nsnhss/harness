"""顾问层 v0：单次咨询，真实调 LLM，产物落盘为 eval 证据（DESIGN.md §6、§22）。

流程：idea → extractor 提取槽位（JSON）→ advisor 出方案（Markdown）
     → idea.txt / slots.json / recommendation.md 写入 advise/<ts>/evidence/
产物目录可直接作为 `harness run --evidence <dir>` 的输入，供 A 类题库判定。

v0 省略：多轮追问、决策表匹配（阶段 2 补齐）。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

from ..observability.trace import Tracer
from ..providers.router import Router

SLOT_KEYS = [
    "game_type", "dimension", "perspective", "platform", "team_size",
    "skill_code", "skill_art", "timeline_days", "budget", "monetization",
    "reference_games", "core_loop", "scope_signals",
]


def _load_prompt(root: Path, role: str, version: str = "v1") -> str:
    return (root / "prompts" / role / f"{version}.md").read_text(encoding="utf-8")


def _load_slots_schema(root: Path) -> dict:
    return yaml.safe_load((root / "config" / "slots_schema.yaml").read_text(encoding="utf-8"))


def _enum_constraints_text(schema: dict) -> str:
    """从 schema 生成枚举约束表，注入 prompt（单一事实来源在 config）。"""
    lines = []
    for key, spec in schema.get("slots", {}).items():
        if spec.get("type") in ("enum", "multi_enum"):
            lines.append(f"- {key}: {spec['values']}")
    return "\n".join(lines)


def _coerce_slots(data: dict, schema: dict) -> tuple[dict, list[str]]:
    """校验层（DESIGN.md §22）：枚举越界值置 null 并记违规，双保险。"""
    violations = []
    slots_def = schema.get("slots", {})
    out = {}
    for k in SLOT_KEYS:
        v = data.get(k)
        spec = slots_def.get(k, {})
        if v is not None and spec.get("type") == "enum" and v not in spec.get("values", []):
            violations.append(f"{k}: '{v}' 不在枚举内，已置 null")
            v = None
        out[k] = v
    return out, violations


def _match_scope_signals(idea: str, schema: dict) -> list[str]:
    """危险信号词表匹配（DESIGN.md §21.2：必须稳定可回归，不用 LLM 判断）。"""
    words = schema.get("scope_signal_words", [])
    return [w for w in words if w in idea]


def _load_active_rules(root: Path) -> str:
    lines = []
    for path in sorted((root / "rules").glob("RULE-*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("status") == "active":
            lines.append(f"- {data['id']}: {data['rule']}")
    return "\n".join(lines) or "（规则库为空）"


def _load_game_index(root: Path) -> str:
    lines = []
    for path in sorted((root / "game_analysis").glob("GA-*.md")):
        lines.append(f"- {path.stem}")
    return "\n".join(lines) or "（拆解库为空）"


def _parse_slots(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("json").strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise TypeError("extractor 输出不是 JSON 对象")
    return {k: data.get(k) for k in SLOT_KEYS}


async def advise(root: Path, router: Router, idea: str) -> Path:
    """单次咨询。返回证据目录路径。"""
    ts = time.strftime("%Y-%m-%d_%H%M%S")
    evidence_dir = root / "advise" / ts / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "idea.txt").write_text(idea, encoding="utf-8")
    tracer = Tracer(root, root / "advise" / ts)

    # 1. extractor：想法 → 槽位 JSON（prompt v2 + 枚举约束注入）
    schema = _load_slots_schema(root)
    extract_msgs = [
        {"role": "system", "content": _load_prompt(root, "extractor", "v2")},
        {"role": "user", "content":
            "槽位键：\n" + "\n".join(SLOT_KEYS)
            + "\n\n枚举约束表：\n" + _enum_constraints_text(schema)
            + "\n\n用户想法：\n" + idea},
    ]
    resp = await router.chat("extractor", extract_msgs)
    tracer.record(run_id=f"advise-{ts}", role="extractor", model=resp.model,
                  messages=extract_msgs, response=resp.content,
                  latency_ms=resp.latency_ms,
                  tokens=resp.prompt_tokens + resp.completion_tokens,
                  retries=resp.retries)
    try:
        raw_slots = _parse_slots(resp.content)
    except (json.JSONDecodeError, TypeError) as e:
        raw_slots = {}
        parse_error = str(e)
    else:
        parse_error = None

    # 校验层：枚举越界置 null + 危险信号词表匹配（LLM 语义判断仅存档）
    slots, violations = _coerce_slots(raw_slots, schema)
    slots["scope_signals"] = _match_scope_signals(idea, schema)
    if parse_error:
        slots["_extract_error"] = parse_error
    if violations:
        slots["_violations"] = violations
    if raw_slots.get("scope_signals"):
        slots["_llm_scope_signals"] = raw_slots["scope_signals"]  # 存档，不采用
    (evidence_dir / "slots.json").write_text(
        json.dumps(slots, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. advisor：槽位 + 规则库 + 拆解库索引 → 方案
    advise_msgs = [
        {"role": "system", "content": _load_prompt(root, "advisor")},
        {"role": "user", "content":
            f"用户想法：\n{idea}\n\n提取槽位：\n```json\n"
            f"{json.dumps(slots, ensure_ascii=False, indent=2)}\n```\n\n"
            f"可用规则库：\n{_load_active_rules(root)}\n\n"
            f"可用拆解库：\n{_load_game_index(root)}"},
    ]
    resp2 = await router.chat("advisor", advise_msgs)
    tracer.record(run_id=f"advise-{ts}", role="advisor", model=resp2.model,
                  messages=advise_msgs, response=resp2.content,
                  latency_ms=resp2.latency_ms,
                  tokens=resp2.prompt_tokens + resp2.completion_tokens,
                  retries=resp2.retries)
    (evidence_dir / "recommendation.md").write_text(resp2.content, encoding="utf-8")
    return evidence_dir
