# 当前程序存在问题清单

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
