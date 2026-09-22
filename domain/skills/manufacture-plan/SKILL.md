---
name: manufacture-plan
description: 用于 manufacture_plan 阶段。当用户说"用什么五金""三合一连接件""铰链怎么装""封边怎么做""出BOM清单""打孔位置"时触发。根据已确认板件制定材料、封边、连接、五金、孔位和 BOM，不构造特征树或 CAD。
---

# 家具制造策略

阶段：`manufacture_plan`

**这一阶段只回答一件事：已确认的板件用什么材料、封边、连接和五金，孔打在哪，BOM 怎么列。** 交出去的是一版还没确认的制造方案。特征树和柜体模型都不在这里做。

## 人要交什么

前置：`layout_plan` 与 `panel_plan` 都已确认。

有 Project Store 时，制造按确认时记下的 `confirmed_panel_sha256` 读 `store/<project-id>/panels/<sha256>.json`。文件缺失就失败。不改用内存里的板件，也不重跑 `panel-plan`。无 Store 时读内存中已确认的 `stage_outputs.panel_plan`。

由 LLM 根据完整上下文理解制造需求，提出整份策略草案，并把未明确的假设逐项列出给用户确认。策略覆盖：

- 材料：类别、等级、厚度、纹理、可见面、饰面。材质选型按角色（柜体/门板/背板）引用 `materials_catalog.yaml` 的 `substrate` / `surface` 键，经 `appearance` 输入，由代码查表准入。材料厚度来自已确认的 `panel_plan`，不在这里另写一套。
- 封边：封哪些边、封边条材质和厚度。选型 `{material, thickness}` 经 `requested_options.edge_banding` 输入（默认 ABS 1.0mm），由代码查表准入。封边宽度（等于板厚）和颜色（同色取 surface 的花色）由代码派生。
- 连接：螺钉、木榫、偏心件（三合一/二合一）、槽、胶合。接触默认连不连见 [连接与接触默认规则](references/connection-contact-defaults.md)。
- 活动层板连接：`movable_shelf_connector`（`two_in_one` 二合一 / `shelf_pin` 层板托）。有活动层板时必须显式选择，经 `requested_options` 传入并盖章到 `PanelRecord`。没提供时运行时拒绝，不静默补齐。
- 五金：铰链、滑轨、拉手、层板托、固定、防倾倒及荷载。单门铰链侧 `door_hinge_side`（`left` / `right`）是制造输入。双门由制造按门板位置派生。不从意图重建，也不硬编码覆盖。
- 公差和净空：门缝、安装/设备缝隙、地墙不平、安全余量。

口径见 [制造规则](references/manufacturing-rules.md)。不做关键词识别、同义词映射或开放方案排序。五金变体与打孔参数以 `scripts/furniture_manufacturing/hardware_catalog.yaml`、`hardware_rules.yaml` 为准：LLM 只选变体，并把数值假设标为待确认，不硬编码或猜测参数。

## 一步一步做什么

1. **确认板件文件还在。** 两段前置都已确认。有 Store 时，冻结板件文件缺失就停，不要改读内存。
2. **把制造需求收成整份策略。** 这一步只整理，还不调用工具。假设逐项给客户看。
3. **调用 `FurnitureOrchestrator.run_next()`。** 代码生成孔位、封边、槽和 BOM，并由运行时校验。
4. **展示后停。** 把整套制造方案给客户看。`readiness` 默认 `preliminary`。它表示整份方案和 BOM 的接受程度，不是每条五金或封边各自审批过。
5. **客户明确接受，才升 `accepted`。** 工厂确认之后才升 `factory_ready`。
6. **同一批已确认板件上再试。** 调用 `retry_stage("manufacture_plan")`。冻结板件文件保持不变。直接改已有制造结果用 `revise_stage_output()`，本阶段及下游失效。

## 守住这些口径

- 三合一在高度方向按系统 32 排钻分布，深度方向前后双排。铰链孔、背板槽、背板连接和封边的精确口径见 [制造规则](references/manufacturing-rules.md)。
- 入槽背板不封边。其余背板及背拉条四边封边。cover 外盖螺钉与 groove 背拉条螺钉是组装现场工艺，不生成孔位与五金。

## 按触发词另外读

日常做材料、封边、连接、孔和 BOM 不必打开下面这些。

| 用户提到 | 读取/调用 |
|---------|----------|
| 对照外部五金/加工类目、打孔 | `references/hardware-machining-reference.md` |
| 六面钻、机床加工、导 XML | `references/six-side-drill-export.md` |
| 样件、承重、连接件或涂装对比试验 | `../../external/scientific-agent-skills/skills/experimental-design/SKILL.md` + `prototype_experiment.py` |
| 分析已采集试验数据 | `../../external/scientific-agent-skills/skills/statistical-analysis/SKILL.md` + `test_statistics.py` |
| 板件加工路线、共享设备、齐套装配、工位排队、交期 | `../../external/scientific-agent-skills/skills/simpy/SKILL.md` + `production_simulation.py` |

试验、统计和生产仿真写入 `stage_analyses.manufacture_plan`，只提供证据或候选。它们不自动提升 `readiness`，不直接修改 BOM，也不构成现实工厂因果结论。

## 本阶段不做什么

- 不发射特征树，不调用 CAD Bridge，不手改派生产物。
- 不重跑板件规划。板件几何以冻结文件为准。

## 参考导航

运行时在 `scripts/furniture_manufacturing/`。代码契约见 [运行时映射](references/runtime-map.md)。未落地需求见 [backlog](references/backlog.md)，日常实现不必读。

- 孔位、封边、槽和背板连接的口径： [制造规则](references/manufacturing-rules.md)
- 哪对接触默认连、哪对默认不连： [连接与接触默认规则](references/connection-contact-defaults.md)
