# 制造阶段未落地需求

日常改孔位、BOM 或封边不必读本文。核对实现或规划演进时再打开。

## 待评审

- 连接点级实体（杆/轮/螺母按连接点整体增删、校验按连接点对齐）：`connection-point-design.md`。已部分落地：`HoleSpec.connection_id` + 三合一/背板按连接点 1:1:1 校验；「删单个孔 → 静默孤儿」已修复（按连接点报缺件）。
- cover（外盖）改三合一（留待以后确定）：方向已厘清——反向角色（背板=母件，偏心轮在侧/顶/底板上）；且背板需 18mm（预埋螺母深 11mm 放不进 9mm 薄背板）。几何与装配可达性待确定后再实现；当前 cover 仍视为组装现场工艺、不钻孔。
- 完整抽屉组件（门+抽屉混合区、托底轨、有面板）：`drawer-component-design.md`。
- appearance 与板件材质一致性（待定）：`revise_stage_output` 直接编辑制造输出后，`BOMReport.appearance`（选型输入记录）与 `PanelRecord.substrate/surface`（物化真相）可不同步；下游当前只读 panels，无实际影响。候选方案：① `PanelRecord` 加 `material_role` + validation 逐值一致性校验；② `BOMReport` 不再存 appearance，材质只存 panels，选型留 `stage_inputs`。

## 已落地（留档）

- 背板三合一孔类型合并：`back_insert_cam/rod/nut` → `three_in_one_cam/rod/nut`，校验/BOM 按 `connection_id` 区分柜体 vs 背板。
