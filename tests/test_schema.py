"""判定输出契约测试（DESIGN.md §8、§20）。"""

import pytest
from pydantic import ValidationError

from harness_core.evaluation.schema import CheckItem, JudgeResult, Verdict


def test_verdict_is_binary_plus_unable():
    assert {v.value for v in Verdict} == {"pass", "fail", "unable"}


def test_judge_result_rejects_rating():
    # 禁止评级：score/grade 等字段不存在，verdict 不接受枚举外值
    with pytest.raises(ValidationError):
        JudgeResult.model_validate({"verdict": "3分", "evidence_refs": [], "reason": "x"})


def test_check_item_method_enum():
    item = CheckItem.model_validate({
        "id": "TC-9001", "target": "t", "check": "c", "method": "auto",
    })
    assert item.expect == Verdict.PASS
    with pytest.raises(ValidationError):
        CheckItem.model_validate({"id": "TC-9002", "target": "t", "check": "c",
                                  "method": "vibe"})
