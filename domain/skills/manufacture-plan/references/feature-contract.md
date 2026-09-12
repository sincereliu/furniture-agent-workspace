# 特征契约（制造层）

状态：**契约先行，逐步实施**。`kind="hole"`（孔）、`kind="groove"`（槽）、
`kind="edge_band"`（封边）三种特征的契约与无损转换函数均已落地；连接点
（`ConnectionPoint`）实体在第三步落地。校验/导出改为「遍历 Feature」仍待后续。
代码骨架见 `scripts/furniture_manufacturing/features.py`。

## 目标抽象（一句话）

制造层把「每一处加工」统一为「特征」，把「配对的孔」打包为「连接点」；
BOM、校验、导出、设备路线都是它们的派生或标注。

## 三个层次

| 层 | 回答的问题 | 归属 |
|----|-----------|------|
| 设计层 | 谁和谁接触（装配关系）、背板模式 | design-intent / panel-plan |
| 工艺层 | 连不连、铰链侧、具体用哪种五金（含活动层板连接件）、连在哪、打什么孔、买多少 | manufacture-plan |
| 物理层 | 真做出来 | 工厂（仓库之外，只出机器文件） |

分界线的判据是「改变面板几何 vs 只改变加工/五金」：**改变面板几何（尺寸/位置/拓扑）
→ panel-plan；只改变孔/槽/封边/BOM → manufacturing。** 设计层产出 `PanelJoint` 拓扑
（`bearing_id/end_id/face/edge`）；不产孔位、不选五金、不决定连不连与铰链侧——那些由制造层
决定/推导（「用什么五金仍由制造连接件决定」）。孔位是「实现」不是「目标」：它在工艺层
由代码确定性推导，不在设计层定。

## 爆炸半径判据：一个输入放哪，由「改它要重跑多远」决定

五金选型只影响孔位和 BOM，不改变面板尺寸/拓扑。若它放在 panel-plan，改五金会让
panel-plan 失效、从面板重跑——面板其实没变，白跑且修订语义错误（记录说「板件变了」）。

| 选型放哪 | 改五金后的重跑范围 | 对不对 |
|---------|-------------------|--------|
| panel-plan（现状） | panel-plan + manufacturing + feature-tree + CAD + delivery | ❌ 面板没变却全重跑 |
| manufacture-plan（应然） | manufacturing + feature-tree + CAD + delivery | ✅ 面板不动 |

判据一句话：**只影响制造的东西就放制造阶段，让爆炸半径止于制造；只有真正改变面板
结构的东西才放 panel-plan。** 也可表述为「改变面板几何 vs 只改变加工/五金」——
改面板几何才重跑面板，只改孔/槽/封边/BOM 就只重跑制造。

### 待迁移（现状 → 目标）

- ✅ `movable_shelf_connector`（活动层板 two_in_one/shelf_pin）：**已迁移**。已从
  panel-plan 的 `FurnitureSpec` 移除，改为制造阶段 `requested_options` 输入，经
  `plan_manufacturing` 盖章到 `PanelRecord`；有活动层板却未提供时运行时拒绝。改它只
  重跑 manufacturing 及下游。
- ✅ `connection`（连不连 on/off）：**已迁移**。panel-plan 不再解析，制造层在
  `plan_manufacturing` 按面板类型重解析（`default_joint_connection`）；拓扑
  （`bearing_id/end_id/face/edge`）留在 panel-plan。
- ✅ `door_hinge_side`（铰链侧）：**已迁移**。单门为制造输入（`requested_options`，
  `left`/`right`），双门由制造按门板 X 位置派生；panel-plan 不再携带。
- `back_mount`（groove/insert/cover）**留在** panel-plan：它改变背板尺寸与柜体深度
  （结构决策），改它本就该重跑面板。
- 固定柜体三合一当前硬编码在制造 `Connector`（只有一种可选）；将来多选时按
  「选型=决策、参数=计算」上提为可确认项，仍落在制造层。

剩余待办：固定柜体三合一的「选型」上提（当前只有一种可选，暂无用户爆炸半径问题）。

## 特征（Feature）

一处加工动作，挂在某块板上。字段：

| 字段 | 含义 | 现状 |
|------|------|------|
| `kind` | 特征种类：`hole` / `groove` / `edge_band` | 只实现 `hole` |
| `panel_label` | 宿主板 | 来自 `HoleSpec` |
| `x_local` / `y_local` / `z_local` | 局部原生位置（板件参考系） | 来自 `HoleSpec` |
| `hole_type` | 孔型（「哪种孔」，经目录映射到五金材料） | 来自 `HoleSpec` |
| `diameter` / `depth` / `direction` / `is_face_hole` | 形状规格 | 来自 `HoleSpec` |
| `connection_id` | 连接点引用（字符串，待升级实体） | 来自 `HoleSpec` |
| `x_global` / `y_global` / `z_global` | 柜体坐标（派生，迁移期保留，目标现算） | 来自 `HoleSpec` |
| `note` | 备注 | 来自 `HoleSpec` |

### 规格 vs 特征（两层，不混）

- **规格（`hole_type`）** = 「哪种孔」，共享，写在目录里，映射到五金材料；
- **特征（`Feature`）** = 「哪个位置的孔」，每个位置一个；
- **数量** = 数特征（数位置），不存进特征字段。

8 个同规格孔 = 1 种规格 + 8 个特征 → BOM「预埋螺母 × 8」。

### 材料不存进特征

特征只存 `hole_type`；「这个孔消耗哪种五金」由 `hole_type` 查目录得到。
目录是单一真源，不在每个孔上各抄一遍材料、避免抄着抄着不一致。

## 连接点（ConnectionPoint）

一个三合一 = 轮孔 + 杆孔 + 螺母孔 = 一个连接点，本质是「一件事：把两块板连起来」。

- 现状：`connection_id` 只是 `HoleSpec` 上的字符串字段（`<female>→<male>#<排次>`）；
- 目标（第三步）：升级为实体，支持整体增删、按点校验，消除「删一个孔出孤儿」；
- 现状已做到：校验按 `connection_id` 对齐（每个连接点恰好 1 轮 + 1 杆 + 1 螺母）。

## 派生规则

| 派生 | 规则 |
|------|------|
| BOM | 数特征/连接点 + 查目录映射（「哪种 × 多少个」） |
| 校验 | 遍历特征查几何 + 遍历连接点查配对 |
| 导出 | 遍历特征 |
| 设备路线 | 单独一层：选机器 + 查机器参数表，不在特征里 |

## 边界（LLM 提案、代码准入）

- 选五金变体（哪种连接方式）= LLM/用户决策（数值假设标为待确认）；
- 算孔位 = 代码确定性推导（给定 joint + 连接方式，孔位必然算得出）；
- 设备路线 = 投产前决策 / 仿真优化，不硬编码进特征；
- 材料映射 = 目录（数据），代码只查表不猜。

## 实施路径

1. ✅ Feature 契约 + `kind="hole"`，无损装 `HoleSpec`；
2. ✅ 槽（`cut_box`）、封边 → `kind="groove"` / `kind="edge_band"` 的**契约与转换函数**
   已落地（`from_machining_operation` / `from_edge_banding` + 无损测试）；校验/导出改为
   遍历 Feature 尚待后续；
3. `connection_id` → `ConnectionPoint` 实体。

## 验证判据

- 第一步：Feature 能无损装下 `HoleSpec` 全部字段（测试覆盖）；
- 第二步：同一个校验/导出入口同时处理孔与槽；
- 第三步：删一个连接点 → 三个孔 + BOM 数量一起消失，校验通过。
