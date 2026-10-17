# 运行时映射（板件阶段）

核对实现或规划演进时再读；提案字段以 [提案契约](panel-proposal-contract.md) 为准。

## 入口

- `panel_pipeline.py::plan_panel_stage()`：交互主流程入口，接收已确认布局的全部可执行柜体包络（`id` / `furniture_category` / `width` / `depth` / `height`），将共享板件提案应用到每个柜体。
- `plan_panel_cabinets()`：接收逐柜的包络与参数组合。
- Orchestrator 把已确认布局的 CAD 单元投影成外形尺寸（丢掉房间、摆放、原点、转角），再从 `revision.stage_inputs.panels.parameters` 取提案。首次生成先写入该对象再 `run_next()`，或 `retry_stage("panel_plan", stage_input={"parameters": ...})`。

## 交接

下游（制造、旁路分析、`revise_stage_output`）只通过 `cabinets_from_output()` / `handoffs_from_output()` 读板件结果；**只看一台**时用 `cabinet_handoff(output, cabinet_id)`——**哪一台必须说清**（`require_primary_handoff()` 与 `primary_cabinet()` 已删：它们默默取第一台，多柜工程里算错对象）。检查点只有 `cabinets[]`。每台柜带 `id` 和 `spec/interior/back_mount_resolution/assemblies`，不得在柜级再抄 `panels` 或 `structure`。

- `interior.cavity`：内空宽高深和角点；`interior.zones`：前开口分区。
- `assemblies`：`carcass`、可选 `base`、`fronts`、`drawers[]`。板件和接触只写在所属子装配内。
- 板件：`parent_id`（柜体）、`assembly_id`（子装配）、`role`（如 `left_side_panel`）；全局 `id` 为 `{cabinet_id}__{role}`。
- 当前踢脚工法是侧板落地：`base.construction=integrated`，踢脚板仍挂在 `carcass`。
- 当前抽屉前板即盒体前脸，写在该抽屉的 `box.panels`，不进 `fronts`。
- `cabinet_id` 是身份不是构造参数，准入 `FurnitureSpec` 前弹出。交互主流程保留各布局单元的 `id`，同一项目可有多个柜体；需要逐柜不同参数时使用 `plan_panel_cabinets()` 的逐柜请求。

交接函数从 `spec` 派生运行时 `CabinetStructure`，再由 `flatten_panels_for_handoff()` 得到板件列表（接触按装配收口后回贴到相关板上，供制造使用）。柜上必须有 `interior` 和 `assemblies`。顶层不得再写 `spec/structure/panels/cabinet_id`。工具快照 `current_view` 对 `panel_plan` 是 `panel_review.py` 从这棵树派生的确认审查清单，不是冻结文件本身。分析记录属于旁路证据，不并入板件事实。

确认后的板件冻成 `store/<project-id>/panels/<sha256>.json`，Revision 记下 `confirmed_panel_sha256`。有 Project Store 时，制造、板件旁路分析、CAD 板件快照和交付哈希按该哈希读冻结文件，文件缺失则失败；尚未记录冻结哈希、或没有 Store 时仍读内存中的 `stage_outputs.panel_plan`。不重跑 `plan_panel_stage()`。

**看结构（只读）**：预览里的一台柜子结构页在板件已确认时读同一份冻结文件（`confirmed_panel_sha256` 指向的那份），已生成候选但尚未确认时读当前 `stage_outputs.panel_plan` 供三维审查（不开放顺纹保存），还没有生成过板件时只画布局里已保存的外形（怎么挂路由见 [布局预览维护](../../layout-plan/references/preview-ops.md)）。这条链只读：不写 `stage_outputs`、不改确认状态、不喂下游。

**顺纹方向是板件的属性，不是显示数据**：每块板带 `grain_axis`（`x` 沿宽 / `y` 沿深 / `z` 沿高 / `none` 不限），默认值由**类型**在 `grain_rules.GRAIN_BY_TYPE` 给（侧板 / 门板 / 抽面 / 背板沿高，层板 / 顶板 / 底板 / 踢脚板沿宽，背拉条不限；没点名的类型按沿高），随板件一起进冻结文件。板件页上可以按订单改它（`POST /api/project/{id}/cabinets/{id}/grain` → `revise_stage_output` → 重新冻结），所以**同一类型的板在不同工程里可以不一样**，别再假设"侧板一定沿高"。`_grain_uv()` 把这个轴换算成每个面怎么转、铺几遍：木纹画在贴图横向上，按「这个面的横向是不是顺纹轴」**逐个面**决定转不转，一个全局旋转值必然顾此失彼（`px` 要 0、`py` 要 90°）。渲染端只照着摆，不自己判断。

**材料**仍只供那一页画图：按**角色**分（门板 / 抽屉前脸白色，其余柜体木纹），不进冻结文件。

**已知缺口（未做，不要以为已有）**：制造阶段自己的 `ConfirmedPanel` 没有 `grain_axis`——`admit_panels()` 会把多余字段**忽略掉**（不会报错，也不会崩）。所以顺纹方向目前只到冻结文件为止，制造 / 开料还没有读它。要做"按顺纹排版/开料"得先扩制造那个模型。

## 模块

| 模块 | 职责 | 边界理由 |
| --- | --- | --- |
| `cabinet_envelope.py` | 板件阶段拥有的柜体外形尺寸；忽略 CAD 单元上的布局专用字段 | schema / structured_protocol |
| `panel_spec.py` | schema、完整性、客观冲突、`back_mount` 准入、料档工艺卡展开、省略的层板均分与踢脚支撑数 | schema / validation / calculation / structured_protocol |
| `structure_planning.py` | 精确净空与柜体区域 | calculation |
| `panel_rules.py` | 省略时的踢脚支撑数与层板均分、支撑净距、背拉条数量与净距 | calculation |
| `interior_structure.py` | 正面缝、中立板区间、腔净空和分段长度；不物化柜体板件 | calculation |
| `construction_geometry.py` | 层板/抽屉/踢脚/背拉条盒子 | calculation |
| `topology_solver.py` | 读柜型 YAML，物化板件位置与语义面 | calculation |
| `assembly_tree.py` | 把求解结果编成柜→子装配→板，并按装配收口接触 | calculation / schema |
| `joint_topology.py` | 大面–端面接触几何；不解析连不连 | calculation |
| `panel_review.py` | 确认审查清单：净空、板件一行一条、接触去重；不含连不连 | calculation / structured_protocol |
| `grain_rules.py` | 顺纹方向这个板件属性的默认值、允许取值与规整（进冻结文件） | schema / calculation |
| `cabinet_panel_page.py` | 一台柜子的板件页。给了板件结构投影（已确认冻结板件或待确认候选板件）就画结构；没有只画布局里已保存的外形。`panel_structure_view()` 只把结构投影成页面能画的尺寸、位置、装配、材料，以及把板件带的 `grain_axis` 换算成每个面怎么摆贴图（`_grain_uv()`）；不确认布局，不生成门和层板 | structured_protocol |
| `validation.py` | 检查点入口；柜体/装配在 `validation_cabinet.py`，板件角色在 `validation_panels.py` | validation |
| `quantitative_audit.py` / `design_optimization.py` | 旁路分析 | 只写 `stage_analyses` |

本阶段只产出尺寸、位置和大面–端面接触。接触字段是 `bearing_id`、`end_id`、`face`、`edge_axis`、`edge_sign`、`end_z`、`end_size_z`。接触上出现 `connection` 时拒绝加载。连不连由制造阶段自己决定。
