---
name: furniture-panel-planning
description: 用于 panels_planned 阶段。在已确认成品外包络上理解并提议门、层板、抽屉、板厚、背板、踢脚和净空方案，经结构化代码准入后生成可审查的实体板件；不负责房间摆放或制造策略。
---

# 家具板件规划

阶段：`panels_planned`

## 工作流

1. 只要求 `design_intent` 已确认；独立 `furniture-layout` 结果不是前置条件。
2. 由 LLM 根据完整上下文理解需求、消歧并推荐方案；展示未明确值的假设，不在脚本里做关键词识别、同义词映射或开放方案排序。
3. 把选定草稿的全部规范字段写入 `stage_inputs.panels.parameters`。缺字段不得由代码静默补齐；`toe_kick_support_count=null` 和 `back_mount=auto` 必须是显式结构化值。
4. 由 `FurnitureSpec.from_intent()` 校验意图确认状态、字段完整性/类型和客观结构冲突，首次物化完整规范。混合门/层板/整高抽屉语义无法由当前拓扑表达时先继续消歧，不得让运行时丢弃字段。
5. 依据 [背板结构规则](references/back-construction-rules.md) 对显式 `back_mount=auto` 做确定性解析，生成精确 `CabinetStructure`：柜体前后范围、内部 X/Y/Z 净空、背板基准和踢脚区域。
6. 按 [板件定义规则](references/panel-definition-rules.md) 与 `references/cabinet-topologies/` 柜型拓扑生成实体板件；仅入槽背板生成背拉条。抽屉几何只消费已准入的板件字段，不读取制造五金目录来选择净空。
7. `panel_rules.py` 统一计算显式请求自动计算的踢脚支撑、背拉条数量及净距；生成器和校验器必须共用。
8. 输出 `spec/structure/back_mount_resolution/panels`；校验结构规格、精确净空、板件标识/尺寸/位置/依赖和背板几何。展示后暂停，等待用户确认；未通过不得进入制造、BOM、特征树或 CAD。
9. 用户要求尺寸链、单位或公差审计时，先读 `../../external/scientific-agent-skills/skills/uncertainty-and-units/SKILL.md`，再用 `scripts/furniture_panel_planning/quantitative_audit.py` 对当前输出生成 `stage_analyses.panels_planned.panel_unit_audit`；不得据此静默改板件。
10. 用户要求在材料用量、内部空间和复杂度间优化时，先读 `../../external/scientific-agent-skills/skills/pymoo/SKILL.md`，由 LLM 明确目标与候选变量，再用 `design_optimization.py` 生成有来源摘要的 Pareto 候选。只有用户选中候选后才用 `revise_stage_output()`。

## 提案

- 完整参数包括数量 `shelf_count/n_doors/drawer_count` 与单门铰链侧 `door_hinge_side`（`n_doors=1` 时必填 `left/right`，其余显式 `null`），活动层板连接方式 `movable_shelf_connector`（`two_in_one`/`shelf_pin`），主体厚度，背板模式/偏移/槽/背拉条，门缝与踢脚，以及五项抽屉净空/厚度；单位均为 mm。自然语言说明留在交互中。
- 常见提议起点可采用柜体/门板 18、背板 9、背板后移 18、门边缝 1.5、铰链深度缝 2、槽深 6、槽余量 1、背拉条高 70；抽屉每侧净空 13、层缝 1.5、底/背板厚 18、后净空 0。落地柜可从 50 高踢脚、4 层板/2 门起步，吊柜可从无踢脚、1 层板/2 门起步。它们只是 LLM 候选，须结合需求逐字段确认。
- `toe_kick_support_count=null` 是显式请求宽度公式，`back_mount=auto` 是显式请求厚度公式，均不是运行时缺省。混合门/抽屉、分区柜或多门开启关系超出当前拓扑时继续消歧。
- `movable_shelf_connector` 是活动层板连接方式的显式枚举（`two_in_one`=二合一、`shelf_pin`=隔板钉）；无偏好时提议 `two_in_one` 作为待确认默认，不得由代码静默补齐。

## 边界

- 运行时在 `scripts/furniture_panel_planning/`；`panel_spec.py` 只拥有规范 schema、完整性/客观不变量准入和背板模式解析，`structure_planning.py` 是精确净空的唯一所有者。代码不得按自然语言、柜型或内置 profile 选择方案。
- 板件须有稳定标识、角色、尺寸、位置和材料角色；本阶段输出是后续制造所用的已确认 `FurnitureSpec` 来源。
- 旧持久化 Project 缺少 `spec.door_hinge_side` 时只做有界 schema 迁移：单门仅从唯一门板已有的显式 `left/right` 恢复，缺失或冲突即停止；标准双门的规格迁移为 `null`，板件缺省侧按确定性左右拓扑恢复；更多门保持 `null`。新提案和扁平 API 契约仍必须显式提交该字段，迁移不得猜测新的单门偏好。
- 修改规划用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此阶段确定连接件孔位、封边细节、最终 BOM 或 CAD 操作。
- 单位审计和优化报告属于可重跑的旁路证据；`panels_planned` 仍是唯一板件事实来源。
