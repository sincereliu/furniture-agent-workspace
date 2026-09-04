# 板件旁路分析

回答“`panels_planned` 完成后，可以对当前板件事实输出做哪些附加分析，它们如何与核心阶段解耦？”；本文件只描述旁路分析，不定义板件生成规则。

## 总原则

- `panels_planned` 的唯一事实来源仍是 `spec`、`structure`、`back_mount_resolution` 和 `panels`。
- 旁路分析只读取当前阶段输出，写入 `stage_analyses.panels_planned`。
- 旁路分析不能静默修改板件事实输出，不能替代结构化准入，也不能直接变成制造或 CAD 输入。

## 单位与不确定度审计

- 用户要求尺寸链、单位或公差审计时，先读 `../../external/scientific-agent-skills/skills/uncertainty-and-units/SKILL.md`。
- 再用 `scripts/furniture_panel_planning/quantitative_audit.py` 生成 `panel_unit_audit`。
- 审计只报告量纲一致性、派生净空测量模型和可选不确定度传播，不据此静默改板件。

## 多目标候选分析

- 用户要求在材料用量、内部空间和复杂度间比较候选时，先读 `../../external/scientific-agent-skills/skills/pymoo/SKILL.md`。
- 由 LLM 明确目标、变量和约束，再用 `scripts/furniture_panel_planning/design_optimization.py` 生成 `panel_optimization`。
- 结果是候选集与 Pareto 摘要，不是新的板件事实输出。
- 只有用户明确选中候选后，才可通过 `revise_stage_output()` 物化新的 `panels_planned` 结果。

## 边界

- 分析报告属于可重跑证据，允许失效和重算。
- 分析记录应保留来源摘要、输入哈希或等效追溯信息，避免和核心板件事实混淆。
- 如果分析需要额外领域方法，应先加载对应外部 scientific skill，再调用本仓库运行时代码。