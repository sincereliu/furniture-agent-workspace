# 更新日志

## 20260822.8 — 抽屉盒默认三合一 + TrinityConnector 泛化（轴无关）

全屋定制抽屉盒主流用三合一连接（木销+胶为少数），改为默认；连接布置按确认方案。

### 连接布置（每抽 8 连接 × 2 排 = 16 套三合一）

- 底板 ↔ 侧板（x 轴，2 侧）：male=底板，cam_face=`-z`（偏心轮在底板下面，抽屉外部操作）。
- 底板前端 ↔ 前板 / 底板后端 ↔ 背板（y 轴）：male=底板（cam 仍在 `-z`），female=前板/背板。
- 前板 ↔ 侧板（y 轴）：female=前板，male=侧板，cam_face=`±x`（侧板外侧面）。
- 背板 ↔ 侧板（x 轴）：female=侧板，male=背板，cam_face=`-y`（背板外侧面）。

### 改动点

- `TrinityConnector.generate_holes_for_panels` 重写为**连接驱动、轴无关**：螺母/杆/轮按 joint 的
  边轴（x/y）+ cam 面轴 + 第三轴推导，替代原"x 轴 + 横板 male（cam ±z）"假设；`_nut_holes`/
  `_rod_holes`/`_cam_holes` 新 builder；`generate_holes` 保留为无拓扑旧数据回退。
- 连接判定 `_is_trinity_joint`：抽屉子装配内部 x/y 轴接触均为连接；柜体仅 x 轴（层板后 y 端面
  搁背板前面是接触不是连接，不再误生成螺母孔）。
- `joint_topology.compute_joints`：排除抽屉↔柜体跨装配接触（抽屉是滑动子装配）。
- `_drawer_panels`：侧板按滑轨间隙内缩（`slide_gap`）；底板 y 向延伸到前板；背板底边与底板齐平
  （底板后端连接杆轴线才能落在背板内）；各板 `cam_face` 按布置赋值。
- **顺带修正**：柜体层板连接"螺母/杆前排错位 27mm"（螺母原按自身跨度、现按 male 跨度对齐，
  层板前排螺母 world y 64→91）；侧板螺母数不变。

### 验证

- 57 项测试通过（抽屉默认三合一新测试替代原"无三合一"断言）。
- 抽屉柜 1:1:1（杆=轮=螺母=24/抽含柜体）；底板 8 轮孔全在底面（z_local=0、方向 +z）。
- 柜体（drawer_count=0）侧板 12 螺母、层板 8 孔、背板 0——仅层板前排螺母对齐修正 4 处。

## 20260822.7 — 修复抽屉侧板被误判为三合一母件

抽屉盒体不用三合一（现实工艺为木榫+胶/螺丝）；但 `_trinity_female` 的拓扑判定
只查 `face[1]=="x"`、未校验 `male_has_cam`，导致抽屉侧板（与抽屉底板/背板存在
x 面邻接）被误判为三合一母件，走 fallback 全高排钻打出系统 32 预埋螺母孔
（且仅左侧板出现，不对称）。

### 修复

- `connectors/trinity.py`：`_trinity_female` joint 判定补 `j.male_has_cam` 条件
  （与 `_trinity_male`/`_female_holes` 一致）；抽屉板件 `cam_face=None` → 不再误判。
- 测试：`test_drawer_panels_have_no_trinity_holes`（抽屉板件零三合一孔，carcass 孔位不变）。

### 验证

- 57 项测试通过；抽屉 15 板零孔；carcass 孔位不变（bottom 8 / 侧板各 4 / top 8）。

## 20260822.6 — 抽屉区首版落地（档 B：整高抽屉区 + 无面板 + 三节轨）

`drawer_count` 驱动的整高抽屉区打通板件规划→制造全链路。

### 改动点

