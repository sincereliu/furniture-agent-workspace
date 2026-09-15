# 制造层数据流梳理（工作稿）

> **目的**：建立制造层的「数据流 + 字段所有权」地图，找出四类问题（越界 / 丢失 / 无主 / 死字段）与抽象机会。
> **范围**：仅制造层（`domain/skills/manufacture-plan`）。
> **方法**：每个字段问四句——① 越界？消费者是否自造了非自己所有的数据 ② 丢失？上游知道却没传下来 ③ 无主？没有明确所有者或派生规则 ④ 死字段？没有消费者。
> **状态**：工作稿，逐层补充；梳理完成后统一整理、合并。
> **背景**：发现 A（`length_mm/width_mm` 轴映射错误）暴露的问题，是本轮梳理的起点。

---

## L1 输入层：4 段输入的职责边界

`plan_manufacturing` 的输入是 4 段：

```python
def plan_manufacturing(
    spec: FurnitureSpec,
    placements: list[PanelPlacement],
    *,
    requested_options: Mapping[str, Any] | None = None,
    appearance: Mapping[str, Any] | None = None,
) -> BOMReport:
```

### 1.1 两分法：事实 vs 决策

| # | 输入 | 性质 | 所有者 | 生产者 | 制造层能否改 |
|---|---|---|---|---|---|
| 1 | `spec` | 柜体规格**事实** | 设计层冻结 | panel-plan | 否（只读） |
| 2 | `placements` | 板件几何**事实** | 设计层冻结 | panel-plan（topology_solver） | 否（只读） |
| 3 | `requested_options` | 制造**决策** | 制造层 | LLM 提案 + 代码准入 | 是 |
| 4 | `appearance` | 制造**决策** | 制造层 | LLM 提案 + 代码准入 | 是 |

**关键判断**：1、2 是「设计层冻结的事实」，3、4 是「制造层的决策」。制造层可以自由产生决策，但**不得重新定义事实**——发现 A 的病灶正是「把事实（板件平面尺寸）当成了可以自己拼装的东西」。

### 1.2 各段内容与作用

**`spec`（FurnitureSpec，28 字段）**——柜体的整体规格事实：

| 分组 | 字段 | 作用 |
|---|---|---|
| 外形 | `furniture_category`, `width`, `depth`, `height` | 柜型与外包络 |
| 料厚 | `board_thickness`, `back_thickness`, `door_thickness`, `drawer_bottom_thickness`, `drawer_back_thickness` | 各角色板件的厚度（**权威来源**） |
| 背板 | `back_mount`, `back_offset`, `back_rail_height`, `groove_depth`, `groove_clearance` | 背板安装方式与槽参数 |
| 门/抽屉 | `n_doors`, `drawer_count`, `drawer_side_clearance`, `drawer_layer_gap`, `drawer_back_clearance` | 门抽屉配置与净空 |
| 踢脚 | `toe_kick_height`, `toe_kick_reveal_front`, `toe_kick_reveal_back`, `toe_kick_support_count` | 踢脚尺寸 |
| 前脸 | `front_face_margin`, `front_gap` | 门缝与边距 |
| 层板 | `shelves`, `top_gap_mm` | 层板布局 |

**`placements`（PanelPlacement，20 字段）**——每块物理板件的事实：

| 分组 | 字段 | 作用 |
|---|---|---|
| 身份 | `id`, `name`, `panel_type`, `role`, `parent_id` | 板件标识与归属柜体 |
| 几何 | `size_x`, `size_y`, `size_z`, `pos_x`, `pos_y`, `pos_z` | **世界坐标**三轴尺寸与最小角点 |
| 朝向 | `orientation`（**空置**）, `inner_face`, `outer_face` | 板件朝向与内外可见面 |
| 材质角色 | `material_role` | carcass / door / back |
| 接触 | `joints` | 面-边接触拓扑（承面/端面） |
| 其他 | `quantity`, `depends_on`, `note`, `door_overlay` | 数量、依赖、备注、门盖方式 |

**`requested_options`（4 个合法键）**——制造层选型：

| 键 | 作用 |
|---|---|
| `options` | 连接件嵌套选项（透传给各 `Connector.boms`） |
| `movable_shelf_connector` | 活动层板连接方式（`two_in_one` / `shelf_pin`） |
| `door_hinge_side` | 单门铰链侧（`left` / `right`） |
| `edge_banding` | 封边皮选型（`{material, thickness}`） |

