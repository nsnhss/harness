# Game Dev Harness

AI 辅助游戏开发工作台：设计顾问 → 开发辅助 → 二元判定检测（Eval）→ 失败沉淀进化。

- **聚焦引擎**：Unity（优先），后期移植 Unreal
- **Eval 哲学**：要么对要么错，不评级；前期 AI 判 + 人判双轨对齐，后期 AI 独立判
- **核心资产**：数据层沉淀的规则库、题库、案例库、游戏拆解库（模型可换，判断标准永存）

## 文档

- 设计总纲：[docs/DESIGN.md](docs/DESIGN.md)（最高设计依据）
- 协作铁律：[AGENTS.md](AGENTS.md)
- 数据层协议：[docs/DATA_LICENSE.md](docs/DATA_LICENSE.md)

## 状态

🏗️ 骨架阶段。路线图见 DESIGN.md §27。

## License

- 框架代码（`src/`、`scripts/`、`config/`）：MIT，见 [LICENSE](LICENSE)
- 数据资产（`rules/`、`knowledge/`、`cases/`、`game_analysis/`、`eval/testbank/`）：CC BY-NC 4.0
