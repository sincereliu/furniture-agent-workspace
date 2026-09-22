---
name: panel-plan
description: 用于 panel_plan 阶段。当用户说“几扇门”“几层板”“要不要抽屉”“背板怎么装”“踢脚多高”“板厚多少”，或需要从已确认外形尺寸生成可审查板件时使用。门、层板、抽屉、背板安装、背拉条和踢脚先由 LLM 提案，经结构化代码准入后物化。料厚按车间料档准入，不是开放默认值。单位审计与优化属于旁路分析，不属于核心板件生成。
---

# 家具板件规划

阶段：`panel_plan`

**这一阶段只回答一件事：已确认的柜体外形尺寸里面，门、层板、抽屉、背板、踢脚和料厚怎么落成板。** 交出去的是一版还没确认的板件。房间怎么摆、材料五金、柜体模型都不在这里做。

## 人要交什么

前置只有已确认并冻结的 `layout_plan`。这里只读已确认外形尺寸：`furniture_category`，以及宽、深、高。不读房间、摆放或离地，也不改类别或外形尺寸。

整份板件方案写入 `stage_inputs.panels.parameters`。必填字段、可选料档和候选起点见 [提案契约](references/panel-proposal-contract.md)。料厚目录与工艺卡见 [料档与工艺卡](references/sheet-stock-catalog.md)。

- 提案要盖住契约里的必填字段。客户没说的构造值，按提案契约的候选起点写成具体值，标成假设，一次确认。
- 料档可以省略，按工艺卡展开，不进假设清单。
- 停问清单和 `null` 口径只在提案契约。
- 当前拓扑表达不了的混合语义继续问清楚。运行时不得丢字段。

## 一步一步做什么

按编号往下做。第 6 步是客户要另一版时的回头路。第 7 步是确认。

1. **确认布局已经冻结。** 没有已确认的 `layout_plan` 就停。不要回布局里改外形尺寸。
2. **把客户的话收成整份板件方案。** 这一步只整理，还不调用工具。没说清的构造值写成假设给客户看。不要在脚本里做关键词识别、同义词映射或开放方案排序。
3. **写入参数并调用 `furniture_run_next`。** `FurnitureSpec.from_intent()` 校验意图已经确认、字段完整和类型、以及客观结构冲突，并按工艺卡展开省略的料档，首次物化完整规范。
4. **代码生成柜体。** 依据 [背板结构规则](references/back-construction-rules.md)、[板件定义规则](references/panel-definition-rules.md)、[抽屉尺寸链](references/drawer-dimension-chain.md) 和 `references/cabinet-topologies/` 生成柜体实例及其 `spec` / `interior` / `back_mount_resolution` / `assemblies`。背板模式需要背拉条时，同一阶段把背拉条物化并纳入校验。运行时统一校验柜体身份、子装配归属、结构规格、精确净空、板件标识、尺寸、位置、依赖和背板几何。
5. **展示后停。** 先给客户一份假设清单。代码准入后，展示工具快照 `current_view` 的确认审查清单：柜体、背板安装、内部净空、板件一行一条、接触去重。不要展开完整 `cabinets` 树。清单由运行时从检查点派生，见 [运行时映射](references/runtime-map.md)。每次规划是一次 attempt。
6. **客户要另一版。** 调用 `retry_stage("panel_plan")`，可带新的 `stage_inputs.panels`。不要 `revise()` 意图。失败只记录该次，冻结意图仍在。客户选定某次通过的尝试后，用 `select_stage_attempt()` 选用，再确认。
7. **客户认这版板件，再确认。** `confirm_stage(panel_plan)` 把当前候选冻成 `store/<project-id>/panels/<sha256>.json`。制造只读这份冻结文件，重试制造不会重跑板件。未确认不得进入后续阶段。直接改已经生成的板件结果用 `revise_stage_output()`。

按当前任务读对应 reference，不要一次加载全部规则。

## 本阶段不做什么

- 房间、摆放、门窗洞口：布局阶段。
- 材料、封边、五金、孔，以及「连不连」：制造阶段。这里只产出尺寸、位置和大面–端面接触。口径见 [术语规范表](references/terminology-glossary.md)。
- 特征树和柜体模型：后面的阶段。
- 代码按自然语言、柜型或内置 profile 选方案。料档省略只由工艺卡展开。

## 旁路分析

- `panel_unit_audit` 和 `panel_optimization` 只读取已确认冻结板件。有 Store 时按 `confirmed_panel_sha256` 读文件，写入 `stage_analyses.panel_plan`。
- 它们不改写 `panel_plan` 的事实输出，不替代结构化准入，也不是制造或 CAD 的直接输入。
- 客户明确选中优化候选之后，才用 `revise_stage_output()` 物化新的板件结果。
- 触发哪份外挂见 [板件旁路分析](references/panel-side-analyses.md)。

## 参考导航

运行时在 `scripts/furniture_panel_planning/`。对象树、入口和下游读法见 [运行时映射](references/runtime-map.md)。

- 规范术语和单位口径： [术语规范表](references/terminology-glossary.md)
- 提案字段、显式值要求和 LLM 候选起点： [提案契约](references/panel-proposal-contract.md)
- 柜体板/背板目录、工艺卡和角色绑定： [料档与工艺卡](references/sheet-stock-catalog.md)
- 背板模式解析、背板基准、内部净深和背拉条约束： [背板结构规则](references/back-construction-rules.md)
- 板件角色、门/层板/踢脚规则和柜型拓扑边界： [板件定义规则](references/panel-definition-rules.md)
- 层板列表、计算层与固定/活动层板物化： [层板规则](references/shelf-planning-rules.md)
- 踢脚区、支撑数量公式和净距： [踢脚规则](references/toe-kick-rules.md)
- 抽屉区尺寸链、适用条件和限制： [抽屉尺寸链](references/drawer-dimension-chain.md)
- 柜型拓扑骨架： `references/cabinet-topologies/`（围合面、有无踢脚、整高抽屉区类型；门/层板/抽屉几何由求解器执行，不能只加 YAML 就支持新柜型）
- 单位审计和优化等旁路证据： [板件旁路分析](references/panel-side-analyses.md)
