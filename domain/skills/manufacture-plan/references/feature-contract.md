# 特征契约（制造层）

状态：**已落地**。特征已拆成**判别联合**（基类 `Feature` +
`HoleFeature` / `GrooveFeature` / `EdgeBandFeature` 三子类），无损转换函数均已落地；
连接点（`ConnectionPoint`）实体已落地。**生产端已反转**：`plan_manufacturing` 先生成
一次孔 → Feature + ConnectionPoint（本源），BOM/校验/导出从它们派生（不再从 BOM 反推）。
BOM 展示（`format_bom_markdown`）仍读原始结构，待后续。
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

一处加工动作，挂在某块板上。用**判别联合**表示：基类 `Feature` + 三个子类。
这是**继承**关系（一个特征实例是三种之一），不是组成关系（不是「一个特征分成三个」）。
类型判断用 `isinstance(feature, HoleFeature)`，不靠 `kind` 字符串。

### 基类 Feature（三种加工共有的字段）

| 字段 | 含义 |
|------|------|
| `panel_label` | 宿主板 |
| `x_local` / `y_local` / `z_local` | 局部原生位置（板件参考系） |
| `x_global` / `y_global` / `z_global` | 柜体坐标（派生，迁移期保留，目标现算） |
| `note` | 备注 |

### 三个子类（各自专属字段）

| 子类 | 加工 | 专属字段 |
|------|------|---------|
| `HoleFeature` | 打孔 | `hole_type`、`diameter`、`depth`、`direction`、`is_face_hole`、`connection_id` |
| `GrooveFeature` | 开槽 | `feature_id`、`size_x/y/z` |
| `EdgeBandFeature` | 封边 | `edges`、`material` |

### 规格 vs 特征（两层，不混）

- **规格（`hole_type`）** = 「哪种孔」，共享，写在目录里，映射到五金材料；
- **特征（`Feature`）** = 「哪个位置的孔」，每个位置一个；
- **数量** = 数特征（数位置），不存进特征字段。

8 个同规格孔 = 1 种规格 + 8 个特征 → BOM「预埋螺母 × 8」。

### 材料不存进特征

`HoleFeature` 只存 `hole_type`；「这个孔消耗哪种五金」由 `hole_type` 查目录得到。
目录是单一真源，不在每个孔上各抄一遍材料、避免抄着抄着不一致。

## 连接点（ConnectionPoint）

一个三合一 = 轮孔 + 杆孔 + 螺母孔 = 一个连接点，本质是「一件事：把两块板连起来」。

- ✅ 实体已落地（`connection_points.py`）：`ConnectionPoint` 持有稳定 id（`connection_id`）+
  结构字段 `bearing_id`/`end_id`/`row_index`/`owner`（归属连接件）+ 组成孔 `holes`；
- `collect_connection_points(holes, owner=...)` 按 `connection_id` 把孔分组为连接点
  并打上 owner；`connection_id` 字符串仍保留在 `HoleSpec`/`HoleFeature` 上作为主键
  （供导出/Viewer 分组）；
- ✅ 反转彻底：`plan_manufacturing` 先生成一次孔 → 带 owner 的 ConnectionPoint +
  Feature（本源），BOM/校验/导出都从它们派生——三合一/背板校验按 owner 过滤读
  `bom.connection_points`，不再各自重新生成孔；「删一个孔出孤儿」由快照缺件直接暴露；
- 生产端仍逐孔产出 `HoleSpec`（`make_connection_id` 逐孔打标），连接点在规划阶段
  统一分组打标——「由连接件直接产出 ConnectionPoint」仍为可选后续。

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

1. ✅ Feature 契约 + `HoleFeature`，无损装 `HoleSpec`；
2. ✅ 槽（`cut_box`）、封边 → `GrooveFeature` / `EdgeBandFeature` 的**契约与转换函数**
   已落地（`from_machining_operation` / `from_edge_banding` + 无损测试），并已拆成
   判别联合（基类 + 三子类）；`collect_features` 统一入口、校验（孔/槽/封边）与
   孔导出（`emit_drilled_holes`）均已改为遍历 Feature；BOM 展示
   （`format_bom_markdown`）仍读原始结构，待后续；
3. ✅ `connection_id` → `ConnectionPoint` 实体（`connection_points.py` + 按点校验 + 契约测试）；
4. ✅ 生产端反转：`plan_manufacturing` 先生成一次孔 → Feature + ConnectionPoint
   （带 `owner` 归属），BOM（hardware）从它们派生；`BOMReport` 承载
   `features`/`connection_points`；校验/BOM 按 owner 过滤读 `bom.connection_points`；
   Feature 增加 `kind` + `feature_from_dict` 序列化往返；`revise_stage_output`
   直接编辑制造输出后重算派生快照（`recompute_features`）。

## 验证判据

- ✅ 第一步：Feature 能无损装下 `HoleSpec` 全部字段（测试覆盖）；
- ✅ 第二步：同一个校验/导出入口同时处理孔/槽/封边（`collect_features` + 校验遍历，测试覆盖）；
- ✅ 第三步：连接点实体按点校验（每个点 1 轮 + 1 杆 + 1 螺母，测试覆盖）。
