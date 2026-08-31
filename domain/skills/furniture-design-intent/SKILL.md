---
name: furniture-design-intent
description: 用于 design_intent 阶段，也是家具流水线的入口。当用户提出"设计一个柜子"、描述想要的家具类型和大致尺寸时触发。只确认家具类别与成品外包络，不提前确认布局、结构、材料或制造细节；非柜类家具只产出 fallback 草稿。
---

# 家具设计意图

阶段：`design_intent`

## 工作流

1. 读取 [家具目录](references/intake/catalog.yaml)，由 LLM 根据用户完整语义把家具描述归一化为 `families` 中的规范 `furniture_type`。归一化按**落位/安装方式**进行：柜类家具中落地的归 `floor_cabinet`、上墙的归 `wall_cabinet`，与功能、外观、所在房间无关。目录中的语言示例不穷举、不得按字符串精确匹配，也不得在运行时代码中实现别名表；无法可靠归类时只生成草稿 fallback，不确认、不进入可执行流水线。
2. 按 [意图采集规则](references/intent-capture-rules.md) 生成 `DesignIntent`。阶段字段只有 `furniture_type`、成品外包络 `overall_size`、吊柜挂装方式 `mount_mode` 与挂高 `mounting_height_mm`，以及工作流元数据；扁平 CLI/API 输入才使用 `type/width/depth/height/mount_mode/mounting_height`。
3. 草稿尺寸可为 `null`；吊柜挂装方式 `mount_mode` 二选一：`free_height`（自由挂高，需挂高 `mounting_height_mm`，底边离地高度）或 `flush_ceiling`（贴顶到顶，无需数字）。确认前只校验：支持的类别、宽/深/高均为正数，以及吊柜挂装方式完整（`free_height` 时挂高为正数）。
4. 展示外包络与吊柜挂装方式并等待确认。门、层板、抽屉、房间位置等进入布局阶段；板厚、背板、踢脚、门缝等进入板件阶段；材料、饰面、连接和五金进入制造阶段。

## 边界

- 运行时仅含 `DesignIntent`（含吊柜挂装方式 `mount_mode` 与挂高 `mounting_height_mm`）、`OverallSize`、目录中的可执行规范类别和外包络校验；不得导入或定义下游 `FurnitureSpec`。运行时只验证 LLM 已归一化的规范类别，不负责理解自然语言名称。
- CLI/API 完整请求由 `furniture_workflow/input_adapter.py` 拆成 `DesignIntent` 与 `stage_inputs`；下游参数保存在对应阶段输入中，不进入 `DesignIntent`。
- 意图变化用 `FurnitureOrchestrator.revise()` 新建 Revision；不得另建规格、状态机或入口。
- 本阶段的阻塞项只允许是类别、外包络尺寸或吊柜挂装方式。
