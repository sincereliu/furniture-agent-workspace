---
name: furniture-agent
description: 将家具工作路由到本仓库正确的本地域技能和 CAD 技能。适用于家具需求、设计意图、板件结构、BOM 或裁切清单、特征树、CAD 生成、STEP 检查、产物验证，以及 CAD Viewer 交接。
---

# 家具智能体

将本技能作为家具工作的入口。所有路径从仓库根目录解析，本入口只负责路由。

## 请求路由

1. 每个家具请求只读取当前阶段对应的明确路径，不得提前加载后续技能：
   - `design_intent`：`skills/furniture-design-intent/SKILL.md`
   - `layout_planned`：`skills/furniture-layout/SKILL.md`
   - `panels_planned`：`skills/furniture-panel-planning/SKILL.md`
   - `manufacturing_planned`：`skills/furniture-manufacturing/SKILL.md`
   - `feature_tree_planned`：`skills/furniture-feature-tree/SKILL.md`
   - `cad_generated`：`skills/furniture-cad/SKILL.md`
   - `delivery_validated`：`skills/furniture-delivery-validation/SKILL.md`
2. 讨论、设计意图、家具结构、板件拆分、BOM 或制造推理停在对应领域技能；可执行实现由各阶段 Skill 的 `scripts/` 拥有，执行顺序仍统一经过 `FurnitureOrchestrator`。
3. 从权威目录 `external/text-to-cad/skills/` 中只加载所需的最小技能：
   - CAD 生成、修改、STEP 检查、几何验证或快照：`cad/SKILL.md`。
   - 可视化审查或产物链接：`cad-viewer/SKILL.md`。
   - 有名称的可采购部件：`step-parts/SKILL.md`。
   - 只有明确请求对应输出时，才加载其他引擎技能。
4. 忽略 `external/text-to-cad/plugins/cad/skills/`，它是生成的生产副本。
5. 声称具备可执行支持前，检查实时代码、测试和入口命令；源码缺失时如实报告。
6. 执行规划或生成时统一经过 `FurnitureOrchestrator`。交互式 Agent 使用 `confirm_stage()` 和 `run_next()`：每次只确认当前阶段、执行下一个阶段、返回该阶段的 `stage_outputs`，然后停止并等待用户确认“继续”。不得使用 `execute_spec()` 绕过交互阶段确认；不得从 Agent 直接调用 `plan_cabinet()`、特征树发射器或 `CadBridge` 拼装第二条流水线。
7. 用户修改设计意图时使用 `revise()` 从第 1 阶段创建新 Revision；用户修改布局、板件、制造策略或特征树时使用 `revise_stage_output()`。新 Revision 只继承被修改阶段之前已确认的输出，被修改阶段及全部下游必须重新确认或生成。
8. 只有明确的一次性批处理请求才调用 `skills/furniture-cad/scripts/generate_furniture.py` 或 `execute_spec()`；API 入口 `skills/furniture-cad/scripts/server.py` 同样只做协议适配，执行仍由 Orchestrator 负责。

## 边界

- 以已确认的家具意图为事实来源。
- 七个本地技能与七个检查点一一对应，每个 Skill 拥有本阶段运行时代码；`skills/furniture-cad/scripts/furniture_workflow/` 中的 Orchestrator 是唯一应用层执行入口。
- CLI、API 与 Agent 只是协议入口，执行顺序、意图确认、状态、验证和产物谱系统一归 `FurnitureOrchestrator`。
- 七个阶段都是用户可见的检查点。交互工作不得在同一轮越过多个未确认阶段；生成 CAD 前必须已确认设计意图、布局规划、板件规划、制造策略和特征树。
- 可复用脚本和运行时模块放在所属阶段 Skill 的 `scripts/`；跨阶段入口与集成测试放在 `skills/furniture-cad/scripts/`；一次性脚本放在 `temp/`。
- 禁止创建根级 `scripts/`、`packages/`、`tests/`、`scratch/` 或 `tmp/` 代码树；禁止把生成源码写入 `generated/`。
- 代码布局变更后运行 `skills/furniture-cad/scripts/validate_workspace_layout.py` 并修复全部违规项。
- 不得通过修改 `external/text-to-cad` 实现家具领域行为。
- 存在上游意图或源文件时，不得手工修改派生 STEP、GLB、BOM、裁切清单或生成的 Python。
- 不要加载整棵外部技能树，只选择最小相关集合。
- 只报告实际运行过的验证和实际存在的产物。
