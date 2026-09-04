# 板件阶段术语规范表

回答“`panel-plan` 阶段哪些术语是规范名，哪些只是兼容别名，各自的单位和语义口径是什么？”；本文件是 `panels_planned` 阶段的术语唯一规范中心。

## 使用原则

- 文档、测试、新代码和新 API 契约默认使用本文件中的规范名。
- 兼容别名只用于旧 Project 迁移、扁平 API 兼容或历史测试夹具；新增逻辑不得再扩展新别名。
- 若规范名与兼容别名同时出现且值冲突，运行时必须拒绝，而不是猜测。
- 除专门声明外，线性尺寸统一为 mm；计数字段无单位。

## 规范名与兼容别名

| 概念 | 规范名 | 兼容别名 | 单位/类型 | 说明 |
| --- | --- | --- | --- | --- |
| 家具类别 | `furniture_type` | `type` | 枚举 | `DesignIntent` 与执行期内部统一用 `furniture_type`；历史 `type` 只在旧序列化 spec 加载时恢复。 |
| 成品总宽 | `overall_size.width_mm` | `width` | mm | 意图阶段规范表达是 `width_mm`；扁平 API 兼容 `width`。 |
| 成品总深 | `overall_size.depth_mm` | `depth` | mm | 意图阶段规范表达是 `depth_mm`；扁平 API 兼容 `depth`。 |
| 成品总高 | `overall_size.height_mm` | `height` | mm | 意图阶段规范表达是 `height_mm`；扁平 API 兼容 `height`。 |
| 吊柜挂高 | `mounting_height_mm` | `mounting_height` | mm | 仅 `mount_mode=free_height` 时有效。 |
| 门数量 | `n_doors` | `door_count` | 整数 | `panels_planned` 规范名是 `n_doors`；`door_count` 仅保留给 layout 序列化与旧数据迁移。 |
| 前脸四周边距 | `front_face_margin` | `door_margin` | mm | 门板与抽屉前板共用的前脸边距；`door_margin` 仅作历史兼容名。 |
| 层板列表 | `shelves` | 无 | 列表 | 从上到下排列的结构化层板列表。 |
| 层板下净高 | `gap_below_mm` | `auto` 仅作值别名 | mm 或 `null` | 字段名固定为 `gap_below_mm`；值 `null`/`auto` 表示计算层。 |
| 顶格净高 | `top_gap_mm` | 无 | mm | 最上层板顶面到顶板底面的净高。 |
| 背板安装方式 | `back_mount` | 无 | 枚举 | 规范值 `auto/groove/insert/cover`。 |
| 背板安装解析 | `back_mount_resolution.requested/effective` | 无 | 对象 | `requested` 保留请求值，`effective` 保留生效值。 |
| 踢脚支撑数量 | `toe_kick_support_count` | 无 | 整数或 `null` | `null` 是“显式请求自动计算”，不是缺省。 |
| 单门铰链侧 | `door_hinge_side` | 无 | 枚举或 `null` | 仅 `n_doors=1` 时允许 `left/right`。 |
| 活动层板连接方式 | `movable_shelf_connector` | 无 | 枚举 | 规范值 `two_in_one/shelf_pin`。 |

## 几何字段口径

| 字段族 | 单位 | 口径 |
| --- | --- | --- |
| `size_x/size_y/size_z` | mm | 板件或操作在世界坐标 X/Y/Z 三轴上的尺寸。 |
| `pos_x/pos_y/pos_z` | mm | 板件或操作最小角点在世界坐标中的位置。 |
| `length_mm/width_mm` | mm | 制造/BOM 视图中的二维成品尺寸字段；是面向报表的派生命名，不替代 `size_*`。 |
| `local_x/local_y/local_z` | mm | 相对于所属板件局部坐标系的孔位或操作坐标。 |
| `diameter/depth` | mm | 孔径与钻入深度；虽然字段名未带 `_mm`，口径仍统一为 mm。 |

## 术语约束

- `front_face_margin` 表示前脸四周边距，并被门板与抽屉前板共同消费；讨论抽屉时不得把它写成独立的“滑轨净空”。
- `door_hinge_gap` 表示门前脸与柜体前方的铰链深度方向间隙，不等于门边缝。
- `back_offset` 表示背板基准相对柜体背侧的偏移；`cover` 模式下背板位于 `Y=0`，不再消费该偏移来决定内部起点。
- `panel` 在本阶段指制造板件记录，不指 CAD 实体、网格或 feature tree 节点。
- `structure` 在本阶段指确定性柜体结构几何与内部净空，不指房间布局结果。

## 禁止扩散的历史叫法

- 新文档和新代码不要把 `furniture_type` 再写回 `type`。
- 新文档和新代码不要把 `n_doors` 再写成主名 `door_count`；新 panel 请求不得再提交 `door_count`。
- 新文档和新代码不要再把 `front_face_margin` 写回历史名 `door_margin`。
- 新文档和新代码不要在同一语境里混用“门边缝”“门缝”“前脸边距”而不指明对应字段。
- 若返回值继续保留不带 `_mm` 的几何字段，必须在契约或响应模型中明确声明其单位是 mm。

## 剩余兼容边界

| 历史名 | 当前保留点 | 是否还能继续删 | 删除条件 |
| --- | --- | --- | --- |
| `type` | `panel_spec.py::FurnitureSpec.from_dict()` | 暂不能 | 仍需加载历史序列化 spec；等旧快照/旧 Project 不再需要恢复时再删。 |
| `door_count` | `workflow_project.py::_legacy_stage_inputs()` | 暂不能 | 仅服务 schema-v1 项目加载；停止支持 v1 项目后可删。 |
| `door_count` | `panel_spec.py::migrate_legacy_panel_hinge_side()` 与 `_legacy_spec_loader_panel_output_door_count()` / `_legacy_spec_loader_panel_input_door_count()` | 暂不能 | 仅服务旧 panel 输出恢复；历史 Revision 退场后可删。 |
| `door_count` | `layout_spec.py::LayoutSpec` | 暂不能 | 这是 layout 子系统当前序列化名；要删需单独做 layout API/存储协调迁移。 |