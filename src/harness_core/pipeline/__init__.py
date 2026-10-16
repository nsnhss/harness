"""执行与编排（DESIGN.md §18）。

五阶段流水线：collect → auto-check → ai-judge → human-gate → distill。
每阶段落盘 runs/<run_id>/stage_*.json，可断点续跑。asyncio 编排，不上重型 DAG 框架。
"""
