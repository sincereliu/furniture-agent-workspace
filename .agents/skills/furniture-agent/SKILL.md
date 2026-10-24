---
name: furniture-agent
description: 路由本仓库六阶段家具生成主流程与 CAD 执行工具。适用于房间布局、板件、制造/BOM、特征树、CAD/STEP、交付验证。
---

# 家具智能体

家具工作的薄路由入口；`domain/`、`external/` 开头的代码路径相对仓库根目录，Markdown 链接相对当前文件。做家具时打开正在做的那一阶段。当前检查点已确认且客户要继续，或当前技能的下一步写了下一阶段的文件时，再打开那一个文件。不要为了预备一次打开后面各阶段。改 Skill 或运行时代码走「改代码」；结构审查按用户指定范围读取，不受做家具时的推进顺序限制。

## 做家具

- `layout_plan`：`domain/stages/layout-plan/SKILL.md`
- `panel_plan`：`domain/stages/panel-plan/SKILL.md`
- `manufacture_plan`：`domain/stages/manufacture-plan/SKILL.md`
- `feature_tree_planned`：`domain/stages/feature-tree/SKILL.md`
- `cad_generated`：`domain/stages/cad-generated/TOOL.md`（`run_next(..., generate_cad=True)`）
- `delivery_validated`：`domain/stages/delivery-validated/SKILL.md`

确认、重试、冻结见 [交互工具面](../../../domain/stages/cad-generated/references/agent-tool-contract.md)。柜门、层板、抽屉、踢脚、背板、料厚归 `panel-plan`。房间门窗归 `layout-plan` 的 `openings[]`。

宿主调用使用交互工具面实际注册的 `furniture_*` 名称，按快照的 `allowed_tools` / `required_tool` 推进。阶段文档中的 `stage_inputs` 是项目保存结构，调用工具时使用 `stage_input`。`revise_stage_output()` 等 Python 方法不是已注册工具，需要直接调用 Python API 时才使用，不自行加上 `furniture_` 前缀。

## 改代码

搜索范围、阶段地图、阶段 Skill 的修改范围，以及何时读边界文档，见 [AGENTS.md](../../../AGENTS.md)。新增或搬移 `scripts/` 中的分支、映射、默认值或解析器前，读取 [LLM 与运行时边界](references/llm-runtime-boundary.md) 并做边界审计。无法归入确定性代码类别的逻辑不得进入 `scripts/`。

规划阶段实现由该 Skill 的 `scripts/` 拥有；CAD 与 Orchestrator 在 `domain/stages/cad-generated/scripts/`。不修改 `external/text-to-cad`，不复制 `external/scientific-agent-skills`。本机 `.venv` 对齐 cadgen pin： [开发环境](references/dev-environment.md)。

共享包、工作流、接入层和跨阶段测试的具体归属见 [模块导航](../../../domain/stages/cad-generated/references/module-map.md)。阶段间只引用所有者的契约；修改交接语义时按 AGENTS.md 列出跨阶段范围。`agents/openai.yaml` 只作入口提示，业务规则留在阶段 Skill 与契约。

## 按需外挂

CAD 审查从 `external/text-to-cad/skills/` 按需读 `cad/SKILL.md`、`cad-viewer/SKILL.md`、`step-parts/SKILL.md`。科学分析从 `external/scientific-agent-skills/skills/` 按需读，链接与适配器归对应阶段 Skill；写入 `stage_analyses`，不覆盖 `stage_outputs`。