- `FurnitureSpec` 新增 `drawer_count`（默认 0，向后兼容）+ `PANEL_SPEC_FIELDS` 白名单 + `from_dict` 解析（走 options 路径，layout 不感知）。
- `floor_cabinet.yaml` 新增 `internals.drawers` profile（type=full_height、slide_type、face_mode=none、layer_gap 1.5、底/背板厚 18、back_clearance≥0）；滑轨间隙**单一真源** = catalog `gap_requirement_mm`（按文件路径读取，不 import 制造模块）。
- `topology_solver._drawer_panels`：每抽屉 5 板（前/左/右/后/底），label 契约 `drawer_*_z{pos}`；底抽前板全盖底板（overlap=18）、顶/中 0；抽屉优先——`drawer_count>0` 时不生成门与固定层板。
- 板件校验：`drawer_count>0` 且 `n_doors>0`/`shelf_count>0` 时发 warning（`DRAWER_ZONE_SUPERSEDES_*`），不静默。
- `hardware_catalog.yaml`：三节轨 `gap_requirement_mm` 12.5→**13.0**（投产前确认）。
- 封边：`DEFAULT_EDGE_RULES` 补 `drawer_*` 四边 ABS 同色。
- 清理：layout 测试中"未知字段"样例由 `drawer_count` 换为 `unsupported_layout_option`（drawer_count 已是合法面板输入）。
- 测试：新增 `DrawerZoneTests` 5 条（5 板/抽、底抽覆盖、BOM 滑轨 ×6、warning、向后兼容）。

### 验证

- 56 项测试通过（51 + 5 新增）。
- `drawer_count=0` 全回归不变；滑轨 BOM：3 抽 → 数量 6、长度按抽屉深 535→450mm。

## 20260822.5 — 记录抽屉组件级实体需求（待评审提案）

抽屉本质是子装配组件（板件集合+盒体拓扑+滑轨/拉手五金），当前板件规划不生成抽屉板件。

### 内容

- 新增 `skills/furniture-manufacturing/references/drawer-component-design.md`：背景、现状、**契约 3 条**（panel_type 含 `drawer`、尺寸取自抽屉板件自身、实例 key = label 位置后缀且每抽 1 副）、需求（抽屉组件物化、layout `drawer_count` 启用或清理、滑轨长度校验、五金变体注入）、实施建议。
- `SKILL.md` 步骤 4 与连接点需求并列加指引，标注"实施前需评审"。

## 20260822.4 — 抽屉滑轨 Connector 化（档 A：纯重构）

`DrawerSlideConnector` 落地，抽屉滑轨从"特例函数"迁入标准 Connector 路径，消灭死代码。

### 改动点

- 新增 `connectors/drawer_slide.py`：`DrawerSlideConnector`（`catalog_entry="drawer_slides"`），按抽屉实例匹配长度/承重/品牌；滑轨螺钉为组装现场工艺，不生成孔位。
- 修复潜在 bug：滑轨数量从"整柜固定 2"改为"每抽一副（左右各 1）× 抽屉实例数"，不同规格分条记录。
- `connectors/__init__.py`：注册 `ALL_CONNECTORS`；`manufacturing_bom.py`：删除滑轨特例块与 import。
- 删除死模块 `manufacturing_hardware.py`（`match_drawer_slides` 原所在，无其他引用）。
- 测试：新增 2 条——按抽屉实例出 BOM（数量/长度/品牌）、无抽屉板件时不产出滑轨。

### 验证

- 51 项测试通过（49 + 2 新增）。
- 无抽屉柜型 BOM 零变化（DrawerSlideConnector 空输出）。
- 契约面向"抽屉组件"（见 20260822.5），档 B 抽屉板件落地时滑轨自动生效。

## 20260822.3 — direction 语义统一为钻入方向

`HoleSpec.direction` 统一为"钻入方向（往板内）"（`coordinate-naming.md` 约定），
消除"杯孔/偏心轮存面朝向、螺母/杆存钻入方向"的混合语义。

### 改动点

- `connectors/hinge.py`：杯孔 direction 从 `inner_face`（面朝向）改为 `_opposite(inner_face)`（钻入方向），新增 `_opposite` 助手。
- `connectors/trinity.py`：偏心轮孔 direction 从 `cam_face` 改为 `_opposite(cam_face)`。
- `furniture_panel_planning/panel_face.py`：`cup_direction`/`cam_direction` 语义同步改为钻入方向（该辅助当前无调用方，纯语义定义修正）。
- `validation.py`：铰链方向校验改为 `hole["direction"] != _opposite(panel.inner_face)`。
- 测试：`test_recent_manufacturing_patches.py` 铰链方向断言 `-y → +y`（1 处）。
- 文档：`coordinate-naming.md` ⚠"待落地"→✅"已统一"、`manufacturing-rules.md`、`SKILL.md` 方向措辞同步。

