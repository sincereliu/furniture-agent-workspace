---
name: panel-plan
description: 用于 panels_planned 阶段。在已确认成品外包络上生成可审查的实体板件事实输出；门、层板、抽屉、背板和踢脚方案先由 LLM 提案，经结构化代码准入后物化。单位审计与优化属于旁路分析，不属于核心板件生成。
---

# 家具板件规划

阶段：`panels_planned`

## 核心流程

1. 前置只有 `design_intent` 已确认；独立 `layout-plan` 结果不是前置条件。
2. 由 LLM 根据完整上下文理解需求、消歧并推荐整份板件方案；未明确值以假设形式展示，不在脚本里做关键词识别、同义词映射或开放方案排序。
3. 把选定草稿的全部规范字段写入 `stage_inputs.panels.parameters`。完整字段、显式值要求与候选起点见 [提案契约](references/panel-proposal-contract.md)。
4. 由 `FurnitureSpec.from_intent()` 校验意图确认状态、字段完整性/类型和客观结构冲突，首次物化完整规范；无法由当前拓扑表达的混合语义必须继续消歧，不得让运行时丢弃字段。
5. 依据 [背板结构规则](references/back-construction-rules.md)、[板件定义规则](references/panel-definition-rules.md)、[抽屉尺寸链](references/drawer-dimension-chain.md) 和 `references/cabinet-topologies/` 生成 `spec/structure/back_mount_resolution/panels`。
6. 运行时统一校验结构规格、精确净空、板件标识/尺寸/位置/依赖和背板几何。展示后暂停，等待用户确认；未通过不得进入制造、BOM、特征树或 CAD。

## 参考导航

- 提案字段、显式值要求和 LLM 候选起点： [提案契约](references/panel-proposal-contract.md)
- 背板模式解析、背板基准和内部净深： [背板结构规则](references/back-construction-rules.md)
- 板件角色、门/层板/踢脚规则和柜型拓扑边界： [板件定义规则](references/panel-definition-rules.md)
- 层板列表、计算层与固定/活动层板物化： [层板规则](references/shelf-planning-rules.md)
- 踢脚区、支撑数量公式和净距： [踢脚规则](references/toe-kick-rules.md)
- 抽屉区尺寸链、适用条件和限制： [抽屉尺寸链](references/drawer-dimension-chain.md)
- 柜型拓扑数据： `references/cabinet-topologies/`
- 单位审计和优化等旁路证据： [板件旁路分析](references/panel-side-analyses.md)

## 旁路分析

- `panel_unit_audit` 和 `panel_optimization` 只读取当前 `panels_planned` 输出，写入 `stage_analyses.panels_planned`。
- 它们不自动改写 `panels_planned` 事实输出，不替代结构化准入，也不构成制造或 CAD 的直接输入。
- 只有用户明确选中优化候选后，才可用 `revise_stage_output()` 物化新的板件结果。

## 边界

- 运行时在 `scripts/furniture_panel_planning/`；`panel_spec.py` 只拥有规范 schema、完整性/客观不变量准入和背板模式解析，`structure_planning.py` 是精确净空的唯一所有者。代码不得按自然语言、柜型或内置 profile 选择方案。
- `panels_planned` 的核心事实输出只包括 `spec`、`structure`、`back_mount_resolution` 和 `panels`；分析记录属于旁路证据，不并入板件事实。
- 旧持久化 Project 缺少 `spec.door_hinge_side` 时只做有界 schema 迁移：单门仅从唯一门板已有的显式 `left/right` 恢复，缺失或冲突即停止；标准双门的规格迁移为 `null`，板件缺省侧按确定性左右拓扑恢复；更多门保持 `null`。新提案和扁平 API 契约仍必须显式提交该字段，迁移不得猜测新的单门偏好。
- 修改规划用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此阶段确定连接件孔位、封边细节、最终 BOM 或 CAD 操作。
