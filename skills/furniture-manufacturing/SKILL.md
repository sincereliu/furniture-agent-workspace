---
name: furniture-manufacturing
description: 根据已确认板件规划制定材料、封边、连接、五金、孔位和 BOM 假设。适用于 manufacturing_planned 阶段；输出制造策略后暂停，不直接构造特征树或 CAD。
---

# 家具制造策略

阶段：`manufacturing_planned`

## 工作流

1. 要求设计意图、布局和板件规划均已确认。
2. 读取 [制造策略](references/manufacturing-policy.md)，确定材料、封边、连接方式、五金、孔位规则、公差和 BOM 假设。
3. 五金规格以 `scripts/furniture_manufacturing/hardware_catalog.yaml` 和 `hardware_rules.yaml` 为准。
4. 打孔和匹配逻辑集中在 `connectors/` 模块中（基类 `Connector`，子类 `TrinityConnector` / `HingeConnector` / `ShelfConnector` / `BackMountConnector`）。新增五金只需新建一个 Connector 文件并注册到 `ALL_CONNECTORS`，无需改动其他代码。
5. 单板连接件实现 `generate_holes()`；需要配合板几何的连接件覆盖 `generate_holes_for_panels()`，同时生成连接双方的匹配孔。`manufacturing_bom.py` 的 `estimate_hardware()` 遍历 `ALL_CONNECTORS` 生成 BOM；`emit_drilled_holes()` 遍历 `ALL_CONNECTORS` 生成孔位 JSON（含全局坐标和板自身 local 坐标）；`drilled_holes_glb.py` 将孔位导出为彩色 GLB 标记。
6. 入槽背板生成左侧板、右侧板、顶板、底板 4 条目标明确的 `cut_box` 加工记录；槽宽 = `back_thickness + groove_clearance`，槽深 = `groove_depth`。
7. 三种背板安装模式必须输出各自的制造语义：`groove` 输出背板槽和背拉条端部连接；`insert` 输出四边三合一及成对孔；`cover` 输出周边沉头螺钉及背板/柜体成对孔。
8. 非入槽背板和背拉条按仓库统一规则四边封边；入槽背板不封边。外盖螺钉、背拉条螺钉及默认孔距是软件暂定值，BOM 必须注明投产前确认。
9. 材料厚度必须来自确认后的 `FurnitureSpec`，不得用硬编码厚度覆盖用户输入。
10. 门板支持可选字段 `door_hinge_side`（"left"/"right"），未指定时由 `HingeConnector` 根据面板位置自动推断；铰链杯孔只生成在门板上，并从门板内侧面钻入。
11. 通过 `FurnitureOrchestrator.run_next()` 生成制造阶段输出；`scripts/furniture_manufacturing/validation.py` 校验 BOM、加工边界、背板五金和配合孔契约，展示后暂停。

## 关键模块

| 模块 | 作用 |
|------|------|
| `connectors/base.py` | `HoleSpec` / `Connector` 抽象基类 |
| `connectors/trinity.py` | 三合一（偏心轮 φ12×13.5 + 连接杆 φ8×33 + 预埋螺母 φ10×11） |
| `connectors/hinge.py` | 铰链（φ35×13，按门高分档，自适应左右门） |
| `connectors/shelf.py` | 层板托（φ10×12） |
| `connectors/back_mount.py` | 内嵌背板三合一、外盖背板螺钉、背拉条端部螺钉及配合孔 |
| `manufacturing_bom.py` | 管道主入口：`plan_manufacturing` → `BOMReport` |
| `drilled_holes_glb.py` | 孔位 GLB 生成器 |
| `hardware_catalog.yaml` | 五金规格库 |
| `hardware_rules.yaml` | 打孔规则 |

## 边界

- 本阶段运行时代码位于 `scripts/furniture_manufacturing/`。
- 修改制造策略时使用 `revise_stage_output()`，使本阶段及下游失效。
- 不在此技能中发射特征树、调用 CAD Bridge 或手工修改派生产物。
