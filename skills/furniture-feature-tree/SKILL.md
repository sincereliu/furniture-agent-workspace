---
name: furniture-feature-tree
description: 将已确认的家具制造策略转换为可审查的特征树建模语义。适用于 feature_tree_planned 阶段的部件、依赖、操作顺序和 CAD 表达规划；完成后暂停，不生成几何。
---

# 家具特征树规划

阶段：`feature_tree_planned`

## 工作流

1. 要求设计意图、布局、板件和制造策略均已确认。
2. 读取 [特征树规则](references/feature-tree.md)，把制造部件转换为建模职责、依赖和操作顺序。
3. Feature Tree v2 将板件保存为 `box` 特征，将制造加工记录保存为目标明确的 `cut_box` 操作；每个切削必须引用已存在的目标板件并完全位于其包络内。
4. 仅 `groove` 背板的四条槽进入 `cut_box`；`insert/cover` 的连接孔和背拉条端孔保留在制造阶段的 drilled-holes 数据中，不虚构为方盒切削。
5. 通过 `FurnitureOrchestrator.run_next()` 生成特征树阶段输出，由 `scripts/furniture_feature_tree/validation.py` 调用公开的 `validate_feature_tree()` 校验结构。
6. 展示 `stage_outputs.feature_tree_planned` 并暂停；不得同时生成 CAD。

## 边界

- 本阶段运行时代码位于 `scripts/furniture_feature_tree/`。
- 修改特征树时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不直接调用特征树发射器、CAD Bridge 或外部 CAD CLI。
- 不在本技能中定义第二套特征树格式或运行时。