**`appearance`**——按材质角色的材质选型：

```python
{"carcass": {"substrate": ..., "surface": ...},
 "door":    {"substrate": ..., "surface": ...},
 "back":    {"substrate": ..., "surface": ...}}
```

### 1.3 L1 初步观察

- **事实与决策混在同一个函数签名里**，且都是「无类型约束的 Mapping」——`requested_options` / `appearance` 靠运行时校验，事实类输入（`spec` / `placements`）靠类型。这个不对称是合理的（决策是开放的，事实是封闭的），但值得记录。
- `placements` 里**已有 `orientation` 字段但空置** → 已确认的「丢失」型问题（发现 A 的根因之一）。
- `spec` 承担了「料厚权威」的角色（`board_thickness` 等），而制造层的 `PanelRecord.thickness` 正是从它取的——**对照发现 A**：同一条记录里，`thickness` 取自权威来源，`length_mm/width_mm` 却靠坐标轴猜，两者来源标准不一致。

---

## L2 字段血缘（关键字段）

### 2.1 判据

每个字段问四句：**越界**（消费者自造了非自己所有的数据）？**丢失**（上游知道却没传）？**无主**（没有所有者或派生规则）？**死字段**（没有消费者）？

「所有者」= **有权定义该字段语义的阶段**，不一定等于生产者。

### 2.2 关键字段表

| 字段 | 生产者 | 消费者 | 所有者 | 用途 | 判定 |
|---|---|---|---|---|---|
| `size_x/y/z` | panel-plan（topology_solver） | 制造层孔位/校验多处 | 设计层 | 几何 | ✅ |
| `length_mm` / `width_mm` | **制造层自造**（`_manufacturing_panel`：固定取 `size_x`/`size_y`） | `area_m2`、markdown 开料尺寸、`estimate_materials` 封边皮周长 | **设计层**（板件平面尺寸） | 展示 + 计算 | ❌ **越界 + 无主**（发现 A：派生规则从未定义） |
| `thickness` | 制造层（按 `material_role` 从 `spec` 取） | 铰链门厚校验、`hole_validator`、材料分组键、封边皮宽度、markdown | 设计层（`spec` 料厚） | 加工 + 计算 + 展示 | ✅ 来源权威 |
| `material`（字符串 `"18mm柜体板"`） | 制造层自造（f-string 拼） | **无消费者** | 制造层 | — | ❌ **死字段 + 越界**（由 `thickness`+`material_role` 可派生） |
| `material_role` | panel-plan 提供，**未收进 `PanelRecord`** | `_normalize_appearance`、`_manufacturing_panel`（仅 placement 层面） | 设计层 | 材质角色 | ❌ **丢失**（appearance 一致性校验因此做不了） |
| `substrate` / `surface` | 制造层（appearance 物化，`_manufacturing_panel`） | `validation`、`estimate_materials`、`_material_label` | 制造层 | 计算 + 展示 + 校验 | ⚠️ 健康，但与 `BOMReport.appearance` 冗余 |
| `edge_banding` | 制造层（`build_edge_banding`） | `from_edge_banding`、`estimate_materials`、`edge_banding_summary` | 制造层 | 加工 + 计算 + 展示 | ✅ |
| `orientation` | **无** | **无** | （应为设计层） | — | ❌ **死字段 + 丢失**（发现 A 的根因之一） |
| `inner_face` / `outer_face` | panel-plan | `_cam_face_for`、封边/可见面判断 | 设计层 | 几何 | ✅ |
| `cam_face` | 制造层（`panel_type` + `inner_face`/`outer_face` 推） | `trinity` 决定偏心轮孔位 | 制造层 | 加工 | ✅ **用了语义字段，非坐标轴猜** |
| `joints` | panel-plan（`compute_joints`） | 制造层重解析 `connection`、三合一打孔 | 设计层 | 几何 + 加工 | ✅ |
| `area_m2` | `PanelRecord` property（`length_mm × width_mm`） | `total_area_m2`、`estimate_materials` 基材/饰面面积 | 制造层 | 计算 + 展示 | ❌ **被发现 A 污染** |
| `volume_m3` | `PanelRecord` property | **无消费者** | 制造层 | — | ❌ **死字段** |
| `total_area_m2` | `plan_manufacturing` | `validation`（仅查 `> 0`）、markdown、workflow 读回 | 制造层 | 展示 + 弱校验 | ❌ 受污染 + 校验弱 |

