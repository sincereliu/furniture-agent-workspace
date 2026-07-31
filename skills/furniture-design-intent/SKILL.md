---
name: furniture-design-intent
description: 用于 design_intent 阶段；将家具需求整理为可确认的类别、尺寸、用途、风格、约束、默认值和未决项，不做布局或 CAD。
---

# 家具设计意图

阶段：`design_intent`

## 工作流

1. 用 [家具目录](references/intake/catalog.yaml) 匹配类别；无匹配则只生成草稿 fallback，不确认、不进入可执行流水线。
2. 按 [意图采集规则](references/intent-capture-rules.md) 生成 `DesignIntent`。阶段字段名为 `furniture_type`；只有扁平 CLI/API 输入使用 `type`。
3. 默认值以 `scripts/furniture_design_intent/design_spec.py` 为准；`back_mount` 接受 `auto/groove/insert/cover`，`back_rail_height` 等字段只作为已确认输入保存，不在此处执行布局、板件或制造校验。
4. 草稿尺寸可为 `null`，缺项写入 `unresolved`；确认前只校验类别、三维尺寸、支持字段及基础类型。`layout.room` 与 `layout.placement` 可分别省略，由布局阶段补齐并标记默认来源。抽屉、隔板分区、滑门、开放格等不能静默忽略，须保留为未决项。
5. 只记录偏好和覆盖值并等待确认：最终内部净空归布局；踢脚支撑间距和背拉条数量归板件；槽包络和铰链孔位归制造；特征树只做防御性复核。

## 边界

- 运行时仅含 `DesignIntent`、已确认输入模型和意图校验；CLI/API 到意图的协议适配位于 `furniture_workflow/input_adapter.py`。
- 意图变化用 `FurnitureOrchestrator.revise()` 新建 Revision；不得另建规格、状态机或入口。
- 至多询问一个阻塞项，其余不确定性写为显式假设。
