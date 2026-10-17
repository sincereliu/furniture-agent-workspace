# 柜内结构

回答“中立板、腔、分段和正面排版提交什么，谁来算毫米”。交互工具是 `furniture_evaluate_interior`（实现函数 `evaluate_interior`）。它不写项目、不推进阶段。

**现在到哪一步**：中立板已经物化——`dividers` 是板件提案的可选字段，缝与区间仍全部出自这个评估器（`construction_geometry.divider_interior_report` 是板件阶段与它之间唯一的接口）。**腔内容（每腔自己的层板/抽屉/挂衣）和分段还没做**；评估回报本身仍不写入 `stage_inputs`，制造、特征树、CAD、交付读的是已物化的板件。

名称见 [术语规范表](terminology-glossary.md)。

## 提交

坐标：柜内 X，0 是左侧板外表面，向右为正，单位 mm。

中立板和分段互不绑定。同一块中立板可以让顶板、踢脚各自保持整段，或按这块中立板断开，四种组合都能表达。断口不写 `align_divider` 时，那块板保持整段。运输拼板用 `at_mm`，与有没有中立板无关。

- 正面：`width_mm`、`n_doors`、`margin_mm`（用已准入的 `front_face_margin`）、`pairs`（从左起、0 开始的相邻两扇）。对开只记录哪两扇对着开，不改变门宽和门缝。
- 中立板：`seam_index`、`seam_align`（不写则 `center`）、`thickness_mm`。缝定锚。侧面锚就是那个侧面。**板件阶段提交的不是这一层**：提案只写 `seam_index` 与 `seam_align`，`id` 和 `thickness_mm` 由板件代码填（厚度取已准入的 `board_thickness`），见 [提案契约](panel-proposal-contract.md)。
- 分段：板的 `start_mm` / `end_mm`。断口要么 `align_divider`，要么 `at_mm`（可带 `width_mm`，不带则为 0）。
- 腔的用途净空：`cavity_needs`，每条带 `grade`。
- 门宽推荐区间：`min_door_width_mm` / `max_door_width_mm` + `door_width_grade`。可只给一头；**一头都不给就是不判**（不报 `unjudged`）。口径见 [门宽与边界件](door-width-and-boundary-pieces.md)。
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
| 门宽超出推荐区间（`typical` 档） | `assumption` | 低于推荐下限，照做可能不好看或变形 / 高于推荐上限，照做可能下垂 | 这一轮没有可审查的门 |
| 门宽超出推荐区间（`confirmed` 档） | `blocked` | 按这个门宽下料，门偏窄、容易变形 / 门偏重、铰链吃力 | 这一轮没有可审查的门 |
| 门宽区间一头都没给 | 不判 | ——（门是必填项，每次报会变成噪音） | —— |

最小段宽和用途净空没有数据时，不拿典型值冒充确认值。

## 代码

`scripts/furniture_panel_planning/interior_structure.py`。验收数字在 `domain/skills/cad-generated/scripts/tests/test_interior_structure.py`。

## 下一步

把评估结果写进板件（谁拥有哪些数、物化清单与分期）见 [柜内结构物化设计](interior-materialization-design.md)。中立板属批次 1，已落地；**分段（`breaks`）和腔级内容还没做**。
