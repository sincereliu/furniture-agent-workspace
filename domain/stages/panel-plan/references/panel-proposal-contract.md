# 板件提案契约

回答“LLM 需要向 `panel_plan` 阶段提交哪些结构化字段，以及哪些值必须显式给出？”；本文件只定义提案契约，不定义最终板件几何。

## 提交原则

- 提案先由 LLM 基于完整上下文整理并消歧，再作为完整对象写入 `stage_inputs.panels.parameters`。
- 用户没说的构造值，由 LLM 按「LLM 候选起点」写入具体数字或规范枚举，并标成假设。客户还没接受这些假设时，一次打包问一句，不要按字段追问。客户已经给出或已经接受的值照写，不再询问。
- 必填字段写入运行时都必须有值。不得把未决定的门数、踢脚高、`back_mount` 写成 `null` 指望代码补。
- 料档字段可省略，由 [料档与工艺卡](sheet-stock-catalog.md) 展开；省略不是 `auto`。
- `null` 只用于已经写出的 `gap_below_mm`：恰好一项为 `null`、并且写了 `top_gap_mm` 时，表示计算层，用剩余内部净高闭合这一层。不得把踢脚支撑数、门数、`back_mount` 写成 `null` 或 `auto`。
- `toe_kick_support_count` 可以不写。不写时，准入用该柜外形宽展开：踢脚高为 0 则为 0；否则宽小于 600 为 0，其余为 `1 + floor((width - 600) / 300)`。写出的非负整数保持原值。
- 至少一块层板，且每一层都不写 `gap_below_mm`（键不存在或整组都是 `null`）、同时不写 `top_gap_mm` 时，准入按内部净高均分，写入具体毫米。写出了顶格或任一格净高之后，就走显式尺寸链，不再均分。没有层板时 `top_gap_mm` 仍必填。
- 这两项和料档一样，只在提案准入时展开。冻结文件和 `from_dict()` 必须已经带具体数。除料档、支撑数和整组层板净高外，代码不补缺字段、不根据柜型推默认方案、不做自然语言别名识别。
- 规范字段名和单位口径统一按 [术语规范表](terminology-glossary.md)。提案、序列化 spec 和 interior 只接受规范名，不接受历史别名。
- 所有线性尺寸单位均为 mm。
- 超出当前拓扑表达能力的语义必须先继续消歧；停问清单见下文「展示与停止」。

## 完整字段

- 背板与槽：`back_mount`、`back_offset`、`groove_depth`、`groove_clearance`、`back_rail_height`
- 前脸边距与踢脚：`front_face_margin`、`front_gap`、`toe_kick_height`、`toe_kick_reveal_front`、`toe_kick_reveal_back`、`toe_kick_support_count`
- 门与抽屉数量：`n_doors`、`drawer_count`
- 层板：`shelves`、`top_gap_mm`
- 中立板（可选）：`dividers`；每项是 {seam_index, seam_align?}，不写就是没有中立板。
- 门铰链侧（可选）：`door_hinges`；从左到右每扇门一项，取值 left 或 right，长度必须等于门数。
- 抽屉尺寸链输入：`drawer_side_clearance`、`drawer_layer_gap`、`drawer_back_clearance`
- 抽屉滑轨系统（可选）：`drawer_runner`；取值 side_mount（三节轨，缺省）或 undermount（托底轨）。换轨只改这一个字段：档位、上下间隙、轨腔高度全部查表，见 [抽屉滑轨规则](drawer-runner-rules.md)。
- 可选料档：`board_thickness`、`back_thickness`、`door_thickness`、`drawer_bottom_thickness`、`drawer_back_thickness`、`sheet_width_mm`、`sheet_length_mm`；省略则按 [料档与工艺卡](sheet-stock-catalog.md) 展开。
- 柜体身份（可选）：`cabinet_id`；这不是构造字段，运行时在准入前弹出，缺省 cabinet_1，不得包含 __。

## 字段口径

- `shelves` 每项是 `{shelf_type: fixed|movable, gap_below_mm: 数值|null}`；列表顺序、均分、计算层和净高口径见 [层板规则](shelf-planning-rules.md)。整组净高省略时准入均分。恰好一项为 `null` 时只闭合那一层，不对其余层均分。不保留 `shelf_count`。
- 当前 `drawer_count>0` 的规范语义只表示整高抽屉区；必须同时提交空 `shelves` 与 `n_doors=0`。
- `drawer_back_clearance` 是**最小后缝要求**，不是实际尺寸：准入只校验它严格大于该滑轨系统的下限（三节轨 > 0、托底轨 > 10），实际后缝由抽芯档决定、只会更大。盒高、盒深都不由提案给，见 [抽屉滑轨规则](drawer-runner-rules.md)。
- `dividers` 每项是 {seam_index, seam_align?}：`seam_align` 不写按 `center`。**不写 id、不写 thickness_mm**——中立板是柜体板，厚度取已准入的 `board_thickness`；`seam_index` 越界或同一缝出现两块，准入/评估直接拒。**不写 `dividers` 等于没有中立板**，不是"按柜型猜一块"。两条客观冲突同样直接拒：与整高抽屉区共存；`n_doors < 2`（一扇门没有内缝可对）。
- `door_hinges` 是**逐扇**的铰链侧：写的是"门往哪边开"这个设计决定，不是工艺参数。规则见 [门板铰链侧](door-hinge-side.md)——**对开腔那两位必须 left、right**（写反直接拒）；**单开腔不给就报警告** `DOOR_HINGE_SIDE_UNKNOWN`（不拦确认，留给板件页上点选或下一版补齐）；整排都是对开腔时可以完全不写。留空的门不能开门、也排不了铰链孔，制造会拦。

