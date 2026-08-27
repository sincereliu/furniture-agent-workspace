---
name: furniture-agent
description: 路由本仓库六阶段家具生成主流程、独立房间摆放布局与所需 CAD 技能。适用于设计意图、板件、制造/BOM、特征树、CAD/STEP、交付验证，以及按需的房间摆放预览和 Viewer 交接。
---

# 家具智能体

家具工作的薄路由入口；路径均相对仓库根目录。

## 路由

家具生成主流程只读取当前阶段，不提前加载下游：

   - `design_intent`：`domain/skills/furniture-design-intent/SKILL.md`
   - `panels_planned`：`domain/skills/furniture-panel-planning/SKILL.md`
   - `manufacturing_planned`：`domain/skills/furniture-manufacturing/SKILL.md`
   - `feature_tree_planned`：`domain/skills/furniture-feature-tree/SKILL.md`
   - `cad_generated`：`domain/skills/furniture-cad/SKILL.md`
   - `delivery_validated`：`domain/skills/furniture-delivery-validation/SKILL.md`

独立能力（不在上述串联阶段内）：

   - 房间摆放、碰撞检查、SVG/互动 Viewer：`domain/skills/furniture-layout/SKILL.md`

规则：

- 创建、修改或审查家具 Skill 及其运行时代码前，必须读取 [LLM 与运行时边界](references/llm-runtime-boundary.md)，并在完成前执行其中的边界审计；无法归入确定性代码类别的逻辑不得进入 `scripts/`。
- 讨论或推理停在所属阶段；实现由该 Skill 的 `scripts/` 拥有，串联阶段顺序统一由 `FurnitureOrchestrator` 管理。
- 交互式家具生成 Agent 只用 `confirm_stage()`、`run_next()`：确认当前阶段、生成下一阶段、展示其 `stage_outputs`，然后等待“继续”。不得用 `execute_spec()` 越过确认；不得从 Agent 直接调用 `plan_cabinet()`、特征树发射器或 `CadBridge` 另建流水线。
- 修改设计意图用 `revise()`；修改 `panels_planned`、`manufacturing_planned` 或 `feature_tree_planned` 用 `revise_stage_output()`。新 Revision 只继承修改点之前的已确认输出；修改阶段及下游重新确认/生成。
- 只有用户明确要求房间摆放、靠墙/居中、门窗或障碍物碰撞、摆放图或房间 Viewer 时才调用 `furniture-layout`；它不写入主流程 `STAGE_SEQUENCE`，也不是 `panels_planned` 的前置条件。
- `shelf_count/n_doors` 属于板件规划输入；`back_mount` 也从板件阶段开始。板件阶段首次物化这些家具本体与结构规格、解析有效背板模式并生成背板/背拉条；制造阶段只消费已确认板件方案，生成封边、连接、BOM 和孔位。意图和独立房间布局不得提前携带或解析背板结构。
- 外部技能只从 `external/text-to-cad/skills/` 按需加载：CAD/STEP/几何/快照用 `cad/SKILL.md`，审查/链接用 `cad-viewer/SKILL.md`，命名采购件用 `step-parts/SKILL.md`；忽略生成副本 `external/text-to-cad/plugins/cad/skills/`。
- 科学分析只从 `external/scientific-agent-skills/skills/` 按当前阶段按需加载，不把整个集合注册为家具技能：板件尺寸链/公差审计读 `uncertainty-and-units/SKILL.md`，板件多目标候选读 `pymoo/SKILL.md`；制造样件试验读 `experimental-design/SKILL.md`，已有试验数据读 `statistical-analysis/SKILL.md`，板件流转/工位排队读 `simpy/SKILL.md`。
- 科学分析是 `stage_analyses` 旁路证据，不是新的检查点，也不得直接覆盖 `stage_outputs`。候选方案经用户接受后，按字段所有者调用 `revise()` 或 `revise_stage_output()` 建立新 Revision，再重新确认受影响阶段及下游。
- 仅明确的一次性家具生成批处理可用 `domain/skills/furniture-cad/scripts/generate_furniture.py` 或 `execute_spec()`；`server.py` 的家具生成端点只适配协议并调用 Orchestrator，独立 `/api/plan-layout` 端点调用 `furniture-layout` 自有运行时。
- 声称可执行前检查实时代码、测试和入口；缺失则如实说明。

## 边界

- 已确认意图只定义家具类别和成品外包络；板件结构和制造方案分别以各自已确认的阶段输出为事实来源。六个串联 Skill 对应六个用户可见检查点，生成 CAD 前须确认 `design_intent`、`panels_planned`、`manufacturing_planned` 与 `feature_tree_planned`。房间布局是独立结果，不参与交付检查点谱系。
- `domain/skills/furniture-cad/scripts/furniture_workflow/` 是唯一应用层入口；CLI/API/Agent 仅适配协议。阶段规则归各 Skill，Orchestrator 只编排、记录状态/验证/产物谱系。
- 可复用脚本和运行时模块放在所属阶段 Skill 的 `scripts/`；跨阶段入口与集成测试放在 `domain/skills/furniture-cad/scripts/`。一次性检查、迁移、调试和实验统一放在已忽略的 `temp/<project-slug>/`，每个项目或任务独占一个目录，使脚本与派生产物可按目录整体识别和删除；任务结束即清理。生成 CAD 源码使用保留路径 `temp/cad-source/<artifact-name>/`。
- 禁止根级 `scripts/`、`packages/`、`tests/`、`scratch/`、`tmp/`；生成源码不得进入 `generated/`。工作区目录变更后运行 `domain/skills/furniture-cad/scripts/validate_workspace_layout.py` 并清零违规。
- 不修改 `external/text-to-cad` 实现家具逻辑；有上游意图/源码时不手改派生 STEP、GLB、BOM、裁切清单或 Python。
- 不修改或复制 `external/scientific-agent-skills` 来实现家具逻辑；家具输入适配、结果约束和可复用执行代码归对应家具阶段的 `scripts/`。科学技能缺少可选依赖时必须报告 `unavailable` 或使用明确标注的有界回退，不得伪装成已运行上游引擎。
- 只报告实际运行过的验证和实际存在的产物。
