# 柜内结构

回答“中立板、腔、分段和正面排版提交什么，谁来算毫米”。交互工具是 `furniture_evaluate_interior`（实现函数 `evaluate_interior`）。它不写项目、不推进阶段。这一步不把结果写进柜体板件，制造、特征树、CAD、交付仍读原来的板件形状。

名称见 [术语规范表](terminology-glossary.md)。

## 提交

坐标：柜内 X，0 是左侧板外表面，向右为正，单位 mm。

中立板和分段互不绑定。同一块中立板可以让顶板、踢脚各自保持整段，或按这块中立板断开，四种组合都能表达。断口不写 `align_divider` 时，那块板保持整段。运输拼板用 `at_mm`，与有没有中立板无关。

- 正面：`width_mm`、`n_doors`、`margin_mm`（用已准入的 `front_face_margin`）、`pairs`（从左起、0 开始的相邻两扇）。对开只记录哪两扇对着开，不改变门宽和门缝。
- 中立板：`seam_index`、`seam_align`（不写则 `center`）、`thickness_mm`。缝定锚。侧面锚就是那个侧面。
- 分段：板的 `start_mm` / `end_mm`。断口要么 `align_divider`，要么 `at_mm`（可带 `width_mm`，不带则为 0）。
- 腔的用途净空：`cavity_needs`，每条带 `grade`。
- 侧板厚用已准入的 `board_thickness`，字段名 `side_thickness_mm`。评估不另设边距或板厚默认值。

## 三步

1. **生成。** 只提交上面这些选择。不填槽位、门宽、区间、净空、段长。
2. **评估。** 调用 `furniture_evaluate_interior`，传入 `interior` 对象。回报在结果的 `interior` 里：每扇门宽、每条缝宽、中立板区间、各腔净空、各段长度，以及 `findings`。毫米以这份回报为准。
3. **修复。** 锚、板厚变化、对齐中立板的断口，评估时已经按缝和当前板厚算完。板厚变了锚不动，两侧净空一起变。`findings` 里没有 `blocked` 就可以把这份结果当方案。有 `blocked` 时同时看 `proceed_loss` 和 `stop_loss` 再决定问不问。`assumption` 留下方案并标成假设。`unjudged` 是缺数据、这条没判，不等于通过。

## 两侧代价

| 情况 | 状态 | 继续的损失 | 停下的损失 |
| --- | --- | --- | --- |
| 净空小于 `confirmed` 需求 | `blocked` | 按这个净空下料，腔放不下 | 这一轮没有可审查的板件 |
| 净空小于 `typical` 需求 | `assumption` | 典型值放不下，照做可能返工 | 没有可确认的假设方案 |
| `unknown` | `blocked` | 没有依据就下料 | 这一轮不出板；已经算出的净空仍在报告里 |
| 两块中立板抢同一条缝、断口重叠或落在板外、段短于 `confirmed` 最小段 | `blocked` | 对不齐或短板进车间 | 这一轮定不下这块板 |
| 最小段宽没给 | `unjudged` | 把没判当成做得出 | 没有车间数据就整单停住 |

最小段宽和用途净空没有数据时，不拿典型值冒充确认值。

## 代码

`scripts/furniture_panel_planning/interior_structure.py`。验收数字在 `domain/skills/cad-generated/scripts/tests/test_interior_structure.py`。
