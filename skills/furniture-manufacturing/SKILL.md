---
name: furniture-manufacturing
description: 用于 manufacturing_planned 阶段。当用户说"用什么五金""三合一连接件""铰链怎么装""封边怎么做""出BOM清单""打孔位置"时触发。根据已确认板件制定材料、封边、连接、五金、孔位和 BOM，不构造特征树或 CAD。
---

# 家具制造策略

阶段：`manufacturing_planned`

## 工作流

1. 要求设计意图、布局和板件规划均已确认。
2. 按 [制造规则](references/manufacturing-rules.md) 确定材料、封边、连接、五金、孔位、公差和 BOM 假设；整份方案用 `readiness=preliminary/accepted/factory_ready` 表示接受程度，默认 `preliminary`。
3. 五金规格以 `scripts/furniture_manufacturing/hardware_catalog.yaml` 和 `hardware_rules.yaml` 为准。
4. `connectors/` 集中连接/打孔逻辑：`Connector` 基类及 `TrinityConnector`、`HingeConnector`、`ShelfConnector`、`BackMountConnector`、`DrawerSlideConnector`。新五金新增 Connector 并注册 `ALL_CONNECTORS`。
    各连接件通过 `HoleSpec` 描述孔位，`is_face_hole=True` 表示板面钻孔 (TypeNo=1 垂直孔)，`False` 表示板边钻孔 (TypeNo=2 水平孔)。三合一在高度方向按系统 32 排钻规则分布，深度方向前后双排。
    （已记录需求：连接点级实体——杆/轮/螺母按连接点整体增删、校验按连接点对齐，见 `references/connection-point-design.md`；抽屉组件级实体——抽屉子装配+滑轨契约，见 `references/drawer-component-design.md`；实施前均需评审。）
5. 单板规则实现 `generate_holes()`；需配合板时覆盖 `generate_holes_for_panels()` 生成成对孔。`estimate_hardware()` 与 `emit_drilled_holes()` 遍历 `ALL_CONNECTORS` 生成 BOM 和可序列化的全局/local 孔位数据；实际 `.drilled-holes.json/.glb` 文件由 CAD 阶段的 `workflow_artifact_writer.py` 写入。
6. 六面钻 XML 导出由 `export_six_side_drill.py` + `devices/six_side_drill_guigui.yaml` 完成。设备映射 yaml 按面板类型定义 `sixd_x_from_box`/`sixd_y_from_box`（机床轴）和 `x1_from_hole`/`y1_from_hole`/`z1_from_hole`（局部坐标→机床坐标）；水平孔方向须从世界轴转换为机床轴后再确定 Quadrant。导出层从 `HoleSpec.is_face_hole` 直接读取 TypeNo，不再推导。板件轮廓 `PanelOutline` 顶点严格按 `(0, sixd_y) → (0, 0) → (sixd_x, 0) → (sixd_x, sixd_y)` 逆时针闭合。
7. `groove` 为左右侧板、顶/底板生成 4 条目标明确的 `cut_box`：槽宽 `back_thickness + groove_clearance`，槽深 `groove_depth`。`insert` 输出四边三合一成对孔。cover/背拉条的螺钉连接属组装现场工艺，不生成孔位与五金。
8. 入槽背板不封边；其他背板及背拉条四边封边。未经明确
   接受不得把 `readiness` 提升为 `accepted`，未经工厂确认不得提升为
   `factory_ready`。
9. 厚度来自 `panels_planned.spec` 中已确认的 `FurnitureSpec`，不得从意图重建或硬编码覆盖。单门和标准双门由板件规划
   显式写入 `door_hinge_side="left"/"right"`；旧数据缺省时
   `HingeConnector` 才按位置回退。杯孔只从门板内侧钻入，`direction` 为钻入方向（`inner_face` 的反向），Y1 =
   `edge_offset + cup_diameter/2`，为杯孔中心到门边的距离。
10. 用 `FurnitureOrchestrator.run_next()` 生成；`scripts/furniture_manufacturing/validation.py` 校验 BOM、每条槽是否落在目标板件包络内、铰链孔位置/进刀面/深度、背板五金和配合孔；孔位几何（边界/深度/干涉）由 `hole_validator.py` 校验——深度按打孔方向的板件尺寸判定（端面钻入的连接杆/预孔可大于板厚），正交配合孔（三合一杆↔轮）不判干涉，展示后暂停。
11. 规划样件、承重、连接件或涂装对比试验时，先读 `../../external/scientific-agent-skills/skills/experimental-design/SKILL.md`，再用 `prototype_experiment.py` 生成带种子、区组和真实重复层级的试验表。
12. 分析已采集试验数据时，先读 `../../external/scientific-agent-skills/skills/statistical-analysis/SKILL.md`，再用 `test_statistics.py` 输出描述统计、假设检查、效应量和适用的推断；不得把未采集的计划数据当结果。
13. 分析板件加工路线、共享设备、齐套装配、工位排队或交期时，先读 `../../external/scientific-agent-skills/skills/simpy/SKILL.md`，再用 `production_simulation.py` 运行有界板件级模型；报告模型假设、种子、复制次数、未完成实体和引擎。

## 边界

- 运行时在 `scripts/furniture_manufacturing/`。
- 修改制造策略时使用 `revise_stage_output()`，使本阶段及下游失效。
- `readiness` 作用于整份制造方案/BOM，不伪装成每条五金或封边记录均已单独审批。
- 不发射特征树、不调用 CAD Bridge、不手改派生产物。
- 试验、统计和生产仿真写入 `stage_analyses.manufacturing_planned`，只提供证据或候选；它们不自动提升 `readiness`，不直接修改 BOM，也不构成现实工厂因果结论。
