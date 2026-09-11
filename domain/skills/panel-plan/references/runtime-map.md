# 运行时映射（板件阶段）

核对实现或规划演进时再读；提案字段以 [提案契约](panel-proposal-contract.md) 为准。

## 入口

- `panel_pipeline.py::plan_panel_stage()`：交互主流程入口，一意图一台柜。
- `plan_panel_cabinets()`：多柜组合；`cabinet_id` 在准入 `FurnitureSpec` 前弹出。
- Orchestrator 从 `revision.stage_inputs.panels.parameters` 取提案。首次生成先写入该对象再 `run_next()`，或 `retry_stage("panels_planned", stage_input={"parameters": ...})`。

## 交接

下游（制造、旁路分析、`revise_stage_output`）只通过 `cabinets_from_output()` / `require_primary_handoff()` 读板件结果。检查点只有 `cabinets[]`；交互主流程取第一台柜的 `spec` 与 `panels`。顶层不得再写 `spec/structure/panels/cabinet_id`。

确认后的板件冻成 `store/<project-id>/panels/<sha256>.json`，Revision 记下 `confirmed_panel_sha256`。有 Project Store 时，制造、板件旁路分析、CAD 板件快照和交付哈希按该哈希读冻结文件，文件缺失则失败；未确认、旧项目没有该哈希、或没有 Store 时仍读内存中的 `stage_outputs.panels_planned`。不重跑 `plan_panel_stage()`。

## 模块

| 模块 | 职责 | 边界理由 |
| --- | --- | --- |
| `panel_spec.py` | schema、完整性、客观冲突、`back_mount=auto` 解析 | schema / validation / calculation |
| `structure_planning.py` | 精确净空与柜体区域 | calculation |
| `panel_rules.py` | 踢脚支撑数量、背拉条数量与净距 | calculation |
| `construction_geometry.py` | 层板/抽屉/踢脚/背拉条盒子 | calculation |
| `topology_solver.py` | 读柜型 YAML，物化板件位置与语义面 | calculation |
| `joint_topology.py` | 接触几何；不解析连不连 | calculation |
| `validation.py` | 检查点不变量 | validation |
| `quantitative_audit.py` / `design_optimization.py` | 旁路分析 | 只写 `stage_analyses` |

## 历史兼容（不参与新提案决策）

- `FurnitureSpec.from_dict()` 恢复 `type` / `furniture_type`，丢弃旧 `movable_shelf_connector` / `door_hinge_side`。
- 新提案路径仍接受 `door_margin` → `front_face_margin`（扁平协议与历史夹具）；规范名是 `front_face_margin`。
- `CabinetStructure.from_dict()` 把历史 `door_count` 收成 `n_doors`。

连不连默认规则在制造 [连接与接触默认规则](../manufacture_plan/references/connection-contact-defaults.md)。
