---
name: furniture-manufacturing
description: 用于 manufacturing_planned 阶段。当用户说"用什么五金""三合一连接件""铰链怎么装""封边怎么做""出BOM清单""打孔位置"时触发。根据已确认板件制定材料、封边、连接、五金、孔位和 BOM，不构造特征树或 CAD。
---

# 家具制造策略

阶段：`manufacturing_planned`

## 工作流

1. 检查前置：`design_intent` 与 `panels_planned` 均已确认；独立 `furniture-layout` 结果不是前置条件。
2. 由 LLM 根据完整上下文理解制造需求，提出整份策略草案，并把未明确的假设逐项列出给用户确认。策略覆盖：
   - 材料：类别、等级、厚度、纹理、可见面、饰面；
   - 封边：封哪些边、封边厚度及余量；
   - 连接：螺钉、木榫、偏心件（三合一/二合一）、槽/企口、胶合；
   - 五金：铰链、滑轨、拉手、层板托、固定、防倾倒及荷载；
   - 公差/净空：门缝、安装/设备缝隙、地墙不平、安全余量。
   口径见 [制造规则](references/manufacturing-rules.md)；不做关键词识别、同义词映射或开放方案排序。
3. 五金变体与打孔参数以 `scripts/furniture_manufacturing/hardware_catalog.yaml`、`hardware_rules.yaml` 为准：LLM 只选变体并把数值假设标为待确认，不硬编码或猜测参数。
4. 把选定策略交 `FurnitureOrchestrator.run_next()` 生成确定性结果（孔位、封边、槽、BOM），由运行时校验；展示整套制造方案，暂停等待用户确认。
5. 整份方案用 `readiness=preliminary/accepted/factory_ready` 表示接受程度，默认 `preliminary`；未经用户明确接受不得升 `accepted`，未经工厂确认不得升 `factory_ready`。

## 关键规则

- 材料厚度、单门/标准双门的铰链侧 `door_hinge_side` 均来自已确认的 `panels_planned` 输出，不从意图重建或硬编码覆盖；旧数据缺省时才按门板位置回退。
- 三合一在高度方向按系统 32 排钻分布、深度方向前后双排；铰链孔、背板槽与背板连接、封边的精确口径见 [制造规则](references/manufacturing-rules.md)。
- 入槽背板不封边；其余背板及背拉条四边封边；cover 外盖螺钉与 groove 背拉条螺钉属组装现场工艺，不生成孔位与五金。
- `readiness` 作用于整份方案/BOM，不伪装成每条五金或封边记录均已单独审批。

## 子流程（按触发词加载，不进主流程）

| 用户提到 | 读取/调用 |
|---------|----------|
| 对照外部五金/加工类目、打孔 | `references/hardware-machining-reference.md` |
| 六面钻、机床加工、导 XML | `references/six-side-drill-export.md` |
| 样件、承重、连接件或涂装对比试验 | `../../external/scientific-agent-skills/skills/experimental-design/SKILL.md` + `prototype_experiment.py` |
| 分析已采集试验数据 | `../../external/scientific-agent-skills/skills/statistical-analysis/SKILL.md` + `test_statistics.py` |
| 板件加工路线、共享设备、齐套装配、工位排队、交期 | `../../external/scientific-agent-skills/skills/simpy/SKILL.md` + `production_simulation.py` |

## 边界

- 运行时在 `scripts/furniture_manufacturing/`；代码契约与演进中需求见 [运行时映射](references/runtime-map.md)。
- 修改制造策略时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不发射特征树、不调用 CAD Bridge、不手改派生产物。
- 试验、统计和生产仿真写入 `stage_analyses.manufacturing_planned`，只提供证据或候选；它们不自动提升 `readiness`，不直接修改 BOM，也不构成现实工厂因果结论。