### 验证

- 3 柜型（地柜 cover/insert + 吊柜）JSON diff 仅 direction 翻转（cam `-z→+z`、铰链 `-y→+y`），其余字段逐字相同。
- GLB 孔位标记网格顶点多重集逐点相等——几何零变化，产物差异仅为旋转表示。
- 六面钻 XML/Quadrant 零影响（Quadrant 仅用于边孔，边孔方向本就为钻入方向）。
- 47 项测试通过。

### 遗留

- 前端 Viewer 是否消费 `drilled-holes.json` 的 `direction` 字段待确认（GUI 代码不在本仓库）。

## 20260822.2 — 记录连接点级实体需求（待评审提案）

记录"连接点作为整体增删"的需求，**未立项、未实施**。

### 内容

- 新增 `skills/furniture-manufacturing/references/connection-point-design.md`：背景（杆/轮/螺母配对为几何隐式约定）、现状行为表（删轮孔被拦、删杆孔静默孤儿、背板 1:1:1 拦截）、需求 4 条（整体增删、按连接点校验、配对显式化、machining id 去重）、实施建议与验收标准。
- `SKILL.md` connectors 步骤加指引行，标注"实施前需评审"。

## 20260822.1 — 三合一/背板/层板孔位局部坐标化

孔位先在面板局部坐标定义（局部为唯一真源），世界坐标统一由 `to_global` 派生
（当前轴对齐：仅平移）。不涉及字段改名（按"搭车改、不单独改"）。

### 改动点

- `connectors/trinity.py`：`_female_holes` 螺母孔 Z 先算局部（joint 高度 − `panel.pos_z`），删除 `x_local = x_global - panel.pos_x` 反推；`_male_holes` 世界坐标全部由 `to_global` 派生，删掉手工并行计算；保留旧发射顺序（先全部杆孔再全部轮孔）。
- `connectors/back_mount.py`：连接点以背板局部坐标为锚，配合板按同一世界点折算到各自局部坐标；`_hole` 改为收局部坐标、内部统一 `to_global`。
- `connectors/shelf.py`：层板托孔局部优先，世界由 `to_global` 派生。

### 验证

- 4 柜型（地柜 cover/insert/groove + 吊柜）改前/改后孔位 JSON 快照**字节级一致**（244578 字节）。
- 所有孔位满足 `world == to_global(local)`。
- 41 项测试通过。

### 遗留

- 字段改名（`x_local → hole_x` 等）：`coordinate-naming.md` P3 触发条件现已满足，仍按"搭车改、不单独改"等待下游需求。

## 20260819.2 — 铰链死接口清理（五金类目决策：路线 B）

经五金类目讨论拍板，采纳路线 B（整体移除）：`hinge_brand / hinge_variant / hinge_overlay / hinge_angle` 四个参数自 20260817.1 精简目录后已成死接口（API/适配器接受并回显，`HingeConnector` 不消费），删除以消除"收了不生效"的静默失效风险。决策依据见 `temp/hardware-category-decision/PROPOSAL.md`。

### 移除点

- `server.py`：删除 `CabinetRequest` 四个铰链偏好字段（`hinge_brand/hinge_variant/hinge_overlay/hinge_angle`）。
- `input_adapter.py`：`MANUFACTURING_SPEC_FIELDS` 仅保留 `options`。
- `workflow_project.py`：`_legacy_stage_inputs` 制造搬运白名单仅保留 `options`。
- `manufacturing_bom.py`：`MANUFACTURING_OPTION_FIELDS` 仅保留 `options`。
- `hardware_rules.yaml`：删除 `bore_distance_mm` 注释残留（杯孔边距由 `edge_offset_mm + cup_diameter/2` 现算，无消费方）。
- `test_furniture_orchestrator.py`：删除 `test_input_adapter_routes_hinge_preferences_to_manufacturing`（只测回显、语义已死）。

### 影响

- 孔位/BOM/六面钻 XML 零变化（死字段本就无消费；探针已验证磁盘产物与代码一致）。
- 铰链仍为单一默认 `35mm杯全盖 100° full`（`hardware_catalog.yaml` 不变）。
- 未来如需多盖法/品牌：按经验层设计（`temp/experience-layer-design/DESIGN.md` §6.3 候选-拍板）以真参数形态回归，品牌经 `factory_profile.yaml` 厂规注入。

