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
4. 通过 `FurnitureOrchestrator.run_next()` 生成制造阶段输出，展示后暂停。

## 边界

- 本阶段运行时代码位于 `scripts/furniture_manufacturing/`。
- 修改制造策略时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此技能中发射特征树、调用 CAD Bridge 或手工修改派生产物。
