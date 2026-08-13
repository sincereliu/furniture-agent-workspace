# 更新日志

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
