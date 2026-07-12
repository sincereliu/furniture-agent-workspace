# 家具技能运行时

这是 `furniture-cad` 技能的私有运行时包。把它放在技能旁边，可以避免将同一工作流拆散到根目录的 `packages/`、`scripts/` 和 `tests/` 中：

1. `design_*` —— 设计意图与可执行尺寸。
2. `layout_*` —— 布局规划与柜体定位。
3. `panel_*` —— 板件语义与生产记录。
4. `manufacturing_*` —— 封边、钻孔、五金和 BOM 策略。
5. `feature_tree_*` —— 特征树构建与 CAD 源码发射。
6. `cad_bridge.py` —— 调用并验证外部 STEP 生成。
7. `workflow_*` —— 编排、修订、验证和产物谱系。

`workflow_orchestrator.py` 是唯一应用层入口，CLI、API 与 Agent 都通过它执行。它把七个阶段记录在 Revision 的 `stage_outputs` 和 `approved_stages` 中：`confirm_stage()` 确认当前阶段，`run_next()` 只执行下一阶段，`run_until()` 默认停在第一个未确认阶段，`revise_stage_output()` 从修改点建立新 Revision 并使下游失效。`planner.py` 和 `layout_pipeline.py` 是无状态领域规划门面，不是独立应用入口；特征树发射器和 `cad_bridge.py` 由 Orchestrator 按统一顺序调用。