### 遗留（完整总账见 `temp/hardware-category-decision/PENDING.md`）

- 路线 B 改动**未提交**（7 文件在工作树，待 review 后 commit）。
- 四边盖值模型（铰链边+三边）讨论中：已共识"铰链边为主、默认联动、先做第 1 层"；宽度口径/对开门中缝/铰链型号映射/特殊角度排除 4 点待拆单员拍板。
- 经验层 `temp/experience-layer-design/` DESIGN.md 待评审 + 5 个开放问题 + EXPERIENCE-CHECKLIST 8 类厂规待填。
- `direction` 语义统一与坐标字段改名：按策略 P3 搭车改，不单独动。

## 20260817.1 — 三合一几何正确性修复 + 孔即真源 + 铰链局部坐标化

### 三合一孔位几何修正（connectors/trinity.py, joint_topology.py, hardware_catalog.yaml）

- 偏心轮孔 cam_face 坐标映射反转修复：`cam_face="+z"` 落在顶面、`"-z"` 落在底面（原先写反）。
- 连接杆孔/预埋螺母孔高度从"板厚中心"改为"偏心距驱动"：新增 `rod_axis_offset_mm: 9`（连接杆轴线到偏心轮安装面的距离），25mm 板下不再错位。
- 偏心轮圆心修正：沿连接杆方向(x)距端面 `center_offset_from_edge_mm`(33.5)，深度方向(y)与连接杆同排（原先 33.5 被误用在深度方向）。
- `PanelJoint` 新增 `male_cam_face`/`male_size_z`，供制造阶段由 cam_face + 偏心距反推连接杆轴线高度。

### 孔即真源（connectors/trinity.py, validation.py）

- 三合一 BOM 数量从"系统 32 排钻估算"改为"统计实际生成的偏心轮孔数"，消灭数量≠孔数。
- 新增校验：三合一数量必须等于偏心轮孔数。

### 几何接口地基（manufacturing_models.py）

- `PanelRecord` 新增 `face_position`/`extent`/`center_along`/`to_global`/`to_local`，为局部坐标化与异形内核铺路。

### 铰链目录精简（hardware_catalog.yaml, hardware_rules.yaml, hinge.py）

- 铰链规格从 13 种（国内/进口 × 全盖/半盖/内嵌，共 11 品牌）精简为 1 个默认 `35mm杯全盖 100°`。
- `cup_by_variant_group` 同步精简为单个 `35mm杯全盖`。

### 铰链局部坐标化（connectors/hinge.py）

- 杯孔生成从"先算全局、再反推局部"反转为"先在局部定义、`to_global` 派生"，局部坐标成为唯一真源。

### 文档与测试

- `manufacturing-rules.md` 三合一偏心轮规则与铰链"国产全盖"措辞同步。
- `test_recent_manufacturing_patches.py` 三合一偏心轮 x/y 断言更新。

### 背板螺钉删除（组装现场工艺，不加工）

- cover 外盖螺钉与 groove 背拉条螺钉的孔位（clearance 通孔 + pilot 预孔）与五金 BOM 全部删除——它们是组装现场工艺，非柜体加工。
- `BackMountConnector` 只保留 insert 内嵌背板四边三合一；catalog 删除 `back_fasteners`，rules 删除 cover/back_rail 打孔规则。

### 坐标命名约定（references/coordinate-naming.md）

- 新增命名约定文档：三层坐标 panel/cabinet/world，`对象_参考系_轴` 命名规则，
  `hole_x`/`hole_cabinet_x`/`panel_cabinet_x`/`panel_world_x`/`cabinet_world_x` 五层量，
  以及圆心=入口面圆心、direction=钻入方向、废弃 `global` 等约定。
- 现有代码字段未动，按"搭车改、不单独改"策略，待 P3 局部坐标化/direction 统一/2.5D 时落地。

### 遗留（待五金类目讨论）

- `hinge_brand/hinge_variant/hinge_overlay/hinge_angle` 参数成为死接口（catalog 已精简，连接件不消费）。
- `bore_distance_mm` 仍为死配置。

---

## 20260814.1 — 房间坐标 Y 轴约定统一

