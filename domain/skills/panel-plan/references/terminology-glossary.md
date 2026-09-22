# 板件阶段术语规范表

回答“`panel-plan` 阶段哪些术语是规范名，各自的单位和语义口径是什么？”；本文件是 `panel_plan` 阶段的术语唯一规范中心。

## 使用原则

- 文档、测试、代码和 API 契约只使用本文件中的规范名。
- 本阶段提案、序列化 spec、interior 和板件输出不接受历史别名；出现未知字段时运行时拒绝。
- 除专门声明外，线性尺寸统一为 mm；计数字段无单位。

## 规范名

| 概念 | 规范名 | 单位/类型 | 说明 |
| --- | --- | --- | --- |
| 家具类别 | `furniture_category` | 枚举 | 板件柜型，来自 CAD 单元外包络快照；本阶段不接受 `furniture_type` 或 `type`，也不读房间或摆放字段。 |
| 成品外包络宽 | `width` | mm | CAD 单元外包络快照。扁平协议可用 `finished_envelope.width_mm`，本阶段序列化 `FurnitureSpec` 只写 `width`。 |
| 成品外包络深 | `depth` | mm | CAD 单元外包络快照。扁平协议可用 `finished_envelope.depth_mm`，本阶段序列化 `FurnitureSpec` 只写 `depth`。 |
| 成品外包络高 | `height` | mm | CAD 单元外包络快照。扁平协议可用 `finished_envelope.height_mm`，本阶段序列化 `FurnitureSpec` 只写 `height`。 |
| 柜门数量 | `n_doors` | 整数 | 柜体前脸门板数。本阶段不接受 `door_count`。房间门洞是 layout 的 `openings[].kind=door`，不是本字段。 |
| 前脸四周边距 | `front_face_margin` | mm | 门板与抽屉前板共用的前脸边距。本阶段不接受 `door_margin`。 |
| 层板列表 | `shelves` | 列表 | 从上到下排列的结构化层板列表。 |
| 层板下净高 | `gap_below_mm` | mm 或 `null` | 字段名固定为 `gap_below_mm`；`null` 表示计算层。 |
| 顶格净高 | `top_gap_mm` | mm | 最上层板顶面到顶板底面的净高。 |
| 背板安装方式 | `back_mount` | 枚举 | 规范值 `groove/insert/cover`。 |
| 背板安装解析 | `back_mount_resolution.requested/effective` | 对象 | `requested` 保留请求值，`effective` 保留生效值。 |
| 踢脚支撑数量 | `toe_kick_support_count` | 整数 | 必须是非负整数。无踢脚时为 `0`。 |
| 料板厚 | `board_thickness` | mm | 柜体料档，目录 `18/22`，工艺卡默认 `18`。侧板、顶底、层板、踢脚、背拉条和抽屉盒都用这一档。不是每块板的独立厚度。 |
| 卷后背板厚 | `back_thickness` | mm | `groove/cover` 为常量 `9`；`insert` 等于料板厚。提案可省略。 |
| 门板厚 | `door_thickness` | mm | 料板目录 `18/22`。省略则等于 `board_thickness`。 |
| 柜体实例 | `cabinet_id` / `cabinets[].id` | 标识符 | 柜体父对象身份；缺省 `cabinet_1`。不得包含 `__`。 |
| 子装配 | `assemblies` | 对象 | 柜内 `carcass`、可选 `base`、`fronts`、`drawers[]`。检查点事实源。 |
| 底座工法 | `assemblies.base.construction` | 枚举 | 当前只允许 `integrated`（侧板落地，踢脚板挂在 `carcass`）。 |
| 内腔 | `interior.cavity` | 对象 | 可用内腔：`width/height/depth` 与最小角点 `origin.{x,y,z}`。不是缝隙 `clearance`。 |
| 内腔分区 | `interior.zones[]` | 列表 | `kind` 为 `doors` 或 `full_height_drawers`；成员是门板 id 或抽屉装配 id。 |
| 板件柜内角色 | `role` | 字符串 | 柜内稳定角色名，如 `left_side_panel`。输出必须写出。 |
| 板件所属柜体 | `parent_id` | 标识符 | 必须等于所属 `cabinets[].id`。输出必须写出。 |
| 板件所属子装配 | `assembly_id` | 标识符 | 如 `cabinet_1__carcass`、`cabinet_1__drawer_1`。输出必须写出。 |
| 板件全局标识 | `id` | 字符串 | `{cabinet_id}__{role}`。输出不得再写裸角色名。 |
| 板件接触 | `joints` | 列表 | 检查点写在所属子装配上；交接派生列表才回贴到板上。每条是承面被端面顶住。 |

