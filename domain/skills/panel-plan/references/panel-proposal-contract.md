# 板件提案契约

回答“LLM 需要向 `panel_plan` 阶段提交哪些结构化字段，以及哪些值必须显式给出？”；本文件只定义提案契约，不定义最终板件几何。

## 提交原则

- 提案先由 LLM 基于完整上下文整理并消歧，再作为完整对象写入 `stage_inputs.panels.parameters`。
- 用户没说的构造值，由 LLM 按「LLM 候选起点」写入具体数字或规范枚举，并标成假设；一次打包给用户确认，不要按字段追问。
- 必填字段写入运行时都必须有值。不得把未决定的门数、踢脚高、`back_mount` 写成 `null` 指望代码补。
- 料档字段可省略，由 [料档与工艺卡](sheet-stock-catalog.md) 展开；省略不是 `auto`。
- `null` 只用于 `gap_below_mm`：表示该层是计算层，用剩余内净高闭合尺寸链。不得把踢脚支撑数、门数、`back_mount` 写成 `null` 或 `auto`。
- 除料档工艺卡外，代码不补缺字段、不根据柜型推默认方案、不做自然语言别名识别。
- 规范字段名和单位口径统一按 [术语规范表](terminology-glossary.md)。提案、序列化 spec 和 structure 只接受规范名，不接受历史别名。
- 所有线性尺寸单位均为 mm。
- 超出当前拓扑表达能力的语义必须先继续消歧；停问清单见下文「展示与停止」。

## 完整字段

- 背板与槽：`back_mount`、`back_offset`、`groove_depth`、`groove_clearance`、`back_rail_height`
- 前脸边距与踢脚：`front_face_margin`、`front_gap`、`toe_kick_height`、`toe_kick_reveal_front`、`toe_kick_reveal_back`、`toe_kick_support_count`
- 门与抽屉数量：`n_doors`、`drawer_count`
- 层板：`shelves`、`top_gap_mm`
- 抽屉尺寸链输入：`drawer_side_clearance`、`drawer_layer_gap`、`drawer_back_clearance`
- 可选料档：`board_thickness`、`back_thickness`、`door_thickness`、`drawer_bottom_thickness`、`drawer_back_thickness`；省略则按 [料档与工艺卡](sheet-stock-catalog.md) 展开。
- 柜体身份（可选）：`cabinet_id`；这不是构造字段，运行时在准入前弹出，缺省 cabinet_1，不得包含 __。

## 字段口径

- `shelves` 每项是 `{shelf_type: fixed|movable, gap_below_mm: 数值|null}`；列表顺序、计算层和净高口径见 [层板规则](shelf-planning-rules.md)。运行时不做均分，不保留 `shelf_count`。
- 当前 `drawer_count>0` 的规范语义只表示整高抽屉区；必须同时提交空 `shelves` 与 `n_doors=0`。

## 展示与停止

- 先给出一整份方案：用户已给的值 + 一份假设清单（来自候选起点）。用户没提板厚时，料档只写一行「料板 18 / 卷后背板 9 / 门同料板」，不进假设清单。只问这一句：按这套出板，还是要改门/层板/抽屉/背板安装/踢脚。
- 用户说「就这样」或只改其中几项后，把完整对象写入 `stage_inputs` 再 `run_next()` / `retry_stage()`。代码准入后展示柜体 `id`、`back_mount` requested/effective、内部净空和板件清单（含所属柜体），再等人确认阶段。
- 只有超出当前拓扑表达能力时才停在消歧，不要写入 `stage_inputs`。完整停问清单：混合门/层板/抽屉分区；三门及以上的开启关系。

## LLM 候选起点

用户没说时，LLM 用下面这组值填满必填字段并标成假设。料档按工艺卡省略或覆盖，不能把目录展开当成开放默认值。

- 料档按工艺卡，不写入假设清单：料板 18、卷后背板 9、门与抽屉盒同料板。覆盖时只允许目录值，见 [料档与工艺卡](sheet-stock-catalog.md)。
- `back_mount=groove`、背板后移 18、前脸边距 1.5、前脸深度缝 2、槽深 6、槽余量 1、背拉条高 70。
- 抽屉每侧净空 13、层缝 1.5、后净空 0。
- 落地柜：踢脚 50、前后退让 1/30、2 门、`drawer_count=0`、4 层固定层板。层板净高由 LLM 按内净高均分成数写入 `top_gap_mm` 与各层 `gap_below_mm`（运行时不均分）。踢脚支撑数由 LLM 写出整数：`W < 600 → 0`，否则 `1 + floor((W - 600) / 300)`（800 宽为 1）。
- 吊柜：踢脚 0、前后退让 0、支撑数 0、2 门、`drawer_count=0`、1 层固定层板。同样由 LLM 把顶格与该层下净高等分成数写入。
- 用户要整高抽屉时：`drawer_count` 用其给出的抽数，空 `shelves`、`n_doors=0`、`top_gap_mm=0`，其余仍用上列工艺起点。