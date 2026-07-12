---
name: furniture-panel-planning
description: 将已确认的家具布局拆分为有语义的实体板件。适用于 panels_planned 阶段的板件名称、角色、尺寸、位置和材料角色规划，不处理五金细节或 CAD 生成。
---

# 家具板件规划

阶段：`panels_planned`

## 工作流

1. 要求 `design_intent` 与 `layout_planned` 已确认。
2. 读取 [板件规则](references/panel-planning.md)，把布局空间转换为明确的实体板件。
3. 通过 `FurnitureOrchestrator.run_next()` 生成板件阶段输出。
4. 展示 `stage_outputs.panels_planned` 并暂停；不得同时生成制造策略。

## 边界

- 本阶段运行时代码位于 `scripts/furniture_panel_planning/`。
- 板件必须有稳定标识、语义角色、尺寸、位置和材料角色。
- 修改板件规划时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此阶段确定连接件孔位、封边细节、最终 BOM 或 CAD 操作。
