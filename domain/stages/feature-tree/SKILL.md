---
name: feature-tree
description: 用于 feature_tree_planned 阶段。将已确认制造策略转为可审查的部件、依赖、顺序和 CAD 建模语义。适用于建模顺序、部件依赖与切削操作表达；背板安装和槽参数归板件，槽加工位置与合法性归制造，STEP 几何生成归 CAD 工具。
---

# 家具特征树规划

阶段：`feature_tree_planned`

**这一阶段只回答一件事：已确认的制造方案，按什么部件、依赖和顺序去建模。** 交出去的是一棵可审查的特征树。还不生成几何。

## 人要交什么

布局、板件和制造策略都要已经确认。房间场景与本阶段无关。板件几何来自已确认的冻结板件，制造结果来自已确认的制造输出。不重跑 `panel-plan`。

建模职责、依赖和顺序按 [特征树建模规则](references/feature-tree-rules.md) 转换。

## 一步一步做什么

1. **确认板件和制造都已冻结。** 缺一段就停。
2. **按特征树规则排出部件、依赖和顺序。**
3. **用 Feature Tree v2 表达。** `box` 表示板件。带 `target` 的 `cut_box` 表示切削。槽包络的主校验在制造阶段。本阶段再核对目标是否存在、切削包络是否说得通。
4. **将制造输出中的背板槽逐条转为 `cut_box`。** 不在本阶段按固定条数重建槽；目标与数量以已确认制造输出为准。圆孔保留为 drilled-holes，不写成方盒切削；`insert` / `cover` 不补槽。
5. **调用 `furniture_run_next(project_id)` 生成。** `scripts/furniture_feature_tree/validation.py` 调用公开的 `validate_feature_tree()` 做校验。
6. **展示结果。** 把 `stage_outputs.feature_tree_planned` 给客户看。客户已经接受这一版时再确认。还没接受时不确认，也不生成 CAD。
7. **要再试或要改。** 同一份已确认制造结果上再试，用 `furniture_retry_stage(project_id, stage="feature_tree_planned")`。直接改已有特征树，使用 Python API `revise_stage_output()`，本阶段及下游失效；它不在宿主注册工具中。阶段确认统一使用 [交互工具面](../cad-generated/references/agent-tool-contract.md) 的 `furniture_confirm_stage`。

## 本阶段不做什么

不直接调用发射器、CAD Bridge 或外部 CAD CLI。不另定义一套格式或运行时。

## 参考导航

- 建模职责、依赖和顺序： [特征树建模规则](references/feature-tree-rules.md)
- 运行时在 `scripts/furniture_feature_tree/`。
