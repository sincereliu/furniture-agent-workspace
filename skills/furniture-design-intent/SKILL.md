---
name: furniture-design-intent
description: 用于 design_intent 阶段；将家具需求整理为可确认的类别、尺寸、用途、风格、约束、默认值和未决项，不做布局或 CAD。
---

# 家具设计意图

阶段：`design_intent`

## 工作流

1. 用 [家具目录](references/intake/catalog.yaml) 匹配类别；无匹配则走 fallback，且不声称可执行。
2. 按 [意图采集规则](references/intent-capture-rules.md) 生成可确认的 `DesignIntent`。
3. 默认值以 `scripts/furniture_design_intent/design_spec.py` 为准：板/背板/门厚 `18/9/18mm`，`back_offset=18`、`door_margin=1.5`、`door_hinge_gap=2`、`back_mount=auto`、`back_rail_height=70`。
4. 只记录结构偏好和覆盖值，不计算板件/加工：`toe_kick_reveal_front/back` 交给布局，`toe_kick_support_count` 交给板件；`back_mount` 接受 `auto/groove/insert/cover` 并展示 `auto` 解析假设；`groove_depth/groove_clearance/back_rail_height` 仅约束入槽下游。
5. 确认前由 `scripts/furniture_design_intent/validation.py` 调用实时 `FurnitureSpec.validation_errors()`，拒绝无效值、越界结构和零净空。
6. 展示阶段输出并等待确认，不进入下游。

## 边界

- 运行时在 `scripts/furniture_design_intent/`；`translation.py` 归一化协议输入，`validation.py` 校验，Orchestrator 不重复实现。
- 意图变化用 `FurnitureOrchestrator.revise()` 新建 Revision；不得另建规格、状态机或入口。
- 至多询问一个阻塞项，其余不确定性写为显式假设。
