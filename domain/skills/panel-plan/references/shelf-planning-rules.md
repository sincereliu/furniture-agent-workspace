# 层板规则

回答“`panels_planned` 阶段如何解释层板列表、计算层以及固定/活动层板板件？”；本文件是层板尺寸链与层板物化的唯一规则中心。

## 适用范围

- 仅适用于当前仓库以 `shelves` 列表表达的柜内层板。
- `shelves` 按从上到下的视觉顺序排列。
- 当前规则不表达分区隔板、挂衣区或开放格组合；超出当前拓扑表达能力的语义必须先继续消歧。

## 输入字段

- `shelves`
- `top_gap_mm`
- `board_thickness`
- `structure.internal_height`
- `structure.internal_width`
- `structure.internal_y_start`
- `structure.internal_y_end`

## 列表语义

- 每项 `gap_below_mm` 表示“本层板底面到下方紧邻一层顶面”的净高。
- 最下层的 `gap_below_mm` 指到底板顶面。
- 顶格单独由 `top_gap_mm` 表示。
- 恰好一项 `gap_below_mm` 可为 `null`/`auto`，表示计算层；运行时用剩余内部净高求出该层，不做均分推断。

## 计算规则

- 若存在且仅存在一项 `gap_below_mm=null`，则
  `auto_gap = internal_height - top_gap_mm - N × board_thickness - 其余显式净高之和`
- 若没有计算层，则要求
  `top_gap_mm + N × board_thickness + 所有 gap_below_mm 之和`
  与 `internal_height` 在 `0.5 mm` 容差内相等。
- 若计算出的 `auto_gap < 0`，则该提案非法。

## 板件物化

- 每块层板的 X 尺寸等于 `internal_width`。
- 每块层板的 Y 尺寸等于 `internal_y_end - internal_y_start`。
- 固定层板生成 `fixed_shelf`，活动层板生成 `movable_shelf`。
- 固定层板使用 `cam_face` 表达可用于连接件的面；活动层板不在本阶段选择连接五金。

## 样例

标准落地柜 `800 × 600 × 1000 mm`、板厚 `18`、踢脚 `50`、4 层固定层板时：

- 内部净高 `914`
- 4 块层板总厚度 `72`
- 顶格与各层下净高相等时，每格净高 `168.4`

该样例由测试夹具 `panel_fixtures._even_shelves()` 生成，用于保持层板样例输入稳定。