## 展示与停止

- 先给出一整份方案：用户已给的值 + 一份假设清单（只含候选起点里客户还没表态的构造选择）。用户没提板厚时，料档只写一行「柜体板 18 / 9 厘背板 9 / 门同柜体板」，不进假设清单。用户没给层板净高和踢脚支撑数时，这两项也不进假设清单，等准入结果里的具体数再给客户看。还有未接受的假设时，只问这一句：按这套出板，还是要改门/层板/抽屉/背板安装/踢脚。
- 客户已经给出完整构造，或已经说按这套做时，把完整对象写入 `stage_inputs` 再 `run_next()` / `retry_stage()`，不要把同一句话再问一遍。只改其中几项时，改完再调用。代码准入后展示确认审查清单（`current_view.markdown` 或其中的柜体/板件/接触表）。客户接受这一版后再确认阶段；还没接受时不确认。
- 只有超出当前拓扑表达能力时才停在消歧，不要写入 `stage_inputs`。完整停问清单：混合门/层板/抽屉分区（**腔级内容还表达不了**）。多扇门**不再**是停问项：一排放几扇都能出件，门宽由代码按等宽槽算。门缝按 [柜内结构契约](interior-structure-contract.md) 评估，评估回报不写入 `stage_inputs`。**中立板已经能落成板件**：要就说准哪条缝（`dividers`），毫米由代码给，不必也不该问客户"板多宽、离左墙多少"。

## 逐柜参数（一组柜不用长一样）

`stage_inputs.panels` 的形状是 **一份共享提案 + 按柜覆盖**：

```json
{
  "parameters": { "…所有柜的底…" },
  "cabinets": { "cabinet_2": { "n_doors": 1, "shelves": [ … ], "top_gap_mm": 620 } }
}
```

- **覆盖是逐字段的**：`{**共享, **这台}`；合起来必须是一份完整合法的提案——阶段验收照旧拒不合法的结果（净空填不满、单门没给铰链方向之类，**由代码报错，不替人补**）。
- **身份与几何不许写在覆盖里**：`cabinet_id` / `furniture_category` / `width` / `depth` / `height` 只来自包络（布局），覆盖里写了会被拒。
- **柜名必须认识**：覆盖里出现布局里没有的柜名直接拒（不静默忽略）。
- 平铺写法（`stage_inputs_from_spec`）用 `panel_cabinets: {柜名: {…}}`。
- **制造选项同理**：`stage_inputs.manufacturing.cabinets[柜名]` 可覆盖 `parameters`（如 `door_hinge_side`）与 `appearance`——一台双门、一台单门时，共享一份铰链方向根本表达不了。
- 改过板件产物（`revise_stage_output`）后，**每台柜自己的 spec 会写回它自己的覆盖**；不要再把某一台的参数抄给全部柜。

**旁路分析也要指名**：`panel_unit_audit` 默认**逐台**跑（报告里 `cabinet_ids` + 逐台明细，问题条目带 `cabinet_id`），`config.cabinet_id` 可以只审一台；`panel_optimization` **必须**指名（多柜工程里不指就报错），候选自带 `cabinet_id`，落地只改那一台。

## LLM 候选起点

用户没说时，LLM 用下面这组值填满必填字段并标成假设。料档、层板净高和踢脚支撑数按各自的省略口径留下不写，不把展开后的毫米或根数写成假设。

- 料档按工艺卡，不写入假设清单：柜体板 18、9 厘背板 9、门与抽屉盒同柜体板、板幅 1220×2440。覆盖时只允许目录值，见 [料档与工艺卡](sheet-stock-catalog.md)。客户说要长板（1220×2745）时两个数一起写，只写一个是没说清。
- `back_mount=groove`、背板后移 18、前脸边距 1.5、前脸深度缝 2、槽深 6、槽余量 1、背拉条高 70。
- 抽屉每侧净空 13、层缝 1.5、后缝 20（三节轨要 > 0、托底轨要 > 10）；滑轨系统不写就是三节轨。盒高与盒深由代码按格高和抽芯档算，不写成假设。
- 落地柜：踢脚 50、前后退让 1/30、2 门、`drawer_count=0`、4 层固定层板。层板只写 `shelf_type`，不写 `gap_below_mm` 和 `top_gap_mm`。不写 `toe_kick_support_count`。准入按该柜外形尺寸写入均分净高和支撑数。
- 吊柜：踢脚 0、前后退让 0、2 门、`drawer_count=0`、1 层固定层板。层板净高同样整组不写。不写支撑数；踢脚高为 0 时展开为 0。
- 用户要整高抽屉时：`drawer_count` 用其给出的抽数，空 `shelves`、`n_doors=0`、`top_gap_mm=0`，其余仍用上列工艺起点。