- 房间坐标 Y 轴从"向北"调整为"向南"（俯视朝下），原点从"西南角"改为"西北角"。
- 标准柜体默认贴北墙、门朝南，此时柜体局部坐标与世界坐标完全一致（零旋转）。
- 默认摆放从"沿南墙居中"改为"沿北墙居中"，`placement_source` 标记改为 `default_north_wall_centered`。
- 沿墙偏移方向纠正为顺时针：`north` 西→东、`east` 北→南、`south` 东→西、`west` 南→北。
- 同步修正 `room_planning` 的旋转/原点/净距/门窗跨度计算，以及 SVG/Viewer 的门窗渲染坐标。

---


## 20260731.3 — 默认卧室与三维包络预览

- 未提供房间时，第 2 阶段使用 `4200×3600×2800 mm` 的“默认卧室（系统假设）”。
- 未提供摆放位置时，柜体默认沿南墙居中；只提供房间或位置时补齐缺失项。
- `layout_planned` 增加 `layout_context` 来源标记，成功输出必须包含房间定位和 SVG 预览。
- SVG 从俯视平面图改为近大远小的透视三维包络：房间透明，家具为不透明长方体，门窗和障碍物保留空间标识。
- `layout_planned` 增加自包含 HTML 互动 Viewer，支持拖拽环绕、滚轮缩放及透视/正视/左视/右视/俯视切换。
- FastAPI 版本更新至 `0.5.0`，无房间输入也可直接取得布局预览，并增加 `/api/plan-layout/viewer`。

---

## 20260731.2 — 房间定位与第 2 阶段 SVG 预览

- `furniture-layout` 增加矩形房间、门窗和长方体障碍物模型。
- 支持按南/东/北/西墙与沿墙偏移自动定位，也支持自由坐标和旋转定位。
- `layout_planned` 增加标准化房间变换、四角占地、六向净距和内联 SVG 平面预览。
- 布局校验增加房间越界、层高、门窗遮挡、障碍物碰撞及预览谱系检查。
- FastAPI 增加 `/api/plan-layout` 和 `/api/plan-layout/preview`。

---

## 20260731.1 — 最近制造/六面钻更新的稳定性补丁

- 柜型拓扑移回 `furniture-panel-planning/references/cabinet-topologies/`，
  避免设计意图阶段承载板件构成。
- 单门和标准双门显式写入铰链侧；铰链杯孔继续使用杯心距边与门板内侧面。
- `drilled-holes.json` 补齐 `panel_type`，三合一前后双排、板面孔/板边孔和
  4.5mm 螺钉直通孔增加回归测试。
- 六面钻 XML 统一使用板件局部坐标，并将水平孔方向从世界轴转换到机床轴；
  修复 Z1、Quadrant、重复闭合顶点和缺失局部坐标的问题。
- 槽位尚无设备契约时明确拒绝导出，不再静默漏加工。
- 孔位 STEP 导出不再吞异常或覆盖普通 GLB；动态板件按来源角色分组。
- 孔位 STEP/Viewer 侧车与逐板六面钻 XML 全部登记进 Manifest 和交付必需项。

---

## 20260729.2 — 六面钻 XML 导出修正 + 三合一打孔逻辑修复

### 六面钻 XML 导出 (export_six_side_drill.py)

**修正 1：TypeNo 判定基准修正**
- 原因: 原先用世界坐标 ±z 区分垂直/水平孔 (TypeNo=1/2)，但板件在机床上的放置方向可能使 ±x 方向变为垂直孔
- 修复: 引入 `is_face_hole` 属性到 `HoleSpec`，由连接件生成孔时直接标记面孔/边孔，XML 导出层直接读取
- 涉及文件: `connectors/base.py` (新增字段), `connectors/trinity.py`, `connectors/hinge.py`, `connectors/back_mount.py`, `connectors/shelf.py`, `manufacturing_bom.py`, `export_six_side_drill.py`

**修正 2：PanelOutline 顶点 X/Y 写反（板子转了 90°）**
- 原因: `_make_panel_xml` 中 outline 用 `(width_2d, length)` 当作 X/Y，实际 PanelLength 是 X 轴
- 修复: 变量改为六面钻语义 `sixd_x`(机床X轴), `sixd_y`(机床Y轴), `sixd_z`(板厚)，outline 顶点改为 `(sixd_x, sixd_y)` 顺序

