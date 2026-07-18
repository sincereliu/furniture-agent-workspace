---
name: furniture-layout
description: 用于 layout_planned 阶段；根据已确认意图规划空间、净空、分区和定位，保持左下落地基准。
---

# 家具布局规划

阶段：`layout_planned`

## 工作流

1. 要求当前 Revision 的 `design_intent` 已确认。
2. 按 [布局规则](references/layout-planning.md) 规划外包络、分区、净空和定位。
3. `CabinetLayout` 保留有效 `back_mount`，输出成品包络、`carcass_y_start/end`、内部净空、背板基准、踢脚区及层板/门数量。
4. 用 `FurnitureOrchestrator.run_next()` 生成；`scripts/furniture_layout/validation.py` 校验包络、净空、背板模式和区域边界。
5. 展示 `stage_outputs.layout_planned.layout` 后暂停，不生成板件。

## 边界

- 运行时在 `scripts/furniture_layout/`；原点为成品外包络左下落地角。
- 修改布局用 `revise_stage_output()`，使本阶段及下游失效。
- 不输出板件角色、板件数量、成品板件尺寸、连接件、孔位、BOM 或 CAD 几何。
