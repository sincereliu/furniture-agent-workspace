# 抽屉尺寸链

回答“当前仓库在 `panels_planned` 阶段如何把已准入的抽屉字段转成整高抽屉区板件几何？”；本文件是抽屉尺寸链的唯一规则中心。

## 适用范围

- 仅适用于当前仓库已支持的 `drawer_count>0` 语义：整高抽屉区。
- 该语义要求 `shelves=[]` 且 `n_doors=0`。
- 抽屉几何只消费已准入的板件字段，不读取制造五金目录来猜测净空或滑轨型号。

## 输入字段

- `drawer_count`
- `drawer_side_clearance`
- `drawer_layer_gap`
- `drawer_bottom_thickness`
- `drawer_back_thickness`
- `drawer_back_clearance`
- `door_margin`
- `board_thickness`
- `structure.internal_width`
- `structure.internal_height`
- `structure.internal_y_start`
- `structure.internal_y_end`

## 当前执行口径

- 每层抽屉带高 `band_h = internal_height / drawer_count`
- 抽屉前板高 `front_h = band_h - drawer_layer_gap`
- 抽屉前板宽 `front_w = internal_width - 2 × door_margin`
- 盒体宽 `box_w = internal_width - 2 × drawer_side_clearance`
- 盒体深 `box_d = internal_depth - board_thickness - drawer_back_clearance`
- 底板 Y 向尺寸 `bottom_size_y = box_d - board_thickness`
- 抽屉前板的 Z 起点按抽屉带自下而上布置；首层不追加层缝，其余层在带起点额外加入 `drawer_layer_gap`
- 底抽前板按“一块板厚的底板覆盖量”处理，`overlap = board_thickness`；其余抽屉 `overlap = 0`
- 盒体高 `box_h = front_h - 2 × overlap`
- 盒体 Z 起点 `box_z = front_z + overlap`

## 板件结果

- 每层生成前板、左右侧板、后板和底板。
- 前板作为前脸板件参与 `panels_planned` 事实输出；不在本阶段额外选择五金或打孔。
- 侧板、后板和底板只表达几何、位置、材料角色和装配依赖。

## 限制与后续

- 本文件记录的是当前仓库执行口径，便于把抽屉规则从入口文档中独立出来；它不是制造阶段的五金选型规则。
- 如果后续引入实物样柜、厂内标准图或滑轨安装手册作为依据，应先更新本文件，再同步更新代码与测试。
- 混合门抽屉区、分区抽屉、异形前脸、覆盖方式差异等未被当前拓扑支持时，必须在 LLM 侧继续消歧，不得由运行时猜测。