# 更新日志

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
