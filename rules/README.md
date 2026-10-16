# 规则库

每条规则一个文件，格式：

```yaml
id: RULE-0001
rule: 一句话规则（可执行、可检验）
scope: [advisor | executor | judge]   # 作用于哪层
source:
  case_id: CS-xxx        # 出处案例（铁律：必带出处）
  quote: "用户原话"
created: 2026-10-15
status: active           # active / deprecated（只增不改不删）
recurrence: 2            # 同类反馈出现次数（<2 且无显式确认不得 active）
```

入库闸门（DESIGN.md §12）：
1. 必带出处（案例 ID + 用户原话）
2. 同类反馈 ≥2 次，或用户显式说"入库"
3. 新规则先对历史案例回归，不破坏过去判 ✓ 的结果
