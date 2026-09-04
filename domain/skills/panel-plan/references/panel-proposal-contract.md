# 板件提案契约

回答“LLM 需要向 `panels_planned` 阶段提交哪些结构化字段，以及哪些值必须显式给出？”；本文件只定义提案契约，不定义最终板件几何。

## 提交原则

- 提案先由 LLM 基于完整上下文整理并消歧，再作为完整对象写入 `stage_inputs.panels.parameters`。
- 代码不补缺字段、不根据柜型推默认方案、不做自然语言别名识别。
- 规范字段名、兼容别名和单位口径统一按 [术语规范表](terminology-glossary.md)。
- 所有线性尺寸单位均为 mm。
- `toe_kick_support_count=null` 与 `back_mount=auto` 都是显式结构化请求，不是运行时缺省。
- 混合门/层板/抽屉分区、多门开启关系或其它超出当前拓扑表达能力的语义，必须先继续消歧。

## 完整字段

- 柜体与门板厚度：`board_thickness`、`back_thickness`、`door_thickness`
- 背板与槽：`back_mount`、`back_offset`、`groove_depth`、`groove_clearance`、`back_rail_height`
- 前脸边距与踢脚：`front_face_margin`、`door_hinge_gap`、`toe_kick_height`、`toe_kick_reveal_front`、`toe_kick_reveal_back`、`toe_kick_support_count`
- 门与抽屉数量：`n_doors`、`drawer_count`
- 单门铰链侧：`door_hinge_side`
- 层板：`shelves`、`top_gap_mm`、`movable_shelf_connector`
- 抽屉尺寸链输入：`drawer_side_clearance`、`drawer_layer_gap`、`drawer_bottom_thickness`、`drawer_back_thickness`、`drawer_back_clearance`

## 字段口径

- `shelves` 按从上到下的视觉顺序排列；每项是 `{shelf_type: fixed|movable, gap_below_mm: 数值|null}`。
- `gap_below_mm` 表示“本层板底面到下方紧邻一层顶面”的净高；最下层到底板顶面，顶格由 `top_gap_mm` 表示。
- 恰好一项 `gap_below_mm` 可为 `null`/`auto`，表示计算层；运行时不做均分，不保留 `shelf_count`。
- `n_doors=1` 时必须显式提交 `door_hinge_side=left/right`；其它门数必须显式提交 `null`。
- `movable_shelf_connector` 的显式枚举为 `two_in_one` 或 `shelf_pin`；无偏好时只能由 LLM 提议候选，不得由代码静默补齐。
- 当前 `drawer_count>0` 的规范语义只表示整高抽屉区；必须同时提交空 `shelves` 与 `n_doors=0`。

## LLM 候选起点

- 柜体/门板 18、背板 9、背板后移 18、前脸边距 1.5、铰链深度缝 2、槽深 6、槽余量 1、背拉条高 70。
- 抽屉每侧净空 13、层缝 1.5、底/背板厚 18、后净空 0。
- 落地柜可从 50 高踢脚、4 层板、2 门起步；吊柜可从无踢脚、1 层板、2 门起步。
- 以上都只是 LLM 候选起点，必须结合需求逐字段确认，不能当作运行时默认值。