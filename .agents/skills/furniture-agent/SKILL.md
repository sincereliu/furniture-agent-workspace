---
name: furniture-agent
description: 路由本仓库七阶段家具工作与所需 CAD 技能。适用于设计意图、布局、板件、制造/BOM、特征树、CAD/STEP、交付验证和 Viewer 交接。
---

# 家具智能体

家具工作的薄路由入口；路径均相对仓库根目录。

## 路由

只读取当前阶段，不提前加载下游：

   - `design_intent`：`skills/furniture-design-intent/SKILL.md`
   - `layout_planned`：`skills/furniture-layout/SKILL.md`
   - `panels_planned`：`skills/furniture-panel-planning/SKILL.md`
   - `manufacturing_planned`：`skills/furniture-manufacturing/SKILL.md`
   - `feature_tree_planned`：`skills/furniture-feature-tree/SKILL.md`
   - `cad_generated`：`skills/furniture-cad/SKILL.md`
   - `delivery_validated`：`skills/furniture-delivery-validation/SKILL.md`

规则：

- 讨论或推理停在所属阶段；实现由该 Skill 的 `scripts/` 拥有，顺序统一由 `FurnitureOrchestrator` 管理。
- 交互式 Agent 只用 `confirm_stage()`、`run_next()`：确认当前阶段、生成下一阶段、展示其 `stage_outputs`，然后等待“继续”。不得用 `execute_spec()` 越过确认；不得从 Agent 直接调用 `plan_cabinet()`、特征树发射器或 `CadBridge` 另建流水线。
- 修改设计意图用 `revise()`；修改第 2～5 阶段用 `revise_stage_output()`。新 Revision 只继承修改点之前的已确认输出；修改阶段及下游重新确认/生成。
- `back_mount` 从板件阶段开始：板件阶段首次物化结构规格、解析有效模式并生成背板/背拉条；制造阶段只消费已确认板件方案，生成封边、连接、BOM 和孔位。意图和布局不得提前携带或解析背板结构。
- 外部技能只从 `external/text-to-cad/skills/` 按需加载：CAD/STEP/几何/快照用 `cad/SKILL.md`，审查/链接用 `cad-viewer/SKILL.md`，命名采购件用 `step-parts/SKILL.md`；忽略生成副本 `external/text-to-cad/plugins/cad/skills/`。
- 仅明确的一次性批处理可用 `skills/furniture-cad/scripts/generate_furniture.py` 或 `execute_spec()`；`server.py` 只适配协议，仍调用 Orchestrator。
- 声称可执行前检查实时代码、测试和入口；缺失则如实说明。

## 边界

- 已确认意图只定义家具类别和成品外包络；布局、板件结构和制造方案分别以各自已确认的阶段输出为事实来源。七个 Skill 对应七个用户可见检查点，生成 CAD 前须确认前五阶段。
- `skills/furniture-cad/scripts/furniture_workflow/` 是唯一应用层入口；CLI/API/Agent 仅适配协议。阶段规则归各 Skill，Orchestrator 只编排、记录状态/验证/产物谱系。
- 可复用脚本和运行时模块放在所属阶段 Skill 的 `scripts/`；跨阶段入口与集成测试放在 `skills/furniture-cad/scripts/`。一次性检查、迁移、调试和实验统一放在已忽略的 `temp/<project-slug>/`，每个项目或任务独占一个目录，使脚本与派生产物可按目录整体识别和删除；任务结束即清理。生成 CAD 源码使用保留路径 `temp/cad-source/<artifact-name>/`。
- 禁止根级 `scripts/`、`packages/`、`tests/`、`scratch/`、`tmp/`；生成源码不得进入 `generated/`。布局变更后运行 `skills/furniture-cad/scripts/validate_workspace_layout.py` 并清零违规。
- 不修改 `external/text-to-cad` 实现家具逻辑；有上游意图/源码时不手改派生 STEP、GLB、BOM、裁切清单或 Python。
- 只报告实际运行过的验证和实际存在的产物。
