# 背板结构规则

回答“外形尺寸确认后，柜体采用什么背板结构，以及由此得到哪些精确结构尺寸？”；本文件是背板设计的唯一规则中心。

## 阶段输入

- `back_mount`：规范值为 `groove/insert/cover`；必须由提案显式给出，不存在运行时缺省或 `auto` 解析。
- `board_thickness/back_thickness/door_thickness`：来自已准入料档；入槽和外盖背板厚为 9 厘背板 `9` mm，见 [料档与工艺卡](sheet-stock-catalog.md)。
- `back_offset/front_face_margin/front_gap`。
- `groove_depth/groove_clearance/back_rail_height`。

这些值可在完整 CLI/API 请求中提前提交，但只保存在 `stage_inputs.panels.parameters`，直到客户确认布局后才物化为板件阶段 `FurnitureSpec`。

## 模式

- 提案必须显式选择 `groove`、`insert` 或 `cover`。运行时不从板厚推断模式。
- 输出仍写 `back_mount_resolution.requested/effective`；两者必须等于已准入的 `back_mount`。下游消费该值。
- `groove_depth/groove_clearance/back_rail_height` 只在模式为 `groove` 时参与几何；其他模式仍要求它们是合法规范数值，但不因数值范围与入槽加工关系而阻塞。

## 精确结构

- 柜体前端统一预留 `door_thickness + front_gap`，所有板件保持在已确认成品深度内。
- `groove/insert`：柜体从 `Y=0` 开始，背板基准为 `back_offset`，内部 Y 起点为 `back_offset + back_thickness`。
- `cover`：背板位于 `Y=0`，柜体从 `Y=back_thickness` 开始，背板不得与柜体重叠。
- 内部 X/Z 范围由外形尺寸、柜体板厚和踢脚高度计算；所有净宽、净高、净深必须为正。

## 背板与背拉条

**没有中立板时**背面只有一件：

- `groove`：宽高为内部净宽/净高各加 `2×groove_depth`。
- `insert`：内部净宽×内部净高，位于 `back_offset`。
- `cover`：成品宽×成品高，覆盖整个背面。

**有中立板时**：

- **中立板通到柜背**：它从 `carcass_y_start`（`groove`/`insert` 是 0，`cover` 是背板厚）做到内空前沿，不再停在背板内表面。这样每腔的背板和背拉条都夹在板与板之间，背板两侧才有面可入槽/可打孔。
- **背板每腔一块**：`groove` 那块的两条竖边分别进侧板或中立板的槽 —— 立板两侧各开一条 `groove_depth` 深的背板槽，所以背板宽 = 腔净宽 + `2×groove_depth`；`insert` 齐腔净宽，四边三合一（立板通到柜背，它的大面就是内侧那两条边的配合面）。`cover` 不打断：它和立板不接触，切开只多出无谓的拼缝；宽柜盖不住就得改 `groove`/`insert`（见 [料档与工艺卡](sheet-stock-catalog.md) 的板幅校验）。
- **背拉条每腔一套**：立板到背，拉条不横穿过去；宽度是腔净宽。
- **id**：没有中立板时是 `back_panel` / `back_rail_1…n`（老工程逐字节不变），分腔后是 `back_panel_1…n` / `back_rail_c{腔}_{序}`，名称 `背板1…n` / `背拉条(腔2·1)`。**下游按 `panel_type == "back"` / `"back_rail"` 找，不按角色名找**。

背拉条本身（两种情形都适用）：仅有效模式为 `groove` 且 `back_rail_height > 0` 时生成，
每腔 `floor(internal_height / 500)` 根，沿内部净高等距布置，净距必须为正。
背拉条尺寸、位置和净距属于本阶段；槽包络与连接细节属于制造阶段。
