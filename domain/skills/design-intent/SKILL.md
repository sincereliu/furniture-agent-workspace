---
name: design-intent
description: 用于 design_intent 阶段，也是家具流水线的入口。当用户提出"设计一个柜子"、描述想要的家具类型和大致尺寸时触发。只确认家具类别与成品外包络，不提前确认布局、结构、材料或制造细节；非柜类家具只产出 fallback 草稿。
---

# 家具设计意图

阶段：`design_intent`

**本阶段只回答一个问题：做哪类家具、占多大外部空间（外包络）？** 产物是一份待确认的 `DesignIntent` 草稿；布局、结构、材料、制造都不在此阶段，由后续阶段接管。

## 工作流

1. **归一化类别**：读 [家具目录](references/intake/catalog.yaml)，按完整语义把描述归到 `families` 中的规范 `furniture_category`。拿不准就只出 fallback 草稿，不确认、不进可执行流水线。
2. **生成草稿**：字段只有 `furniture_category`、成品外包络 `finished_envelope`、吊柜挂装方式 `hanging_mode` 与挂高 `hanging_height_mm`、以及工作流元数据。
3. **预校验**：草稿尺寸可为 `null`；确认前只查——类别已归一化、宽/深/高均为正数、吊柜挂装完整（自由挂高时挂高为正数）、地柜挂装字段为空。
4. **展示并等确认**：只展示外包络与挂装方式。用户没给的值标成假设；缺尺寸或吊柜挂装时先追问，不要编造后当作已确认事实。

## 本阶段不做什么

- 门、层板、抽屉、板厚、背板、踢脚 → 板件阶段
- 房间摆放、靠墙居中、碰撞 → 独立 `layout-plan`，不是本流水线前置
- 制造（材料/饰面/五金…）→ 制造阶段

归一化判据、挂装方式取值与挂高基准、以及不在本阶段捕获的完整清单，见 [意图采集规则](references/intent-capture-rules.md)。

## 边界

- 运行时仅含 `DesignIntent`（含吊柜挂装方式 `hanging_mode` 与挂高 `hanging_height_mm`）、`FinishedEnvelope`、目录中的可执行规范类别和外包络校验；不得导入或定义下游 `FurnitureSpec`。
- CLI/API 完整请求由 `furniture_workflow/input_adapter.py` 拆成 `DesignIntent` 与 `stage_inputs`。扁平的 `furniture_category`、宽深高、挂装方式和挂高映射为设计意图的规范字段；门数、板厚等下游参数写入对应阶段输入，不进入 `DesignIntent`。
- 意图变化用 `FurnitureOrchestrator.revise()` 新建 Revision；不得另建规格、状态机或入口。
- 本阶段的阻塞项只允许是类别、外包络尺寸或吊柜挂装方式。
