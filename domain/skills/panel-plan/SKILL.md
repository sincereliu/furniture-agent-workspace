---
name: panel-plan
description: 用于 panels_planned 阶段。当用户说“几扇门”“几层板”“要不要抽屉”“背板怎么装”“踢脚多高”“板厚多少”，或需要从已确认外包络生成可审查板件时使用。门、层板、抽屉、背板、背拉条和踢脚先由 LLM 提案，经结构化代码准入后物化。单位审计与优化属于旁路分析，不属于核心板件生成。
---

# 家具板件规划

阶段：`panels_planned`

## 核心流程

1. 前置只有已确认并冻结的 `design_intent`；独立 `layout-plan` 结果不是前置条件。板件规划只读这份冻结意图，不改类别或外包络。
2. 由 LLM 根据完整上下文理解需求、消歧并推荐整份板件方案；未明确值以假设形式展示，不在脚本里做关键词识别、同义词映射或开放方案排序。
3. 把选定草稿的全部规范字段写入 `stage_inputs.panels.parameters`。完整字段、显式值要求与候选起点见 [提案契约](references/panel-proposal-contract.md)。
4. 由 `FurnitureSpec.from_intent()` 校验意图确认状态、字段完整性/类型和客观结构冲突，首次物化完整规范；无法由当前拓扑表达的混合语义必须继续消歧，不得让运行时丢弃字段。
5. 依据 [背板结构规则](references/back-construction-rules.md)、[板件定义规则](references/panel-definition-rules.md)、[抽屉尺寸链](references/drawer-dimension-chain.md) 和 `references/cabinet-topologies/` 生成柜体实例及其 `spec/structure/back_mount_resolution/panels`；当背板模式需要时，同时物化背拉条并纳入同一阶段校验。
6. 运行时统一校验柜体身份、板件归属、结构规格、精确净空、板件标识/尺寸/位置/依赖和背板几何。每次规划是一次 attempt：展示后暂停。用户要另一版时调用 `retry_stage("panels_planned")`（可带新的 `stage_inputs.panels`），不要 `revise()` 意图；某次通过的尝试用 `select_stage_attempt()` 选用后再确认。尝试失败只记录该次，冻结意图仍在。`confirm_stage(panels_planned)` 把当前候选冻成 `store/<project-id>/panels/<sha256>.json`；制造只读这份冻结文件，重试制造不会重跑板件。未确认不得进入制造、BOM、特征树或 CAD。

## 提案与展示

- 提案必须覆盖契约中的全部字段。用户没说的值按 [提案契约](references/panel-proposal-contract.md) 的候选起点写成具体值并标成假设，一次确认。
- 停问清单与 `null`/`auto` 口径只在提案契约。
- 展示给用户：一份假设清单；代码准入后再展示柜体 `id`、`back_mount` requested/effective、内部净空和板件清单（含所属柜体）。
- 按当前任务读对应 reference，不要一次加载全部规则。

## 参考导航

- 规范术语和单位口径： [术语规范表](references/terminology-glossary.md)
- 提案字段、显式值要求和 LLM 候选起点： [提案契约](references/panel-proposal-contract.md)
- 背板模式解析、背板基准、内部净深和背拉条约束： [背板结构规则](references/back-construction-rules.md)
- 板件角色、门/层板/踢脚规则和柜型拓扑边界： [板件定义规则](references/panel-definition-rules.md)
- 层板列表、计算层与固定/活动层板物化： [层板规则](references/shelf-planning-rules.md)
- 踢脚区、支撑数量公式和净距： [踢脚规则](references/toe-kick-rules.md)
- 抽屉区尺寸链、适用条件和限制： [抽屉尺寸链](references/drawer-dimension-chain.md)
- 模块职责与入口： [运行时映射](references/runtime-map.md)
- 柜型拓扑骨架： `references/cabinet-topologies/`（围合面、有无踢脚、整高抽屉区类型；门/层板/抽屉几何由求解器执行，不能只加 YAML 就支持新柜型）
- 单位审计和优化等旁路证据： [板件旁路分析](references/panel-side-analyses.md)

## 旁路分析

- `panel_unit_audit` 和 `panel_optimization` 只读取已确认冻结板件（有 Store 时按 `confirmed_panel_sha256` 读文件），写入 `stage_analyses.panels_planned`。
- 它们不自动改写 `panels_planned` 事实输出，不替代结构化准入，也不构成制造或 CAD 的直接输入。
- 只有用户明确选中优化候选后，才可用 `revise_stage_output()` 物化新的板件结果。

## 边界

- 运行时在 `scripts/furniture_panel_planning/`；模块职责和入口见 [运行时映射](references/runtime-map.md)。代码不得按自然语言、柜型或内置 profile 选择方案。
- `panels_planned` 的对象树是 `cabinets[]`：每个柜体是父对象，带 `id` 以及自己的 `spec/structure/back_mount_resolution/panels`。板件带 `parent_id`（所属柜体）和 `role`（柜内角色，如 `left_side_panel`）；全局 `id` 为 `{cabinet_id}__{role}`，避免多柜撞名。检查点只写这棵树，不在顶层再抄一份 `spec/panels`。下游读法见 [运行时映射](references/runtime-map.md)。分析记录属于旁路证据，不并入板件事实。
- 可选结构化字段 `cabinet_id` 是身份，不是构造参数，写入提案后由运行时弹出再准入 `FurnitureSpec`。缺省为 `cabinet_1`。交互式主流程目前仍是一份意图对应一台柜；多柜可经 `plan_panel_cabinets()` 组合，不同外包络仍要多份已确认意图。
- 接触由几何推导（拓扑）；「连不连」见制造 [连接与接触默认规则](../manufacture-plan/references/connection-contact-defaults.md)。本轮没有逐条连接的提案覆盖字段。
- 同一冻结意图上再试一版用 `retry_stage()`；直接改已生成的板件结果用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此阶段确定连接件孔位、封边细节、最终 BOM 或 CAD 操作。
