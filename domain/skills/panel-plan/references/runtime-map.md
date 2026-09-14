# 运行时映射（板件阶段）

核对实现或规划演进时再读；提案字段以 [提案契约](panel-proposal-contract.md) 为准。

## 入口

- `panel_pipeline.py::plan_panel_stage()`：交互主流程入口，一意图一台柜。
- `plan_panel_cabinets()`：多柜组合。
- Orchestrator 从 `revision.stage_inputs.panels.parameters` 取提案。首次生成先写入该对象再 `run_next()`，或 `retry_stage("panel_plan", stage_input={"parameters": ...})`。

## 交接

下游（制造、旁路分析、`revise_stage_output`）只通过 `cabinets_from_output()` / `require_primary_handoff()` 读板件结果。检查点只有 `cabinets[]`。每台柜带 `id` 和 `spec/interior/back_mount_resolution/assemblies`，不得在柜级再抄 `panels` 或 `structure`。

- `interior.cavity`：内腔宽高深和角点；`interior.zones`：前开口分区。
- `assemblies`：`carcass`、可选 `base`、`fronts`、`drawers[]`。板件和接触只写在所属子装配内。
- 板件：`parent_id`（柜体）、`assembly_id`（子装配）、`role`（如 `left_side_panel`）；全局 `id` 为 `{cabinet_id}__{role}`。
- 当前踢脚工法是侧板落地：`base.construction=integrated`，踢脚板仍挂在 `carcass`。
- 当前抽屉前板即盒体前脸，写在该抽屉的 `box.panels`，不进 `fronts`。
- 可选提案字段 `cabinet_id` 是身份不是构造参数，准入 `FurnitureSpec` 前弹出；缺省 `cabinet_1`。交互主流程一份意图一台柜；多柜用 `plan_panel_cabinets()`，不同外包络仍要多份已确认意图。

交接函数从 `spec` 派生运行时 `CabinetStructure`，再由 `flatten_panels_for_handoff()` 得到板件列表（接触按装配收口后回贴到相关板上，供制造使用）。旧冻结文件若只有柜级 `structure/panels`，交接函数按旧形状还原，不重跑规划。顶层不得再写 `spec/structure/panels/cabinet_id`。工具快照 `current_view` 对 `panel_plan` 是 `panel_review.py` 从这棵树派生的确认审查清单，不是冻结文件本身。分析记录属于旁路证据，不并入板件事实。

确认后的板件冻成 `store/<project-id>/panels/<sha256>.json`，Revision 记下 `confirmed_panel_sha256`。有 Project Store 时，制造、板件旁路分析、CAD 板件快照和交付哈希按该哈希读冻结文件，文件缺失则失败；未确认、旧项目没有该哈希、或没有 Store 时仍读内存中的 `stage_outputs.panel_plan`。不重跑 `plan_panel_stage()`。

## 模块

| 模块 | 职责 | 边界理由 |
| --- | --- | --- |
| `panel_spec.py` | schema、完整性、客观冲突、`back_mount` 准入、料档目录与工艺卡展开 | schema / validation / structured_protocol |
| `structure_planning.py` | 精确净空与柜体区域 | calculation |
| `panel_rules.py` | 踢脚支撑数量、背拉条数量与净距 | calculation |
| `construction_geometry.py` | 层板/抽屉/踢脚/背拉条盒子 | calculation |
| `topology_solver.py` | 读柜型 YAML，物化板件位置与语义面 | calculation |
| `assembly_tree.py` | 把求解结果编成柜→子装配→板，并按装配收口接触 | calculation / schema |
| `joint_topology.py` | 承面–端面接触几何；不解析连不连 | calculation |
| `panel_review.py` | 确认审查清单：净空、板件一行一条、接触去重；不含连不连 | calculation / structured_protocol |
| `validation.py` | 检查点入口；柜体/装配在 `validation_cabinet.py`，板件角色在 `validation_panels.py` | validation |
| `quantitative_audit.py` / `design_optimization.py` | 旁路分析 | 只写 `stage_analyses` |

本阶段只产出尺寸、位置和承面–端面接触。连不连默认规则在制造 [连接与接触默认规则](../manufacture-plan/references/connection-contact-defaults.md)。
