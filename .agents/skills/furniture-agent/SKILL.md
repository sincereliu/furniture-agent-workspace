---
name: furniture-agent
description: 路由本仓库六阶段家具生成主流程、独立房间摆放布局与 CAD 执行工具。适用于设计意图、板件、制造/BOM、特征树、CAD/STEP、交付验证，以及按需的房间摆放预览和 Viewer 交接。
---

# 家具智能体

家具工作的薄路由入口；路径均相对仓库根目录。

做家具只读当前阶段，不提前加载下游。改 Skill 或运行时代码走「改代码」，不要把开发规范当成做柜子的步骤。

## 做家具

   - `design_intent`：`domain/skills/design-intent/SKILL.md`
   - `panel_plan`：`domain/skills/panel-plan/SKILL.md`
   - `manufacture_plan`：`domain/skills/manufacture-plan/SKILL.md`
   - `feature_tree_planned`：`domain/skills/feature-tree/SKILL.md`
   - `cad_generated`：Orchestrator tool（`run_next(..., generate_cad=True)`），实现 `domain/skills/cad-generated/TOOL.md`
   - `delivery_validated`：`domain/skills/delivery-validated/SKILL.md`

独立能力（不在上述串联阶段内）：

   - 房间摆放、碰撞检查、SVG/互动 Viewer：`domain/skills/layout-plan/SKILL.md`

讨论停在当前阶段。串联顺序由 `FurnitureOrchestrator` 管理。交互入口是 `FurnitureToolSession`（`domain/skills/cad-generated/scripts/furniture_workflow/agent_tools.py`）。已注册 `furniture_*` 的宿主按 [交互工具面](../../../domain/skills/cad-generated/references/agent-tool-contract.md) 调用；本仓库编码助手按当前阶段 Skill 提案，经同一 Orchestrator 准入。进入 `cad_generated` 必须 `run_next(..., generate_cad=True)`。不得直调特征树发射器或 `CadBridge`。没有一次性批处理入口，不得自动确认中间阶段。`plan_cabinet` / `plan_furniture` 已删除，不得另建压扁检查点的流水线。

只有用户明确要求房间摆放、靠墙/居中、门窗或障碍物碰撞、摆放图或房间 Viewer 时才调用 `layout-plan`；它不写入主流程 `STAGE_SEQUENCE`，也不是 `panel_plan` 的前置条件。

门、层板、抽屉、踢脚、背板安装（`back_mount`）和料厚从板件阶段开始，由 `panel-plan` 负责，不进意图。确认、重试、冻结与改意图的细节见工具契约和当前阶段 Skill。

`server.py` 只提供独立 `/api/plan-layout` 房间摆放；家具生成只走 Orchestrator 的确认 / `run_next` 与 `FurnitureToolSession`。有上游意图或源码时不手改派生 STEP、GLB、BOM、裁切清单或 Python。声称可执行前检查实时代码、测试和入口；缺失则如实说明。只报告实际运行过的验证和实际存在的产物。

## 改代码

创建、修改或审查家具 Skill、CAD 执行工具及其运行时代码前，读取 [AGENTS.md](../../../AGENTS.md) 和 [LLM 与运行时边界](references/llm-runtime-boundary.md)，并在完成前执行其中的边界审计。无法归入确定性代码类别的逻辑不得进入 `scripts/`。

规划阶段实现由该 Skill 的 `scripts/` 拥有，CAD 执行由 `domain/skills/cad-generated/scripts/` 拥有。`domain/skills/cad-generated/scripts/furniture_workflow/` 是唯一应用层入口。工作区目录规则见 `domain/skills/cad-generated/scripts/validate_workspace_layout.py`。

不修改 `external/text-to-cad` 或复制 `external/scientific-agent-skills` 来实现家具逻辑。

## 按需外挂

外部技能只从 `external/text-to-cad/skills/` 按需加载：家具 STEP 由 Orchestrator tool 生成；几何审查/快照用 `cad/SKILL.md`，审查/链接用 `cad-viewer/SKILL.md`，命名采购件用 `step-parts/SKILL.md`；忽略生成副本 `external/text-to-cad/plugins/cad/skills/`。

科学分析只从 `external/scientific-agent-skills/skills/` 按当前阶段按需加载，不把整个集合注册为家具技能：板件尺寸链/公差审计读 `uncertainty-and-units/SKILL.md`，板件多目标候选读 `pymoo/SKILL.md`；制造样件试验读 `experimental-design/SKILL.md`，已有试验数据读 `statistical-analysis/SKILL.md`，板件流转/工位排队读 `simpy/SKILL.md`。科学分析是 `stage_analyses` 旁路证据，不是新的检查点，也不得直接覆盖 `stage_outputs`；用户接受候选后的 Revision 改法见对应阶段 Skill。
