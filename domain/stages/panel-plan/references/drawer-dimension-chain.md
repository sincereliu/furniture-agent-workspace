# 抽屉尺寸链

回答“当前仓库在 `panel_plan` 阶段如何把已准入的抽屉字段转成整高抽屉区板件几何？”；本文件是抽屉尺寸链的唯一规则中心。

## 适用范围

- 仅适用于当前仓库已支持的 `drawer_count>0` 语义：整高抽屉区。
- 该语义要求 `shelves=[]` 且 `n_doors=0`。
- 抽屉几何只消费已准入的板件字段，不读取下游目录来猜测净空。

## 输入字段

- `drawer_count`
- `drawer_side_clearance`
- `drawer_layer_gap`
- `drawer_bottom_thickness`（准入后等于柜体板厚）
- `drawer_back_thickness`（准入后等于柜体板厚）
- `drawer_back_clearance`
- `front_face_margin`
- `board_thickness`
- `structure.internal_width`
- `structure.internal_height`
- `structure.internal_y_start`
- `structure.internal_y_end`

## 当前执行口径

盒体与抽面**各算各的**：盒高由格高减上下间隙、抽面仍按带高减层缝。滑轨系统的数值
（档位、间隙、轨腔）见 [抽屉滑轨规则](drawer-runner-rules.md)。

- 每层抽屉带高（=格高） `band_h = internal_height / drawer_count`
- 抽面高 `front_h = band_h - drawer_layer_gap`；抽面宽 `front_w = internal_width - 2 × front_face_margin`
- 抽面 Z 起点按抽屉带自下而上布置；首层不追加层缝，其余层在带起点额外加入 `drawer_layer_gap`
- 上下间隙由格高查表：`下间隙, 上间隙 = cell_gaps(runner, band_h)`
- 盒体高 `box_h = (band_h - 下间隙 - 上间隙)` 向下取到 10 的整数倍，余量进上间隙
- 盒体 Z 起点 `box_z = 格起点 + 下间隙`；底板 Z `box_z + 轨腔高度`
- 盒体宽 `box_w = internal_width - 2 × drawer_side_clearance`
- 可装深度 `= 内深 - board_thickness`（内嵌：抽面占一块板厚）
- 盒体深 `box_d` 取抽芯档里满足「可装深度 − 档 > 后缝下限」的最大一档；`drawer_back_clearance` 是最小要求，实际后缝 `= 可装深度 - box_d`
- 底板 Y 向尺寸 `bottom_size_y = box_d - drawer_back_thickness`
- 背板通高到盒底（贴底板端面），不坐在底板上

## 来源与校准状态

- 当前规则来源是仓库内的执行契约：`topology_solver.py` 负责按已准入字段生成抽屉板件，`panel_fixtures.py` 提供稳定样例输入。
- 这些规则目前是“仓库规范化口径”，不是车间试装记录或量产工艺卡的替代品。
- 仓库里尚未保存真实试产数据；因此本文件当前只做到“样例校准 + 可执行测试”，不能宣称已完成工厂实测校准。
- 如果后续引入实物样柜或厂内标准图作为依据，应先更新本文件，再同步更新代码与测试。

## 样例校准

标准样例：落地柜 `800 × 600 × 1000 mm`，`board_thickness=18`，`back_thickness=9`，`toe_kick_height=50`，`drawer_count=3`，`drawer_side_clearance=13`，`drawer_layer_gap=1.5`，`drawer_back_clearance=0`，`front_face_margin=1.5`。

- 内部净宽 `764`
- 内部净高 `914`
- 内部净深 `553`
- 每层抽屉带高 `304.667`
- 抽屉前板尺寸 `761 × 18 × 303.167`
- 抽屉盒体深 `535`
- 抽屉底板尺寸 `702 × 517 × 18`
- 底抽左侧板尺寸 `18 × 535 × 267.167`，位置起点 `31, 27, 86`
- 第二层抽屉前板位置起点 `19.5, 562, 374.167`
- 第三层抽屉前板位置起点 `19.5, 562, 678.833`

## 板件结果

- 每层生成前板、左右侧板、后板和底板，写入该抽屉子装配的 `box.panels`。
- 当前无独立抽面：前板即盒体前脸，`front_id` 指向该前板；本阶段只写尺寸、位置和盒内接触。
- 侧板、后板和底板只表达几何、位置、材料角色和装配依赖。

## 限制与后续

- 本文件记录的是当前仓库执行口径，便于把抽屉规则从入口文档中独立出来。
- 变体（三节轨/托底轨）的出件口径见 [抽屉滑轨规则](drawer-runner-rules.md)；本文件只写链条顺序。
- 混合门抽屉区、分区抽屉、异形前脸、覆盖方式差异等未被当前拓扑支持时，必须在 LLM 侧继续消歧，不得由运行时猜测。