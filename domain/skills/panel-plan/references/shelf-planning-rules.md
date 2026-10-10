# 层板规则

回答“`panel_plan` 阶段如何解释层板列表、计算层以及固定/活动层板板件？”；本文件是层板尺寸链与层板物化的唯一规则中心。

## 适用范围

- 仅适用于当前仓库以 `shelves` 列表表达的柜内层板。
- `shelves` 按从上到下的视觉顺序排列。
- 当前规则不表达分区隔板、挂衣区或开放格组合；超出当前拓扑表达能力的语义必须先继续消歧。

## 输入字段

- `shelves`
- `top_gap_mm`
- `board_thickness`（柜体板厚；层板不单独立项）
- `structure.internal_height`
- `structure.internal_width`
- `structure.internal_y_start`
- `structure.internal_y_end`

## 列表语义

- 每项 `gap_below_mm` 表示“本层板底面到下方紧邻一层顶面”的净高。
- 最下层的 `gap_below_mm` 指到底板顶面。
- 顶格单独由 `top_gap_mm` 表示。
- 恰好一项 `gap_below_mm` 可为 `null`，且 `top_gap_mm` 已写成数时，表示计算层；运行时用剩余内部净高求出该层，不对其余层做均分。

## 省略时的均分

提案不要写均分后的毫米。至少一块层板，每一层的 `gap_below_mm` 都没给（键不存在或值为 `null`），并且没写 `top_gap_mm` 时，准入展开为均分：

- 内部净高 = 外形高 − 踢脚高 − 2 × 柜体板厚。与 `CabinetStructure.from_spec` 相同。
- 每格净高 = (内部净高 − 层数 × 柜体板厚) / (层数 + 1)。这个数写入 `top_gap_mm` 和每一层 `gap_below_mm`。
- 结果小于 0 则提案非法。
- 展开后的 spec 和冻结文件带具体毫米。`from_dict()` 不重算。
- 已经写出顶格，或写出了任一格净高时，不均分。

## 计算规则

- 若存在且仅存在一项 `gap_below_mm=null`，则
  `computed_gap = internal_height - top_gap_mm - N × board_thickness - 其余显式净高之和`
- 若没有计算层，则要求
  `top_gap_mm + N × board_thickness + 所有 gap_below_mm 之和`
  与 `internal_height` 在 `0.5 mm` 容差内相等。
- 若计算出的 `computed_gap < 0`，则该提案非法。

## 板件物化

- 每块层板的 X 尺寸等于 `internal_width`。
- 每块层板的 Y 尺寸等于 `internal_y_end - internal_y_start`。
- 固定层板生成 `fixed_shelf`，活动层板生成 `movable_shelf`。

## 样例

标准落地柜 `800 × 600 × 1000 mm`、板厚 `18`、踢脚 `50`、4 层固定层板时：

- 内部净高 `914`
- 4 块层板总厚度 `72`
- 顶格与各层下净高相等时，每格净高 `168.4`

整组省略净高时，准入展开出同一组数。该样例也由测试夹具 `panel_fixtures._even_shelves()` 生成，用于保持显式层板样例输入稳定。