**修正 3：语义重命名**
- `hardware_catalog.yaml` 和 `devices/six_side_drill_guigui.yaml` 全部增加中文注释
- YAML key: `length_from_box` → `sixd_x_from_box`, `width_from_box` → `sixd_y_from_box`
- Python 变量: `length` → `sixd_x`, `width_2d` → `sixd_y`, `thickness` → `sixd_z`

### 三合一打孔逻辑修复 (connectors/trinity.py)

**修正 4：深度方向单排→双排**
- 原因: 原先每个高度层只打 1 个预埋螺母 (Y 固定在 depth-33.5)，三合一应该是前后各一个
- 修复: 预埋螺母/连接杆 Y 位置改为 `[first_hole_mm, depth - last_hole_mm]` 双排（默认 [64, depth-64]）
- 偏心轮 Y 位置改为 `[center_offset_from_edge, depth - center_offset_from_edge]` 双排

**修正 5：交叉补充预埋螺母也改为双排**
- `generate_holes_for_panels` 的去重逻辑从 1D (仅 Z) 改为 2D (Z + y_local)，每处补两个

### 铰链孔位修正 (connectors/hinge.py)

**修正 6：铰链 Y1 用杯心距边**
- 原因: 原先 Y1=edge_offset=5mm（铰链臂侧边距），柜柜 Y1=22.5mm
- 修复: Y1 = `edge_offset + cup_diameter/2 = 5 + 17.5 = 22.5`，杯孔中心到门边的真实距离

### 五金规则检查

全面校验了 3 个 YAML 文件中所有 21 个规则值，全部正确：
- `system_32_drilling`: first/last 64mm, max 512mm, min 32mm ✅
- `hinge_drilling`: edge_offset 5mm, cup φ35×13 (国产全盖) ✅
- `back_mount_drilling`: insert/cover/back_rail 三模式正确 ✅
- `catalog/three_in_one`: φ12 偏心轮, φ8 连接杆, φ10 预埋螺母 ✅
- `devices/six_side_drill_guigui`: side/horizontal/door/toe_kick/default 面板放置正确 ✅

### 与柜柜的差异分析（仅记录，本次未修改）

| 差异 | 原因 | 说明 |
|---|---|---|
| 背板安装模式 | `resolve_back_mount()` auto→groove | 柜柜用 insert |
| 背拉条连接件 | groove 模式用螺钉 | 柜柜用三合一 |
| 踢脚板无三合一 | TrinityConnector 不匹配 toe_kick | 规则值正确，代码匹配范围可扩展 |
| 背板槽未导出 | export_six_side_drill 不处理 TypeNo=3 | 未来可加 |

### SKILL 文档更新

- `SKILL.md`: 更新连接件和六面钻导出描述
- `references/manufacturing-rules.md`: 更新孔位生成规则说明

---

## 20260729.1 — 拓扑驱动重构 + 方向错误修复

### 架构变更：拓扑数据 + 通用求解器

引入三层新抽象，将柜体结构从硬编码改为数据驱动：

1. **`CabinetFrame`** (`cabinet_frame.py`) — 柜体方向模型
   - 用 `front` + `top` 两个方向定义柜体朝向，右手定则自动推导其余四面
   - 落地柜: `front="+y", top="+z"`；未来榻榻米: `front="+z", top="-y"`

2. **`PanelFace`** (`panel_face.py`) — 板件面语义模型
   - 每块板件携带 `inner_face`（朝柜内面）、`outer_face`（朝柜外面）、`cam_face`（偏心轮可操作面）
   - 连接件不再硬编码钻孔方向，改为通过面语义推导

3. **`topology_solver.py`** — 通用空间求解器
   - 读取 YAML 拓扑数据 + FurnitureSpec + CabinetLayout → 计算 PanelPlacement[]
   - 不按柜体类型分支，新增柜型只需增加一份 YAML 拓扑文件

4. **拓扑数据文件**
   - `cabinet_topologies/floor_cabinet.yaml` — 落地柜拓扑
   - `cabinet_topologies/wall_cabinet.yaml` — 吊柜拓扑

### 方向错误修复

**修复 1：右侧板预埋螺母孔打反了**
- 原因: `trinity.py` 对所有竖板写死 `x_global = pos_x + size_x`, `direction="-x"`
- 左侧板 (pos_x=0) → x_global=18, 方向"-x" ✅ 正确
- 右侧板 (pos_x=582) → x_global=600, 方向"-x" ❌ 打到外侧面去了
- 修复: 左侧板 inner_face="+x" → 螺母方向="-x"；右侧板 inner_face="-x" → 螺母方向="+x"

