---
name: furniture-layout
description: 根据已确认的家具设计意图规划空间组织、净空、分区和定位。适用于 layout_planned 阶段；必须保持左下角落地基准，并在进入板件规划前等待确认。
---

# 家具布局规划

阶段：`layout_planned`

## 工作流

1. 要求当前 Revision 的 `design_intent` 已确认。
2. 读取 [布局规则](references/layout-planning.md)，规划外包络、空间分区、净空和定位。
3. `CabinetLayout` 只输出成品包络、内部净空、背板基准面、踢脚区域以及层板/门数量等空间决策。
4. 通过 `FurnitureOrchestrator.run_next()` 生成布局阶段输出。
5. 展示 `stage_outputs.layout_planned.layout` 并暂停；不得同时生成板件。

## 边界

- 本阶段运行时代码位于 `scripts/furniture_layout/`。
- 默认坐标原点是成品外包络的左下落地角。
- 修改布局时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不输出板件角色、板件数量、成品板件尺寸、连接件、孔位、BOM 或 CAD 几何。
