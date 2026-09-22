# 制造阶段未落地需求

日常改孔位、BOM 或封边不必读本文。核对实现或规划演进时再打开。

## 待评审

- 连接点级实体（杆/轮/螺母按连接点整体增删、校验按连接点对齐）：`connection-point-design.md`。已部分落地：`HoleSpec.connection_id` + 三合一/背板按连接点 1:1:1 校验；「删单个孔 → 静默孤儿」已修复（按连接点报缺件）。
- cover（外盖）改三合一（留待以后确定）：方向已厘清——反向角色（背板=母件，偏心轮在侧/顶/底板上）；且背板需 18mm（预埋螺母深 11mm 放不进 9mm 薄背板）。几何与装配可达性待确定后再实现；当前 cover 仍视为组装现场工艺、不钻孔。
- 完整抽屉组件（门+抽屉混合区、托底轨、有面板）：`drawer-component-design.md`。
- appearance 与板件材质一致性（待定）：`revise_stage_output` 直接编辑制造输出后，`BOMReport.appearance`（选型输入记录）与 `PanelRecord.substrate/surface`（物化真相）可不同步；下游当前只读 panels，无实际影响。候选方案：① `PanelRecord` 加 `material_role` + validation 逐值一致性校验；② `BOMReport` 不再存 appearance，材质只存 panels，选型留 `stage_inputs`。
- `length_mm` / `width_mm` 取值错误（现记为「发现 A」）：制造层固定取世界坐标 `size_x` / `size_y`，而板厚方向常落在 X 或 Y 轴上，于是把板厚当成了开料尺寸。实测落地柜（800×1000×600）：侧板报 `18×580`（应为 `580×1000`）、背板报 `776×9`（应为 `776×926`）、背拉条报 `764×18`（应为 `764×70`）；顶/底板的板厚在 Z 轴，恰好正确。**不得作为运行时依据**：当前无消费者据此做决策（`area_m2` 与封边周长 `2×(长+宽)` 对调长宽不敏感），但 BOM markdown 的 `开料尺寸(mm)` 列直接显示它，拿去做开料会切错。根因：`PanelPlacement` 缺「板件平面是哪两个轴」的信息，`orientation` 是死字段（`topology_solver` 未赋值，恒为默认 `xyz`）。未决前提：是否支持有方向的纹理（`grain`）——目录注释说它「用于排版/校验」但无任何代码消费，而这是「长宽之分」唯一的真实用途。详细分析见 [制造层数据流梳理](data-flow.md)（越界 / 丢失 / 无主 / 死字段四类判据，以及「有无计算型下游决定字段是否被验证」）。缺口仍在时由 `test_cabinet_pipeline.py::test_length_width_are_flat_dimensions_not_world_axes` 自动提醒。

## 已落地（留档）

- 背板三合一孔类型合并：`back_insert_cam/rod/nut` → `three_in_one_cam/rod/nut`，校验/BOM 按 `connection_id` 区分柜体 vs 背板。