**修复 2：顶板/底板/固定层板偏心轮方向全统一"+z"**
- 原因: `trinity.py` 偏心轮写死 `direction="+z"`（从顶面钻入）
- 实际: 偏心轮应从可操作面钻入（通常为底面 "-z"），安装后顶面被相邻板挡住
- 修复: 偏心轮方向 = `panel.cam_face`，顶板/底板/层板的 cam_face 设为 "-z"

**修复 3：铰链杯孔方向硬编码 "+y"**
- 原因: `hinge.py` 写死 `direction="+y"`
- 修复: 杯孔方向 = `panel.inner_face`，门板内侧面由拓扑规划器标记

**修复 4：层板托孔打在了层板自身上**
- 原因: `shelf.py` 对 movable_shelf 自身打孔
- 修复: 层板托孔改打侧板内侧面（这是受力支撑点）

### 数据模型扩展

- `PanelPlacement` 新增 `inner_face: str`, `outer_face: str`, `cam_face: str | None`
- `PanelRecord` 新增同样三个字段
- `_manufacturing_panel()` 传递 face 字段到 PanelRecord

---

## 当前程序存在问题清单

### 🔴 已知 Bug（方向/坐标错误）

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 1 | 右侧板预埋螺母孔打到外侧面 | trinity.py | ✅ 本版已修复 |
| 2 | 顶板/底板/层板偏心轮方向硬编码"+z"，不可操作 | trinity.py | ✅ 本版已修复 |
| 3 | 层板托孔打在层板自身，应在侧板内侧面 | shelf.py | ✅ 本版已修复 |

### 🟡 架构问题（缺失抽象）

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 4 | 面板方向由位置隐式推断（pos_x+size_x 猜内侧面），右侧板猜错 | trinity.py, hinge.py | ✅ 本版引入 PanelFace 解决 |
| 5 | 柜体结构硬编码在 cabinet_panel_planner.py 中，无法扩展 | cabinet_panel_planner.py | ✅ 本版引入拓扑 YAML + 求解器解决 |
| 6 | 世界坐标系硬编码在 feature_tree_builder.py | feature_tree_builder.py | ⚠️ 仍硬编码，需改为从 CabinetFrame 生成 |

### 🟠 功能缺失

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 7 | 活动层板 (movable_shelf) 根本不生成 | cabinet_panel_planner → topology_solver | ⚠️ 拓扑 YAML 未定义 movable_shelf |
| 8 | 抽屉完全不生成（面板、滑轨） | 整个 pipeline | ⚠️ 未实现 |
| 9 | 木榫完全不生成 | 五金层 | ⚠️ 未实现 |
| 10 | 拉手/拉直器完全不生成 | 五金层 | ⚠️ 未实现 |
| 11 | 铰链选型硬编码"国内35mm杯全盖 100°"，catalog 有 14 种只用 1 种 | hinge.py | ⚠️ 未实现 |
| 12 | hole_type 硬编码 "hinge"，与 hinge_brand/hinge_variant/hinge_overlay/hinge_angle 字段脱节 | hinge.py, FurnitureSpec | ⚠️ 字段定义了但未使用 |

### 🔵 规则未执行

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 13 | 冲突检测规则定义了但从未执行 | hardware_rules.yaml §conflict_avoidance | ⚠️ 规则有，代码无 |
| 14 | drill_length_by_type 在 YAML 定义了，代码用另一套 if-elif | hardware_rules.yaml + manufacturing_bom.py | ⚠️ 两处不一致 |
| 15 | 排钻起步面未定义（drill_length 只定义长度，不定义从哪个边开始） | trinity.py _system_32_positions | ⚠️ 靠 first_hole_mm=64 隐式假定 |
| 16 | hinge_brand / hinge_variant / hinge_overlay / hinge_angle 在 FurnitureSpec 定义了但连接件不读取 | FurnitureSpec → hinge.py | ⚠️ 字段空置 |