### 2.3 L2.1 首轮小结

关键字段里已经出现**四类问题齐活**：

- **越界**：`length_mm/width_mm`、`material`——制造层造了本该由设计层定义的板件属性。
- **丢失**：`orientation`、`material_role`——上游有（或用得上），却没进数据/记录。
- **无主**：`length_mm/width_mm`——术语表只给了「派生命名」四个字，没有派生规则。
- **死字段**：`material`、`volume_m3`、`orientation`——零消费者。

一条**对照线索**：同一文件里 `cam_face`（用 `inner_face` 语义字段推）是健康的，`length_mm`（按坐标轴猜）是坏的。**差别只在「有没有用上游传下来的知识」**——这是本轮梳理最该复用的判据。

---

## L3 阶段数据流（制造层）

### 3.1 内部处理链

```
4 段输入
  ├─ spec / placements ................. 设计层事实（只读）
  └─ requested_options / appearance ..... 制造层决策
        │
        ▼ 准入（查表校验，失败即拒）
   _normalize_appearance               → appearance_by_role
   _normalize_edge_banding_selection   → 封边皮选型
   movable_shelf_connector / door_hinge_side 校验与派生
        │
        ▼ 逐块板物化 _manufacturing_panel(placement, 选型)
     ├─ material / thickness   ← spec + material_role（权威来源）
     ├─ substrate / surface    ← appearance 选型（物化）
     ├─ edge_banding           ← build_edge_banding(thickness, surface, 选型)
     ├─ cam_face               ← _cam_face_for(placement)（用 inner/outer_face）
     ├─ drill_length           ← placement.joints / panel_type
     └─ length_mm / width_mm   ← placement.size_x / size_y   ← ❌ 发现 A
        │
        ▼ panels
        ├─ _resolve_joint_connections（重解析 connection）
        ├─ _back_groove_operations（槽）
        └─ _derive_features_and_points
              ├─ 三合一/背板：按连接点产出 ConnectionPoint（holes 即 HoleFeature）
              ├─ 其余连接件：逐孔 → HoleFeature
              ├─ 槽 → GrooveFeature
              └─ 封边 → EdgeBandFeature
        │
        ▼ 本源 features + connection_points
        ├─ estimate_hardware   → HardwareRecord[]（从 Feature/ConnectionPoint）
        └─ estimate_materials  → MaterialRecord[]（从 panels 的 substrate/surface/edge_banding）
        │
        ▼ BOMReport（唯一出口）
```

### 3.2 输出字段的消费者（决定验证强度）

| BOMReport 字段 | 消费者 | 消费者类型 |
|---|---|---|
| `panels.size_*` / `pos_*` | feature-tree → CAD | **计算型**（几何错了会炸） |
| `panels.panel_type/role/parent_id/depends_on` | feature-tree | 计算型 |
| `operations` | feature-tree → CAD | 计算型 |
| `width/depth/height/board_thickness/furniture_category` | feature-tree | 计算型 |
| `readiness` | delivery（门禁） | 计算型 |
| `features` | validation、emit_drilled_holes | 计算型 |
| `connection_points` | validation、`connector.boms` | 计算型 |
| `hardware` | markdown、validation（数量） | 弱 |
| `appearance` | validation（完整性） | 弱 |
| `panels.length_mm/width_mm` | markdown、`estimate_materials` | **仅展示 + 无验证的计算** |
| `total_area_m2` | markdown、validation（仅 `>0`） | 仅展示 |
| `materials`（新） | **markdown 唯一** | 仅展示 |
| `panels.material` / `volume_m3` | **无** | 无 |

### 3.3 L3 关键发现：验证强度 = 「消费者类型」

- **几何字段**（`size_*` / `pos_*` / `operations`）有 feature-tree 这个**计算型下游**——它们进 CAD、错了会炸，所以**天然被验证**。
- **报表字段**（`length_mm/width_mm`、`total_area_m2`、`materials`）只有 **markdown 展示**下游——错了没人知道。**这正是发现 A 存活两个月的原因。**
- **今日自我警示**：我新加的 `materials` 现在也**只有 markdown 一个消费者**，落在与当年 `area_m2` 完全相同的处境。若不接一个计算型消费者（采购 / 排版 / 成本 / 校验），它的错误同样不会被发现。

> **一句话**：有没有「计算型下游」决定字段是否被验证；纯展示字段会带病存活。这既解释了发现 A，也是往后加字段时的检查项。
