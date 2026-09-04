# 踢脚规则

回答“`panels_planned` 阶段如何从踢脚参数生成踢脚区域、前后踢脚板与支撑板？”；本文件是踢脚公式与板件物化的唯一规则中心。

## 适用范围

- 适用于 `base.type=toe_kick` 的柜型拓扑。
- 吊柜等无踢脚柜型不适用本文件中的板件生成规则。

## 输入字段

- `toe_kick_height`
- `toe_kick_reveal_front`
- `toe_kick_reveal_back`
- `toe_kick_support_count`
- `board_thickness`
- `structure.internal_width`
- `structure.carcass_y_start`
- `structure.carcass_y_end`
- `structure.toe_kick_rear_y`
- `structure.toe_kick_front_y`

## 支撑数量规则

- 若 `toe_kick_height = 0`，则不生成踢脚支撑。
- 若 `toe_kick_support_count` 是显式整数，则直接使用该值。
- 若提案显式提交 `toe_kick_support_count=null`，则调用宽度公式：
  `W < 600 → 0`，否则 `1 + floor((W - 600) / 300)`。

## 净距规则

- 支撑净距按
  `(internal_width - count × board_thickness) / (count + 1)`
  计算。
- 净距必须大于 `0`，否则该提案非法。

## 板件物化

- 始终先生成前踢脚板和后踢脚板。
- 当支撑数量大于 `0` 时，再在前后踢脚板之间等距布置支撑板。
- 支撑板的 X 起点为 `internal_x_start + clear_spacing + i × (board_thickness + clear_spacing)`。

## 样例

标准落地柜 `800 × 600 × 1000 mm`、板厚 `18`、踢脚高 `50`、显式 `toe_kick_support_count=null` 时：

- 内部净宽 `764`
- 自动支撑数量 `1`
- 支撑净距 `373`
- 唯一支撑板的 X 起点 `391`
- 支撑板的 Y 尺寸 `513`

该样例对应仓库现有回归输入，可直接由运行时和测试重现。