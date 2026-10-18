"""题库冷启动测试：LLM 出题解析 + 审批流转（DESIGN.md §14.1）。"""

import yaml
from tests.conftest import scaffold_root

from harness_core.evaluation.generate import next_check_ids, parse_candidates
from harness_core.evaluation.loader import load_split
from harness_core.evaluation.review import approve, list_drafts, reject

SAMPLE_LLM_OUTPUT = """
```yaml
- target: 帧率稳定性
  check: 目标场景运行 5 分钟平均帧率不低于 60fps
  method: ai
  evidence: [fps_log]
- target: 新手引导
  check: 首次启动游戏 3 分钟内出现操作引导
  method: human
  evidence: [screen_recording]
```
"""


def test_parse_candidates_forces_draft(tmp_path):
    root = scaffold_root(tmp_path)
    expected_ids = next_check_ids(root, 2)  # 动态取，不硬编码（题库在增长）
    items = parse_candidates(SAMPLE_LLM_OUTPUT, root, model="mock/deepseek-chat")
    assert len(items) == 2
    assert [i.id for i in items] == expected_ids
    # 铁律：一律 draft + 标注待审，expect 由人审前默认 pass
    for item in items:
        assert item.status == "draft"
        assert "待审" in item.source
        assert item.expect.value == "pass"


def test_next_ids_scans_all_splits(tmp_path):
    root = scaffold_root(tmp_path)
    ids = next_check_ids(root, 3)
    assert len(ids) == 3
    assert int(ids[0].split("-")[1]) + 1 == int(ids[1].split("-")[1])  # 连续递增


def test_approve_moves_to_dev(tmp_path):
    root = scaffold_root(tmp_path)
    cand = root / "eval" / "testbank" / "candidates"
    cand.mkdir(parents=True, exist_ok=True)
    (cand / "TC-0003_帧率.yaml").write_text(yaml.safe_dump({
        "id": "TC-0003", "target": "帧率", "check": "平均帧率不低于60",
        "method": "ai", "evidence": ["fps_log"], "expect": "pass",
        "status": "draft", "source": "LLM生成（mock，待审）",
    }, allow_unicode=True), encoding="utf-8")

    drafts = list_drafts(root)
    assert len(drafts) == 1
    dest = approve(root, drafts[0])
    assert dest.parent.name == "dev"
    # 激活后可被 run 加载
    assert "TC-0003" in load_split(root, "dev").items
    assert not list_drafts(root)  # 不再出现在待审


def test_reject_keeps_archive(tmp_path):
    root = scaffold_root(tmp_path)
    cand = root / "eval" / "testbank" / "candidates"
    cand.mkdir(parents=True, exist_ok=True)
    path = cand / "TC-0004_模糊项.yaml"
    path.write_text(yaml.safe_dump({
        "id": "TC-0004", "target": "整体", "check": "游戏好玩",
        "method": "human", "evidence": [], "expect": "pass",
        "status": "draft", "source": "LLM生成（mock，待审）",
    }, allow_unicode=True), encoding="utf-8")

    reject(root, path, "不可证伪，违反原子性")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["status"] == "rejected"  # 只增不删：拒绝也留档
    assert "不可证伪" in data["review_note"]
    assert not list_drafts(root)
