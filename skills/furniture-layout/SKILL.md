---
name: furniture-layout
description: 用于 layout_planned 阶段；计算当前固定柜体模板的成品包络、内部净空及其在房间中的位置，并生成早期 SVG 平面预览。
---

# 家具布局规划

阶段：`layout_planned`

## 工作流

1. 要求当前 Revision 的 `design_intent` 已确认。
2. 按 [空间布局规则](references/spatial-layout-rules.md) 计算当前固定地柜/吊柜模板的外包络、柜体深度、内部净空、背板基准和踢脚区。
3. 若意图同时提供 `layout.room` 与 `layout.placement`，解析房间、门窗、障碍物和沿墙/自由摆放位置；输出房间坐标变换、四角占地、六向净距及 SVG 平面预览。两者只提供其一时停止。
4. `CabinetLayout` 保留有效 `back_mount`，输出成品包络、`carcass_y_start/end`、内部 X/Y/Z 范围、背板基准、踢脚前后位置以及 `shelf_count/door_count`。数量不等于分区、开口或开启策略。
5. 用 `FurnitureOrchestrator.run_next()` 生成；`scripts/furniture_layout/validation.py` 校验内部净空、背板模式、房间边界、门窗遮挡、障碍物碰撞和预览谱系。
6. 展示 `stage_outputs.layout_planned.layout`；若存在 `preview.svg`，将其作为 `image/svg+xml` 展示，然后暂停，不生成板件。

## 边界

- 运行时在 `scripts/furniture_layout/`；柜体局部原点仍为成品外包络左后下落地角，房间另有左下地面角原点，二者通过 `room_placement.placement` 关联。
- 修改布局用 `revise_stage_output()`，使本阶段及下游失效。
- 当前运行时不表达抽屉、隔板分区、开放格、滑门、盖门/嵌门、挂衣区或设备区；这些要求若存在，必须在意图阶段保持未决，不得在本阶段假装已布局。
- 本阶段对最终内部净空负责；不把净空合法性退回意图阶段，也不判断支撑、背拉条、槽或孔位。
- 房间模型当前为矩形空间；障碍物为轴对齐长方体。SVG 只表达布局包络，不代表真实衣柜分区、板件或外观。
- 不输出板件角色、板件数量、成品板件尺寸、连接件、孔位、BOM 或 CAD 几何；早期预览不进入 CAD 产物链。
