---
name: furniture-layout
description: 用于 layout_planned 阶段；为当前固定柜体模板计算成品包络、内部净空、背板基准、踢脚区和层板/门数量。
---

# 家具布局规划

阶段：`layout_planned`

## 工作流

1. 要求当前 Revision 的 `design_intent` 已确认。
2. 按 [空间布局规则](references/spatial-layout-rules.md) 计算当前固定地柜/吊柜模板的外包络、柜体深度、内部净空、背板基准和踢脚区。
3. `CabinetLayout` 保留有效 `back_mount`，输出成品包络、`carcass_y_start/end`、内部 X/Y/Z 范围、背板基准、踢脚前后位置以及 `shelf_count/door_count`。数量不等于分区、开口或开启策略。
4. 用 `FurnitureOrchestrator.run_next()` 生成；`scripts/furniture_layout/validation.py` 最终计算并校验内部净宽/净高/净深、背板模式和区域边界。
5. 展示 `stage_outputs.layout_planned.layout` 后暂停，不生成板件。

## 边界

- 运行时在 `scripts/furniture_layout/`；原点为成品外包络左后下落地角。
- 修改布局用 `revise_stage_output()`，使本阶段及下游失效。
- 当前运行时不表达抽屉、隔板分区、开放格、滑门、盖门/嵌门、挂衣区或设备区；这些要求若存在，必须在意图阶段保持未决，不得在本阶段假装已布局。
- 本阶段对最终内部净空负责；不把净空合法性退回意图阶段，也不判断支撑、背拉条、槽或孔位。
- 不输出板件角色、板件数量、成品板件尺寸、连接件、孔位、BOM 或 CAD 几何。
