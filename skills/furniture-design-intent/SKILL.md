---
name: furniture-design-intent
description: 用于 design_intent 阶段；只确认家具类别与成品外包络，不提前确认布局、结构、材料或制造细节。
---

# 家具设计意图

阶段：`design_intent`

## 工作流

1. 用 [家具目录](references/intake/catalog.yaml) 匹配 `furniture_type`；无匹配则只生成草稿 fallback，不确认、不进入可执行流水线。
2. 按 [意图采集规则](references/intent-capture-rules.md) 生成 `DesignIntent`。阶段字段只有 `furniture_type`、成品外包络 `overall_size` 和工作流元数据；扁平 CLI/API 输入才使用 `type/width/depth/height`。
3. 草稿尺寸可为 `null`；确认前只校验支持的类别以及宽、深、高均为正数。
4. 展示外包络并等待确认。门、层板、抽屉、房间位置等进入布局阶段；板厚、背板、踢脚、门缝等进入板件阶段；材料、饰面、连接和五金进入制造阶段。

## 边界

- 运行时仅含 `DesignIntent`、`OverallSize` 和外包络校验；不得导入或定义下游 `FurnitureSpec`。
- CLI/API 完整请求由 `furniture_workflow/input_adapter.py` 拆成 `DesignIntent` 与 `stage_inputs`；下游参数保存在对应阶段输入中，不进入 `DesignIntent`。
- 意图变化用 `FurnitureOrchestrator.revise()` 新建 Revision；不得另建规格、状态机或入口。
- 本阶段的阻塞项只允许是类别或外包络尺寸。
