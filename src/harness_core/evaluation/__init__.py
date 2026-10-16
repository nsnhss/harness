"""Eval 层（DESIGN.md §8-§11、§23-§24）。

- 原子检查项加载与校验（YAML，sha256 数据集哈希；golden 目录加载器层面强制只读）
- 三分割：dev / golden / canary
- 判定输出契约：pass / fail / unable（pydantic 强校验）
- 不一致归因四分类、失败四级分级（L1 工程 / L2 证据 / L3 判定 / L4 提取）
- replay 单案例回放、regress 黄金集回归、一致率统计
"""
