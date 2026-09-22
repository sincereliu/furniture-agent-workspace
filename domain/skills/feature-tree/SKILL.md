---
name: feature-tree
description: 用于 feature_tree_planned 阶段。当用户说"建模顺序""哪个部件先做""槽怎么切""背板槽位置"时触发。将已确认制造策略转为可审查的部件、依赖、顺序和 CAD 建模语义，不生成几何。
---

# 家具特征树规划

阶段：`feature_tree_planned`

**这一阶段只回答一件事：已确认的制造方案，按什么部件、依赖和顺序去建模。** 交出去的是一棵可审查的特征树。还不生成几何。

## 人要交什么

设计意图、板件和制造策略都要已经确认。房间场景与本阶段无关。板件几何来自已确认的冻结板件，制造结果来自已确认的制造输出。不重跑 `panel-plan`。

建模职责、依赖和顺序按 [特征树建模规则](references/feature-tree-rules.md) 转换。

## 一步一步做什么

1. **确认板件和制造都已冻结。** 缺一段就停。
2. **按特征树规则排出部件、依赖和顺序。**
3. **用 Feature Tree v2 表达。** `box` 表示板件。带 `target` 的 `cut_box` 表示切削。槽包络的主校验在制造阶段。本阶段再核对目标是否存在、切削包络是否说得通。
4. **只有 `groove` 的四条背板槽写成 `cut_box`。** `insert` / `cover` 的连接孔和背拉条端孔保留为 drilled-holes，不写成方盒切削。
5. **调用 `FurnitureOrchestrator.run_next()` 生成。** `scripts/furniture_feature_tree/validation.py` 调用公开的 `validate_feature_tree()` 做校验。
6. **展示后停。** 把 `stage_outputs.feature_tree_planned` 给客户看。这一步不生成 CAD。
7. **要再试或要改。** 同一份已确认制造结果上再试，用 `retry_stage()`。直接改已有特征树，用 `revise_stage_output()`，本阶段及下游失效。

## 本阶段不做什么

不直接调用发射器、CAD Bridge 或外部 CAD CLI。不另定义一套格式或运行时。

## 参考导航

- 建模职责、依赖和顺序： [特征树建模规则](references/feature-tree-rules.md)
- 运行时在 `scripts/furniture_feature_tree/`。
