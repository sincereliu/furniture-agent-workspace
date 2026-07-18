---
name: furniture-design-intent
description: 将家具需求整理为可确认的设计意图。适用于讨论家具类别、尺寸、用途、风格、约束、默认值和未决问题；交互式工作在 design_intent 阶段暂停，不进入布局或 CAD。
---

# 家具设计意图

阶段：`design_intent`

把用户语言转换为 FurnitureOrchestrator 可接受并由用户确认的 DesignIntent。

## 工作流

1. 读取 [家具目录](references/intake/catalog.yaml)，匹配家具类别；无匹配时使用 fallback，但不得声称该类别可执行。
2. 读取 [设计意图约定](references/design-intent.md)，整理类别、尺寸、用途、风格、约束、假设和未决问题。
3. 可执行输入默认值以 `scripts/furniture_design_intent/design_spec.py` 的实时定义为准，包括：
   - `board_thickness`（18mm）、`back_thickness`（9mm）、`door_thickness`（18mm）
   - `back_offset`（18mm）、`door_margin`（1.5mm）、`door_hinge_gap`（2mm）
   - `back_mount`（`auto`）、`back_rail_height`（70mm）
4. 本阶段只记录用户明确给出的结构偏好和参数覆盖，不计算板件或加工：
   - `toe_kick_reveal_front/back` 传递给布局阶段形成踢脚空间区域；
   - `toe_kick_support_count` 传递给板件阶段决定支撑板数量；
   - `back_mount` 接受 `auto/groove/insert/cover`，`auto` 的解析结果必须作为假设展示；
   - `groove_depth/groove_clearance/back_rail_height` 只约束入槽策略，下游分别负责板件和制造语义。
5. 在确认前通过 `scripts/furniture_design_intent/validation.py` 调用实时 `FurnitureSpec.validation_errors()`，按有效背板模式拒绝无效值、越界结构和没有净空的区域。
6. 展示 `design_intent` 阶段输出并等待确认。不得自行进入布局、板件、制造、特征树或 CAD。

## 边界

- 本阶段运行时代码位于 `scripts/furniture_design_intent/`。
- 扁平协议输入转换和本阶段校验分别由 `translation.py`、`validation.py` 拥有，Orchestrator 不重复实现字段归一化或意图规则。
- 设计意图变化时，由 `FurnitureOrchestrator.revise()` 创建新 Revision。
- 不在本技能中定义第二套规格、状态机或运行时入口。
- 只问至多一个真正阻塞后续阶段的问题；其余不确定项作为显式假设返回。
