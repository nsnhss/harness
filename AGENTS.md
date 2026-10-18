# AGENTS.md — 项目铁律（每次会话必读）

## 项目是什么

游戏开发 Harness：AI 辅助游戏设计、开发、检测的工作台。设计依据见 `docs/DESIGN.md`，架构级改动必须先改 DESIGN.md 再动代码。

## 环境铁律（最高优先级）

1. **禁止往 C 盘安装/写入任何大体积内容**。C 盘仅剩 12GB，本项目 C 盘预算 ≤ 1GB
2. Python 环境用 uv 管理，虚拟环境在项目内 `D:\harness\.venv`
3. 所有缓存指向 D 盘：`UV_CACHE_DIR`、`PIP_CACHE_DIR`、`HF_HOME`、`OLLAMA_MODELS` → `D:\dev\` 下
4. 不装 Docker Desktop；万不得已时装完必须把 WSL 虚拟磁盘迁到 D 盘

## 架构铁律

1. **状态落盘**：任何重要状态不得只存在于对话历史中。会话状态、运行记录、判定结果全部写文件
2. **资产纯文本**：规则库/题库/案例库/prompt 全部为 Markdown/YAML/JSON，可 git diff
3. **规则只增不改不删**：废弃规则标记 `deprecated`，保留出处
4. **黄金集只读**：`eval/testbank/golden/` 下的文件任何代码路径都不得写入
5. **二元判断**：eval 输出只有 `pass / fail / unable`，禁止引入评分/评级
6. **期望答案人定**：LLM 可生成测试用例草稿，期望答案必须用户确认后才激活
7. **证据强制**：AI 判定必须引用证据（文件指针），无证据的判定无效

## 目录结构

```
docs/            设计文档（DESIGN.md 为最高依据）
config/          模型路由表、槽位 schema 等配置
rules/           规则库（CC BY-NC，核心资产）
knowledge/       引擎知识库（版本化，存结论附来源）
cases/           案例库（每次使用的完整记录）
game_analysis/   相近游戏拆解库（七维模板）
eval/testbank/   题库：dev/ 日常、golden/ 冻结、canary/ 诱饵
prompts/         版本化 prompt（<role>/vN.md）
runs/            运行记录（本地产物，gitignore）
advise/          顾问咨询产物（本地产物，gitignore）
consult_sessions/ 顾问会话状态（本地产物，gitignore）
src/harness_core/ 框架代码（MIT）
scripts/         自动化脚本
```

## 协议

- `src/`、`scripts/`、`config/`：MIT（见 LICENSE）
- `rules/`、`knowledge/`、`cases/`、`game_analysis/`、`eval/testbank/`：CC BY-NC 4.0（见 docs/DATA_LICENSE.md）
