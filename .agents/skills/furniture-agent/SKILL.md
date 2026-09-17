---
name: furniture-agent
description: 路由本仓库六阶段家具生成主流程与 CAD 执行工具。适用于房间布局、板件、制造/BOM、特征树、CAD/STEP、交付验证。
---

# 家具智能体

家具工作的薄路由入口；路径均相对仓库根目录。做家具只读当前阶段，不提前加载下游。改 Skill 或运行时代码走「改代码」。

## 做家具

- `layout_plan`：`domain/skills/layout-plan/SKILL.md`
- `panel_plan`：`domain/skills/panel-plan/SKILL.md`
- `manufacture_plan`：`domain/skills/manufacture-plan/SKILL.md`
- `feature_tree_planned`：`domain/skills/feature-tree/SKILL.md`
- `cad_generated`：`domain/skills/cad-generated/TOOL.md`（`run_next(..., generate_cad=True)`）
- `delivery_validated`：`domain/skills/delivery-validated/SKILL.md`

确认、重试、冻结见 [交互工具面](../../../domain/skills/cad-generated/references/agent-tool-contract.md)。门、层板、抽屉、踢脚、背板、料厚归 `panel-plan`。

## 改代码

搜索范围、阶段地图、以及何时读边界文档，见 [AGENTS.md](../../../AGENTS.md)。新增或搬移 `scripts/` 中的分支、映射、默认值或解析器前，读取 [LLM 与运行时边界](references/llm-runtime-boundary.md) 并做边界审计。无法归入确定性代码类别的逻辑不得进入 `scripts/`。

规划阶段实现由该 Skill 的 `scripts/` 拥有；CAD 与 Orchestrator 在 `domain/skills/cad-generated/scripts/`。不修改 `external/text-to-cad`，不复制 `external/scientific-agent-skills`。

## 按需外挂

CAD 审查从 `external/text-to-cad/skills/` 按需读 `cad/SKILL.md`、`cad-viewer/SKILL.md`、`step-parts/SKILL.md`。科学分析从 `external/scientific-agent-skills/skills/` 按需读，链接与适配器归对应阶段 Skill；写入 `stage_analyses`，不覆盖 `stage_outputs`。
