# 板件阶段术语规范表

回答“`panel-plan` 阶段哪些术语是规范名，各自的单位和语义口径是什么？”；本文件是 `panel_plan` 阶段的术语唯一规范中心。

## 使用原则

- 文档、测试、代码和 API 契约只使用本文件中的规范名。
- 本阶段提案、序列化 spec、structure 和板件输出不接受历史别名；出现未知字段时运行时拒绝。
- 除专门声明外，线性尺寸统一为 mm；计数字段无单位。

## 规范名

| 概念 | 规范名 | 单位/类型 | 说明 |
| --- | --- | --- | --- |
| 家具类别 | `furniture_category` | 枚举 | 来自已确认 `DesignIntent`；本阶段不接受 `furniture_type` 或 `type`。 |
| 成品外包络宽 | `finished_envelope.width_mm` | mm | 意图阶段规范表达。序列化 `FurnitureSpec` 对应字段是 `width`。 |
| 成品外包络深 | `finished_envelope.depth_mm` | mm | 意图阶段规范表达。序列化 `FurnitureSpec` 对应字段是 `depth`。 |
| 成品外包络高 | `finished_envelope.height_mm` | mm | 意图阶段规范表达。序列化 `FurnitureSpec` 对应字段是 `height`。 |
| 挂装方式 | `hanging_mode` | 枚举 | 仅吊柜；规范值 `free_hanging_height`（自由挂高）/`flush_ceiling`（贴顶）。本阶段只读已确认意图，不解析挂装别名。 |
| 吊柜挂高 | `hanging_height_mm` | mm | 仅 `hanging_mode=free_hanging_height` 时有效。 |
| 门数量 | `n_doors` | 整数 | `panel_plan` 规范名是 `n_doors`。本阶段不接受 `door_count`。 |
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
| 板件柜内角色 | `role` | 字符串 | 柜内稳定角色名，如 `left_side_panel`。输出必须写出。 |
| 板件所属柜体 | `parent_id` | 标识符 | 必须等于所属 `cabinets[].id`。输出必须写出。 |
| 板件全局标识 | `id` | 字符串 | `{cabinet_id}__{role}`。输出不得再写裸角色名。 |
| 板件接触 | `joints` | 列表 | 该板参与的定向接触；每条是承面被端面顶住。 |

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
- `structure` 在本阶段指确定性柜体结构几何与内部净空，不指房间布局结果。
- `cabinets[]` 是板件阶段的对象树和检查点唯一形状；`spec/structure/panels` 只写在各柜体内。

## 本阶段不接受的历史名

- `furniture_type`、`type`：用 `furniture_category`。
- `door_margin`：用 `front_face_margin`。
- `door_count`：用 `n_doors`。layout 子系统仍用 `door_count` 作为自己的序列化名，但不进入本阶段提案或 structure。
- `movable_shelf_connector`、`door_hinge_side`：制造阶段输入，不是板件 spec 字段。
- `back_mount=auto`、`gap_below_mm="auto"`：不再接受；背板必须写 `groove`/`insert`/`cover`，计算层只写 `null`。
- `toe_kick_support_count=null`：不再接受；必须写非负整数。
- `female_id`、`male_id`：用 `bearing_id`/`end_id`。
- `male_z`、`male_size_z`：用 `end_z`/`end_size_z`。
- `door_hinge_gap`：用 `front_gap`。
- `cam_face`、`end_has_cam`、`end_cam_face`、`male_has_cam`、`male_cam_face`：本阶段不产出。