### ⚪ 间隙规则缺失

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 17 | 活动层板减尺量未定义（宽度应比内空小 2-4mm） | 未建模 | ⚠️ 需在拓扑或 spec 中定义 |
| 18 | 门板上下间隙应有别于左右间隙（上紧下松） | 未建模 | ⚠️ 目前 door_margin 四周统一 |
| 19 | 抽屉面板减尺未定义 | 未建模 | ⚠️ 依赖抽屉整体功能 |

### 其他

| # | 问题 | 位置 | 状态 |
|---|------|------|------|
| 20 | 榻榻米/床箱等水平柜体完全不支持 | 整体架构 | ⚠️ 拓扑数据 + CabinetFrame 已铺路，需增加 tatami_base.yaml 拓扑 |
| 21 | 转角柜不支撑 | 整体架构 | ⚠️ 拓扑需扩展多翼（multi-wing）描述 |

---

## 20260715.1

### 封边规则修正
- 所有柜体板件（侧板/顶板/底板/固定层板/活动层板/中竖板/踢脚板/门板）统一四边封边 ABS 1.0mm 同色
- 背板插槽模式不封边，内嵌/外盖模式四边同色

### 背板槽位置修正
- `groove_y = back_offset`，槽后壁对齐背板后面，间隙全放前面

### 三种背板安装方式 (back_mount)
- `FurnitureSpec` 新增 `back_mount: str = "auto"` 字段 + `resolve_back_mount()` 推导函数
- `"auto"` → `back_thickness >= board_thickness` 时 `"insert"`，否则 `"groove"`
- `"groove"` / `"insert"` / `"cover"` 可显式指定
- `CabinetLayout` 新增 `back_mount` 字段，`from_spec()` 按模式分流 side_depth / back_plane_y / internal_y_start
- `build_cabinet_panels()` 按三种模式生成不同尺寸/位置的背板
- `_edge_banding_for()` 控制背板封边；`_back_groove_operations()` 只在 groove 返回 4 条槽

| 模式 | side_depth | back_plane_y | 背板尺寸 | 槽 | 封边 |
|------|-----------|-------------|---------|-----|------|
| groove | d - door - hinge | back_offset(18) | int + 2×groove | 4条 | 无 |
| insert | d - door - hinge | back_offset(18) | int_w × int_h | 0 | 四边同色 |
| cover | d - door - hinge - back | 0 | width × height | 0 | 四边同色 |

### 背板拉条 (groove 模式)
- `FurnitureSpec` 新增 `back_rail_height: float = 70.0`
- 数量 = `internal_height // 500`，均分间隙
- 拉条类型 `back_rail`，Y 方向占 0~board_thickness，夹在左右侧板之间

### 封边规则修正
- 所有柜体板件（侧板/顶板/底板/固定层板/活动层板/中竖板/踢脚板/门板）统一四边封边 ABS 1.0mm 同色
- 背板插槽模式不封边，内嵌/外盖模式四边同色

### 背板槽位置修正
- `groove_y = back_offset`，槽后壁对齐背板后面，间隙全放前面

### 三种背板安装方式 (back_mount)
- `FurnitureSpec` 新增 `back_mount: str = "auto"` 字段 + `resolve_back_mount()` 推导函数
- `"auto"` → `back_thickness >= board_thickness` 时 `"insert"`，否则 `"groove"`
- `"groove"` / `"insert"` / `"cover"` 可显式指定
- `CabinetLayout` 新增 `back_mount` 字段，`from_spec()` 按模式分流 side_depth / back_plane_y / internal_y_start
- `build_cabinet_panels()` 按三种模式生成不同尺寸/位置的背板
- `_edge_banding_for()` 控制背板封边；`_back_groove_operations()` 只在 groove 返回 4 条槽

| 模式 | side_depth | back_plane_y | 背板尺寸 | 槽 | 封边 |
|------|-----------|-------------|---------|-----|------|
| groove | d - door - hinge | back_offset(18) | int + 2×groove | 4条 | 无 |
| insert | d - door - hinge | back_offset(18) | int_w × int_h | 0 | 四边同色 |
| cover | d - door - hinge - back | 0 | width × height | 0 | 四边同色 |

### 背板拉条 (groove 模式)
- `FurnitureSpec` 新增 `back_rail_height: float = 70.0`
- 数量 = `internal_height // 500`，均分间隙
- 拉条类型 `back_rail`，Y 方向占 0~board_thickness，夹在左右侧板之间
