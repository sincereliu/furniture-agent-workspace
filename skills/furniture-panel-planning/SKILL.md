---
name: furniture-panel-planning
description: 用于 panels_planned 阶段；将已确认布局拆成有稳定标识、角色、尺寸、位置和材料语义的实体板件，不处理五金或 CAD。
---

# 家具板件规划

阶段：`panels_planned`

## 工作流

1. 要求 `design_intent` 与 `layout_planned` 已确认。
2. 按 [板件规则](references/panel-planning.md) 将 `CabinetLayout` 转为实体板件。
3. 按有效 `back_mount` 生成入槽/内嵌/外盖背板，仅入槽生成背拉条；同时确定前后踢脚板及支撑板的数量、尺寸、位置。
4. 用 `FurnitureOrchestrator.run_next()` 生成；`scripts/furniture_panel_planning/validation.py` 校验标识、尺寸、位置、依赖和背板几何。
5. 展示 `stage_outputs.panels_planned.panels` 后暂停，不生成制造策略。

## 边界

- 运行时在 `scripts/furniture_panel_planning/`；板件须有稳定标识、角色、尺寸、位置和材料角色。
- 修改规划用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此阶段确定连接件孔位、封边细节、最终 BOM 或 CAD 操作。
