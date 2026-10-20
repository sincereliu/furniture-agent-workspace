# 踢脚规则

回答“`panel_plan` 阶段如何从踢脚参数生成踢脚区域、前后踢脚板与支撑板？”；本文件是踢脚公式与板件物化的唯一规则中心。

## 适用范围

- 适用于 `base.type=toe_kick` 的柜型拓扑。
- 吊柜等无踢脚柜型不适用本文件中的板件生成规则。

## 输入字段

- `toe_kick_height`
- `toe_kick_reveal_front`
- `toe_kick_reveal_back`
- `toe_kick_support_count`
- `board_thickness`（柜体板厚；踢脚板与支撑不单独立项）
- `structure.internal_width`
- `structure.carcass_y_start`
- `structure.carcass_y_end`
- `structure.toe_kick_rear_y`
- `structure.toe_kick_front_y`

## 支撑数量规则

- 写出的 `toe_kick_support_count` 必须是非负整数。运行时按这个整数生成支撑板。
- 提案不写该字段时，准入用外形宽 `width` 展开，不用内空宽。踢脚高为 0 则为 0。否则宽小于 600 为 0，其余为 `1 + floor((width - 600) / 300)`。800 宽且有踢脚时为 1，900 宽为 2。
- `null` 拒绝。要指定根数就写非负整数，写出的数保持原值。
- 踢脚高为 0 时，写出的支撑数也必须为 0，并且不生成踢脚支撑。
- 冻结文件必须带这个整数。`from_dict()` 不从柜宽重算。

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

标准落地柜 `800 × 600 × 1000 mm`、板厚 `18`、踢脚高 `50`、`toe_kick_support_count=1` 时：

- 内部净宽 `764`
- 支撑数量 `1`
- 支撑净距 `373`
- 唯一支撑板的 X 起点 `391`
- 支撑板的 Y 尺寸 `513`

该样例对应仓库现有回归输入，可直接由运行时和测试重现。