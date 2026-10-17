# panel-plan

这份在 `backlog/` 里，由 git 跟踪，不是技能。做柜子时按正式技能来。上面的 Open / Done 由程序按已落地版本改写，不要手改状态。

<!-- backlog-status:start -->
file_version: 1

## Open

- full-height-divider version 1 — one full-height divider
- half-height-divider version 1 — divider stops under the top bay
- door-rows version 1 — upper and lower door rows
- pair-grouping version 1 — whether pairs stays
- multi-door-cases version 1 — multi-door cases need a divider premise

## Done

- (none)
<!-- backlog-status:end -->

来源是 rabbit0716 在 2026-10-17 写的那份计划。当时它被放进了 `domain/skills/panel-plan/references/backlog.md`。计划改留在这里。

## full-height-divider

提案 `dividers: [{seam_index, seam_align?}]` → 运行时调 `evaluate_interior` 取缝与区间 → 物化一块通高立板，层板按腔分段；没有中立板的老工程产出不变。边界：只有一排整高门、立板通高、`n_doors ≤ 2`、`drawer_count = 0`、一台最多一块。字段面、验收数字与分步步骤见实施手册（工作区 `temp/`，不入库）。落地后把新增的口径写进契约文档，并把 `backlog_landed.py` 里这条的版本改成上面的 version。

## half-height-divider

现状：计划中的中立板按内部净空通高出件（从底板上表面到顶板下表面），所以它会把顶格一起切开。评估器 `evaluate_interior` 只算宽度方向（`cavity_needs` 也只有 `min_clear_width_mm`），没有任何 z 范围输入。

要做：立板可以只到某道横板下（半高），表达顶格是一个通格、下柜分两腔。

约束：它和 `breaks`（顶板 / 踢脚 / 背板要不要在这块立板处断开）是同一组决定。单独做会返工。评估器要么收每块立板的 z 范围，要么从顶格横板高度推；校验也从通高改成立板与横板/顶板真的接触。

验收：2400 高衣柜、2000 处一道横板、缝 0 上一块半高立板 → 下两腔各 373、上部一个 764 通腔；顶板整段（不断开），立板只到横板下表面。

入口：柜内结构物化设计批次 1 的「分段」、柜内结构契约的 `breaks`。文件在 `domain/skills/panel-plan/references/`。

## door-rows

现状：`n_doors` 是一排整高门；门高 = 柜高 − 踢脚 − 2×边距（`topology_solver._door_panels`），全柜一套 `front_face_margin` / `front_gap`。审查清单、`_validate_doors` 也都只按总数数。

要做：门排概念。每排的 z 区间、上下缝、扇数；上排顶柜门与下排柜门各自出件、各自铰链。

约束：竖向分层不逼门分层。整高门盖住顶格是最常见的做法，只有客户要一道横向门缝时才需要这一条。独立的顶柜（叠在衣柜上的另一台吊柜）在布局里就是另一件家具，不需要它。每排、每条固定竖直边最多 2 扇平开门（一扇挂左壁、一扇挂右壁）；上下排可用的竖直边可以不同（通高侧板 vs 半高立板）。

影响面：`topology_solver._door_panels`、`validation_panels._validate_doors`、`panel_review`、制造阶段 `_derive_door_hinge_sides`（现在写死最多 2 扇）。

验收：一体 2400 高衣柜、上排 400 高两扇门 + 下排两扇 2000 高门 → 四块门件、各自位置与缝；两排的边距/缝可以不同。

## pair-grouping

现状：`pairs` 只是 `furniture_evaluate_interior` 的入参，作用两处：零头落哪条缝（`_leftover_seam`）和审查清单显示（`format_interior_review_markdown`）。制造阶段不读 `pairs`，它按门角色推铰链（`_derive_door_hinge_sides`：单门须显式给 `door_hinge_side`，双门左=left 右=right，最多 2 扇）。板件阶段提案里没有 `pairs` 这个字段。

已厘清的物理边界：平开门每排每条竖直边最多挂 2 扇。一个腔里 1 扇是单开、2 扇是对开。3 扇及以上本拓扑表达不了（要联动 / 推拉 / 加中立板）。所以立板切腔、腔定分组是自洽的，`pairs` 可以退场、由腔推导。

待定：① 采立板定腔、腔定分组，`pairs` 从入参里去掉；② 保留 `pairs` 但加与立板的一致性校验（立板缝不可能同时是某组的中缝）。

影响：`_layout_doors` 要重排次序（门宽 → 立板缝位 → 由腔推分组 → 定零头缝 → 出毫米）；腔里 3 扇及以上改成 `blocked` 并给三条出路（加立板 / 改推拉联动 / 改门数）；门宽与边界件文档里「4 扇 2 组对开零头归宿」那条待择一顺势收口。

一条别写错的细节：零头不总落在立板缝上。分组左右对称时才成立（`[2]`、`[2,2]`、`[1,1]`）；像 `[1,2,1]`（单开+对开+单开，立板在缝 0 和缝 2）时，中心线落在中间那组对开的中缝上，零头落在那里。0.2mm，门缝里看不出来。

## multi-door-cases

现状：`tests/test_interior_structure.py` 有 `2400/7`、`1211/4`、`1511/6` 这类用例，门宽与边界件文档也按「4 扇 2 组对开」讨论零头。门宽与零头公式没错，但在上面的口径下这些组合少了「必须有立板」这个前提。

待定：① 给用例补立板（把「4 扇 2 组对开」落成「1 块立板在中间缝」、「3 扇一单一对」落成立板在其中一条缝），让用例物理成立；② 保留为只验门宽/零头公式的纯计算用例，并在文件头注明前提。

判据：走 ① 之后，「4 扇 2 组对开」的零头缝应等于立板缝；走 ② 则这条等式没有断言覆盖。
