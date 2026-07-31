---
name: furniture-panel-planning
description: 用于 panels_planned 阶段；在客户确认布局后首次确定结构规格、精确净空、背板与踢脚，并生成可审查的实体板件。
---

# 家具板件规划

阶段：`panels_planned`

## 工作流

1. 要求 `design_intent` 与 `layout_planned` 已确认。
2. 从本阶段 `stage_inputs.panels.parameters` 首次物化 `FurnitureSpec`，包括板厚、背板、踢脚、门缝及结构覆盖值；不得从 `DesignIntent` 读取这些字段。
3. 依据 [背板结构规则](references/back-construction-rules.md) 解析 `back_mount=auto`，生成精确 `CabinetStructure`：柜体前后范围、内部 X/Y/Z 净空、背板基准和踢脚区域。
4. 按 [板件定义规则](references/panel-definition-rules.md) 与 `references/cabinet-topologies/` 柜型拓扑生成实体板件；仅入槽背板生成背拉条。
5. `panel_rules.py` 统一计算踢脚支撑与背拉条数量/净距；生成器和校验器必须共用。
6. 输出 `spec/structure/back_mount_resolution/panels`；校验结构规格、精确净空、板件标识/尺寸/位置/依赖和背板几何，展示后暂停，不生成制造策略。

## 边界

- 运行时在 `scripts/furniture_panel_planning/`；`panel_spec.py` 是结构默认值和背板模式解析的唯一所有者，`structure_planning.py` 是精确净空的唯一所有者。
- 板件须有稳定标识、角色、尺寸、位置和材料角色；本阶段输出是后续制造所用的已确认 `FurnitureSpec` 来源。
- 修改规划用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此阶段确定连接件孔位、封边细节、最终 BOM 或 CAD 操作。
