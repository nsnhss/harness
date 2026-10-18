"""题库冷启动：LLM 生成候选检查项（DESIGN.md §14.1）。

铁律：LLM 只生成草稿（status: draft），expect 答案和入库资格由用户审批
（harness review）。种子模板手写，LLM 只会模仿给定的样子——种子烂了全烂。
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..observability.trace import Tracer
from ..providers.router import Router
from .schema import CheckItem

CANDIDATES_DIR = Path("eval") / "testbank" / "candidates"

GEN_INSTRUCTION = """你是游戏开发 Harness 的出题器。围绕主题「{topic}」生成 {n} 个原子检查项。

每个检查项必须：
1. 一句话、可证伪、二元判断（对/错），禁止"整体好不好"这类整包判断
2. method 三选一：auto（可脚本客观检测）/ ai（需 AI 看证据判断）/ human（手感观感必须人判）
3. evidence 只能从【当前可用证据清单】中选取，禁止脑补不存在的证据或产物
4. 覆盖不同维度，不要全挤在一个维度

【当前可用证据清单】（顾问层 v0 场景，输入是用户的游戏想法）：
- idea.txt            用户原始想法文本
- slots.json          意图提取结果（含 _violations 违规记录）
- recommendation.md   顾问层生成的方案（Markdown，含核心循环/引擎推荐/体量评估/风险清单/里程碑）
- calls/call-*.json   模型调用留痕（完整 prompt 与响应）
注意：当前没有代码仓库、commit 记录、UI 原型、资源清单——不要假设它们存在。

严格输出 YAML 列表（不要输出任何其他文字），每项字段：target, check, method, evidence
示例：
- target: 方案明确性
  check: 方案明确给出唯一主引擎名称
  method: auto
  evidence: [recommendation.md]
"""


def next_check_ids(root: Path, n: int) -> list[str]:
    """扫描全部题库 split，分配连续的新 ID。"""
    used = set()
    for path in (root / "eval" / "testbank").rglob("TC-*.yaml"):
        m = re.match(r"TC-(\d+)", path.name)
        if m:
            used.add(int(m.group(1)))
    nxt = max(used, default=0) + 1
    return [f"TC-{nxt + i:04d}" for i in range(n)]


def parse_candidates(text: str, root: Path, *, model: str) -> list[CheckItem]:
    """解析 LLM 输出为 CheckItem 草稿：ID 重排、强制 draft、标注来源。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").removeprefix("yaml").strip()
    raw = yaml.safe_load(cleaned)
    if not isinstance(raw, list):
        raise TypeError(f"LLM 输出不是 YAML 列表，而是 {type(raw).__name__}")
    ids = next_check_ids(root, len(raw))
    items = []
    for new_id, entry in zip(ids, raw, strict=True):
        entry = dict(entry)
        entry.update(
            id=new_id,
            expect="pass",
            status="draft",
            source=f"LLM生成（{model}，待审）",
        )
        items.append(CheckItem.model_validate(entry))
    return items


def write_candidates(root: Path, items: list[CheckItem]) -> list[Path]:
    out_dir = root / CANDIDATES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for item in items:
        slug = re.sub(r"[^\w一-鿿]+", "_", item.target)[:20]
        path = out_dir / f"{item.id}_{slug}.yaml"
        path.write_text(
            yaml.safe_dump(item.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        written.append(path)
    return written


async def generate(
    root: Path, router: Router, topic: str, n: int, run_id: str = "gen"
) -> list[Path]:
    """调 LLM 生成 → 解析校验 → 写 candidates/。解析失败直接抛错（草稿阶段不设 unable）。"""
    prompt = GEN_INSTRUCTION.format(topic=topic, n=n)
    messages = [{"role": "user", "content": prompt}]
    resp = await router.chat("generator", messages)
    tracer = Tracer(root, root / "runs" / run_id)
    tracer.record(
        run_id=run_id, role="generator", model=resp.model, messages=messages,
        response=resp.content, latency_ms=resp.latency_ms,
        tokens=resp.prompt_tokens + resp.completion_tokens, retries=resp.retries,
    )
    items = parse_candidates(resp.content, root, model=resp.model)
    return write_candidates(root, items)
