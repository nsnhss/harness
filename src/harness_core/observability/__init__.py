"""观测与追踪（DESIGN.md §19）。

每次模型调用记 JSONL（trace_id、角色、实际模型、prompt 哈希+原文、响应、
耗时、token、重试、成本），SQLite 建索引供统计查询。
三层查看：report（汇总）→ show（单案例）→ call（单调用原文）。
"""
