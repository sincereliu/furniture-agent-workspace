---
name: furniture-feature-tree
description: 用于 feature_tree_planned 阶段。当用户说"建模顺序""哪个部件先做""槽怎么切""背板槽位置"时触发。将已确认制造策略转为可审查的部件、依赖、顺序和 CAD 建模语义，不生成几何。
---

# 家具特征树规划

阶段：`feature_tree_planned`

## 工作流

1. 要求设计意图、板件和制造策略均已确认；独立房间布局不是前置条件。
2. 按 [特征树建模规则](references/feature-tree-rules.md) 转换建模职责、依赖和顺序。
3. Feature Tree v2 用 `box` 表示板件，用带 `target` 的 `cut_box` 表示切削；制造阶段负责槽包络的主校验，本阶段对目标存在性和切削包络做防御性复核。
4. 仅 `groove` 的四条背板槽转为 `cut_box`；`insert/cover` 连接孔和背拉条端孔保留为 drilled-holes，不伪装成方盒切削。
5. 用 `FurnitureOrchestrator.run_next()` 生成；`scripts/furniture_feature_tree/validation.py` 调用公开 `validate_feature_tree()` 校验。
6. 展示 `stage_outputs.feature_tree_planned` 后暂停，不生成 CAD。

## 边界

- 运行时在 `scripts/furniture_feature_tree/`。
- 修改特征树时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不直调发射器、CAD Bridge、外部 CAD CLI，也不定义第二套格式或运行时。
