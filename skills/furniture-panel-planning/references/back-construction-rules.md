# 背板结构规则

回答“布局确认后，柜体采用什么背板结构，以及由此得到哪些精确结构尺寸？”；本文件是背板设计的唯一规则中心。

## 阶段输入

- `back_mount`：`auto/groove/insert/cover`，默认 `auto`。
- `board_thickness/back_thickness/door_thickness`。
- `back_offset/door_margin/door_hinge_gap`。
- `groove_depth/groove_clearance/back_rail_height`。

这些值可在完整 CLI/API 请求中提前提交，但只保存在 `stage_inputs.panels.parameters`，直到客户确认布局后才物化为板件阶段 `FurnitureSpec`。

## 模式解析

- `groove/insert/cover` 保持显式选择。
- `auto`：`back_thickness < board_thickness` 时解析为 `groove`，否则为 `insert`。
- 输出必须同时展示 `back_mount_resolution.requested/effective`；下游只消费有效模式。
- `groove_depth/groove_clearance/back_rail_height` 只在有效模式为 `groove` 时生效；其他模式的休眠值不得阻塞板件阶段。

## 精确结构

- 柜体前端统一预留 `door_thickness + door_hinge_gap`，所有板件保持在已确认成品深度内。
- `groove/insert`：柜体从 `Y=0` 开始，背板基准为 `back_offset`，内部 Y 起点为 `back_offset + back_thickness`。
- `cover`：背板位于 `Y=0`，柜体从 `Y=back_thickness` 开始，背板不得与柜体重叠。
- 内部 X/Z 范围由成品外包络、柜体板厚和踢脚高度计算；所有净宽、净高、净深必须为正。

## 背板与背拉条

- `groove`：背板宽高为内部净宽/净高各加 `2×groove_depth`；仅此模式生成背拉条。
- `insert`：背板为内部净宽×内部净高，位于 `back_offset`。
- `cover`：背板为成品宽×成品高，覆盖整个背面。
- 背拉条数量、尺寸、位置和净距属于本阶段；实际槽包络、连接、封边和孔位属于制造阶段。
