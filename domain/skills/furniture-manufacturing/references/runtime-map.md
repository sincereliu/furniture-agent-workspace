# 运行时映射（制造阶段）

本参考集中说明 `SKILL.md` 工作流背后的运行时结构与校验职责；LLM 走业务流时不必逐条记忆，核对实现或规划演进时再读。

## 五金连接件（`connectors/`）

- 基类 `Connector` 定义统一接口：`match()`、`generate_holes()`、`generate_holes_for_panels()`、`boms()`、`machining_operations()`。
- 具体连接件：`TrinityConnector`（三合一）、`HingeConnector`（铰链）、`ShelfConnector`（层板）、`BackMountConnector`（背板）、`DrawerSlideConnector`（滑轨）。
- 新增五金：实现对应 `Connector` 并注册进 `ALL_CONNECTORS`。
- 孔位用 `HoleSpec` 描述；`is_face_hole=True` 表示板面钻孔（导出 TypeNo=1 垂直孔），`False` 表示板边钻孔（TypeNo=2 水平孔）。
- 旧数据缺省 `door_hinge_side` 时，`HingeConnector` 按门板位置回退。

## 生成与产物

- 单板规则实现 `generate_holes()`；需要配合板时覆盖 `generate_holes_for_panels()` 生成成对孔。
- `estimate_hardware()` 与 `emit_drilled_holes()` 遍历 `ALL_CONNECTORS` 生成 BOM 与可序列化的全局/local 孔位数据。
- 实际 `.drilled-holes.json` / `.glb` 文件由 CAD 阶段 `workflow_artifact_writer.py` 写入；制造阶段只产出结构化孔位数据。

## 背板槽机制

- `groove` 为左右侧板、顶/底板生成 4 条目标明确的 `cut_box`；槽宽 = `back_thickness + groove_clearance`，槽深 = `groove_depth`。
- `insert` 输出四边三合一成对孔；cover 外盖螺钉与 groove 背拉条螺钉属组装现场工艺，不生成孔位与五金。

## 校验职责

- `validation.py`：BOM、每条槽是否落在目标板件包络内、铰链孔位置/进刀面/深度、背板五金和配合孔。
- `hole_validator.py`：孔位几何（边界/深度/干涉）。深度按打孔方向的板件尺寸判定（端面钻入的连接杆/预孔可大于板厚）；正交配合孔（三合一杆↔轮）不判干涉。

## 演进中需求（待评审）

- 连接点级实体（杆/轮/螺母按连接点整体增删、校验按连接点对齐）：`references/connection-point-design.md`。
- 完整抽屉组件（门+抽屉混合区、托底轨、有面板）：`references/drawer-component-design.md`。

## 相关契约

- 坐标命名约定：`references/coordinate-naming.md`
- 六面钻导出（仅用户要求出机床文件时）：`references/six-side-drill-export.md`
