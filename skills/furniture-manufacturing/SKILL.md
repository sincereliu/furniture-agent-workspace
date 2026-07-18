---
name: furniture-manufacturing
description: 用于 manufacturing_planned 阶段；根据已确认板件制定材料、封边、连接、五金、孔位和 BOM，不构造特征树或 CAD。
---

# 家具制造策略

阶段：`manufacturing_planned`

## 工作流

1. 要求设计意图、布局和板件规划均已确认。
2. 按 [制造规则](references/manufacturing-rules.md) 确定材料、封边、连接、五金、孔位、公差和 BOM 假设。
3. 五金规格以 `scripts/furniture_manufacturing/hardware_catalog.yaml` 和 `hardware_rules.yaml` 为准。
4. `connectors/` 集中连接/打孔逻辑：`Connector` 基类及 `TrinityConnector`、`HingeConnector`、`ShelfConnector`、`BackMountConnector`。新五金新增 Connector 并注册 `ALL_CONNECTORS`。
5. 单板规则实现 `generate_holes()`；需配合板时覆盖 `generate_holes_for_panels()` 生成成对孔。`estimate_hardware()` 与 `emit_drilled_holes()` 遍历 `ALL_CONNECTORS` 生成 BOM 和含全局/local 坐标的 JSON；`drilled_holes_glb.py` 输出标记 GLB。
6. `groove` 为左右侧板、顶/底板生成 4 条目标明确的 `cut_box`：槽宽 `back_thickness + groove_clearance`，槽深 `groove_depth`；并生成背拉条端连接。`insert` 输出四边三合一成对孔；`cover` 输出周边沉头螺钉及背板/柜体成对孔。
7. 入槽背板不封边；其他背板及背拉条四边封边。螺钉和默认孔距均为软件暂定值，BOM 须注明投产前确认。
8. 厚度来自已确认 `FurnitureSpec`，不得硬编码覆盖。`door_hinge_side` 可为 `"left"/"right"`；缺省由 `HingeConnector` 按位置推断，杯孔只从门板内侧钻入。
9. 用 `FurnitureOrchestrator.run_next()` 生成；`scripts/furniture_manufacturing/validation.py` 校验 BOM、加工边界、背板五金和配合孔，展示后暂停。

## 边界

- 运行时在 `scripts/furniture_manufacturing/`。
- 修改制造策略时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不发射特征树、不调用 CAD Bridge、不手改派生产物。