## 接触口径

一条接触是定向面–端邻接：承面被端面顶住。角色属于这一条 `joints[]` 记录，不是板件属性。同一块板可以在不同接触里分别担任承面和端面。本阶段只推导接触，不解析连不连。输出键即下表规范名。

| 概念 | 规范名 | 单位/类型 | 说明 |
| --- | --- | --- | --- |
| 承面板件 | `bearing_id` | 标识符 | 拿出大面、被顶住的板。 |
| 端面板件 | `end_id` | 标识符 | 用厚度端顶住承面的板。 |
| 承面方向 | `face` | 面标记 | 承面所用语义面，值为该板 `inner_face`，如 `+x`。 |
| 端面轴 | `edge_axis` | `x`/`y`/`z` | 端面所在轴。 |
| 端面方向 | `edge_sign` | `+1`/`-1` | `+1` 为轴正端，`-1` 为轴负端。 |
| 端面件厚度中心 Z | `end_z` | mm | 几何基准。 |
| 端面件 Z 向尺寸 | `end_size_z` | mm | 横板时等于板厚。 |

## 几何字段口径

| 字段族 | 单位 | 口径 |
| --- | --- | --- |
| `size_x/size_y/size_z` | mm | 板件或操作在世界坐标 X/Y/Z 三轴上的尺寸。 |
| `pos_x/pos_y/pos_z` | mm | 板件或操作最小角点在世界坐标中的位置。 |
| `length_mm/width_mm` | mm | 下游报表用的二维成品尺寸字段；是派生命名，不替代 `size_*`。 |
| `local_x/local_y/local_z` | mm | 相对于所属板件局部坐标系的坐标。 |
| `diameter/depth` | mm | 孔径与钻入深度；虽然字段名未带 `_mm`，口径仍统一为 mm。 |

## 术语约束

- `front_face_margin` 表示前脸四周边距，并被门板与抽屉前板共同消费；讨论抽屉时不得把它写成独立的侧向净空。
- `front_gap` 表示门前脸与柜体前方的深度方向间隙，不等于门边缝。
- `back_offset` 表示背板基准相对柜体背侧的偏移；`cover` 模式下背板位于 `Y=0`，不再消费该偏移来决定内部起点。
- `panel` 在本阶段指制造板件记录，不指 CAD 实体、网格或 feature tree 节点。
- `interior` 在本阶段指柜体内腔与分区，不指房间布局、踢脚区或背板基准。
- `cabinets[]` 是板件阶段的对象树和检查点唯一形状；`spec/interior/assemblies` 只写在各柜体内，柜级不得再抄 `panels` 或 `structure`。

## 本阶段不接受的历史名

- `furniture_type`、`type`：用 `furniture_category`。
- `door_margin`：用 `front_face_margin`。
- `door_count`：柜门数量用 `n_doors`。房间门洞是 layout 的 `openings[]`（`kind=door`），不是本阶段字段。
- `hanging_mode`、`hanging_height_mm`、`origin_x_mm`、`origin_y_mm`、`origin_z_mm`、`rotation_z_deg`、`room_id`：布局摆放字段。CAD 单元上出现时本阶段忽略，不得写入板件提案。
- `movable_shelf_connector`、`door_hinge_side`：制造阶段输入，不是板件 spec 字段。
- `back_mount=auto`、`gap_below_mm="auto"`：不再接受；背板必须写 `groove`/`insert`/`cover`，计算层只写 `null`。
- `toe_kick_support_count=null`：不再接受；必须写非负整数。
- `connection`：接触上的连不连。旧冻结接触里出现时丢掉，不在本阶段保存。
- `female_id`、`male_id`：用 `bearing_id`/`end_id`。
- `male_z`、`male_size_z`：用 `end_z`/`end_size_z`。
- `door_hinge_gap`：用 `front_gap`。
- `cam_face`、`end_has_cam`、`end_cam_face`、`male_has_cam`、`male_cam_face`：本阶段不产出。
