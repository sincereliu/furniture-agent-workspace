---
name: furniture-manufacturing
description: 根据已确认板件规划制定材料、封边、连接、五金、孔位和 BOM 假设。适用于 manufacturing_planned 阶段；输出制造策略后暂停，不直接构造特征树或 CAD。
---

# 家具制造策略

阶段：`manufacturing_planned`

## 工作流

1. 要求设计意图、布局和板件规划均已确认。
2. 读取 [制造策略](references/manufacturing-policy.md)，确定材料、封边、连接方式、五金、孔位规则、公差和 BOM 假设。
3. 以 `scripts/furniture_manufacturing/hardware_catalog.yaml` 和 `hardware_rules.yaml` 的实时代码数据为准。
4. 入槽背板生成左侧板、右侧板、顶板、底板 4 条目标明确的 `cut_box` 加工记录；槽宽 = `back_thickness + groove_clearance`，槽深 = `groove_depth`。
5. 材料厚度必须来自确认后的 `FurnitureSpec`，不得用硬编码厚度覆盖用户输入。
6. 通过 `FurnitureOrchestrator.run_next()` 生成制造阶段输出，展示后暂停。

## 边界

- 本阶段运行时代码位于 `scripts/furniture_manufacturing/`。
- 修改制造策略时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此技能中发射特征树、调用 CAD Bridge 或手工修改派生产物。
