# 空间布局规则

回答“当前固定柜体模板占据哪些空间，以及它在房间的哪个位置？”；位于意图后、板件前，计算成品包络、内部净空和可选的房间定位，不生成板件或 CAD。

## 坐标约定

- 默认毫米，柜体局部 `W×D×H` 对应 X 左→右、Y 后→前、Z 向上。
- 柜体局部原点 `(0,0,0)` 为成品外包络左后下落地角；用范围/偏移描述区域，不转成 CAD 基元中心。
- 房间原点是平面图西南角的地面点；房间 X 向东、Y 向北、Z 向上。
- `room_placement.placement` 将柜体局部原点转换到房间坐标；`rotation_z_deg` 从房间 X 轴逆时针计算。

## 房间定位输入

房间定位是可选能力，但 `layout.room` 和 `layout.placement` 必须同时存在。

`room`：

- `id/name`：房间标识与展示名。
- `width_mm/depth_mm/height_mm`：当前支持矩形房间。
- `openings[]`：门窗所在 `wall`、沿墙 `offset_mm`、宽高和窗台高。
- `obstacles[]`：柱、管井等轴对齐长方体的位置与尺寸。

沿墙偏移按房间边界顺时针定义：

- `south`：西 → 东；
- `east`：南 → 北；
- `north`：东 → 西；
- `west`：北 → 南。

`placement.mode=wall` 使用 `host_wall + offset_mm + origin_z_mm`，运行时自动推导原点和朝向，使柜体背面贴墙、正面朝向室内。`placement.mode=free` 使用 `origin_x_mm/origin_y_mm/origin_z_mm + rotation_z_deg`。

布局必须拒绝以下情况：柜体越出房间、超过层高、与障碍物发生正体积相交，或沿宿主墙遮挡垂直范围相交的门窗。边界接触不视为碰撞。

## 当前可执行决策

- 尺寸口径：成品、柜体、内部净空或洞口。
- 背板：解析后的 `groove/insert/cover`、柜体前后范围、背板基准和内部 Y 起点。
- 底部：当前模板只支持吊柜无踢脚，或地柜的固定踢脚高度与前后退让。
- 数量：只传递固定层板数量和门板数量，不计算格位、开口、门型或开启轨迹。

当前运行时不表示开放格、隔板分区、抽屉、挂衣/设备/装饰区、滑门、盖门/嵌门、固定/可调层板差异。出现这些要求时，返回意图阶段作为未决项；不得静默丢弃后继续。房间安装障碍只按本文件的长方体包络校验，不推断基层、管线或现场可施工性。

## 运行时输出

`CabinetLayout` 只保存成品包络、有效 `back_mount`、`carcass_y_start/end`、`internal_x/y/z_start/end`、柜体深度、背板基准、踢脚区和 `shelf_count/door_count`；不含分区/开口集合、开启策略、`PanelPlacement`、板件记录或裁切尺寸。

完整 `layout_planned` 输出保持 `layout` 向后兼容；有房间定位时增加：

- `room_placement.room`：标准化房间、门窗和障碍物；
- `room_placement.placement`：已解析的房间原点、标高、旋转及宿主墙；
- `room_placement.furniture_footprint`：房间平面坐标中的四角占地；
- `room_placement.clearances_mm`：西、东、南、北、地面和顶面的净距；
- `preview`：`image/svg+xml` 内联平面预览、尺寸和替代文本。

预览必须由当前房间、柜体包络和定位实时重建；修改定位后不得沿用旧占地或旧 SVG。

背板模式的布局契约：

| 模式 | `carcass_y_start` | 背板基准 | 内部空间起点 |
|------|--------------------|----------|----------------|
| `groove` | `0` | `back_offset` | 槽前侧，即 `back_offset + back_thickness` |
| `insert` | `0` | `back_offset` | 内嵌背板前侧，即 `back_offset + back_thickness` |
| `cover` | `back_thickness` | `0` | 柜体后侧，即 `back_thickness` |

柜体和门板须位于同一成品深度包络；外盖背板占后侧厚度，不得与柜体重叠。

最终内部净空以本阶段实时计算的 `internal_x/y/z_start/end` 为准。净宽、净高、净深必须为正，且与成品包络、板厚、踢脚区、门厚/铰链间隙和背板模式一致；意图阶段不提前复制这些公式。

## 类别指导

- 地柜：当前模板将总高视为成品外包络，生成固定踢脚区；若还要求柜脚、独立底座、台面或装饰板，则停止并列为未支持决策。
- 吊柜：当前模板强制踢脚高度为 0；房间定位应提供 `origin_z_mm`，若为 0 则警告。墙体固定、荷载、基层和安装净空仍是制造/安装前必须确认的事项，但不进入 `CabinetLayout` 几何字段。

## 边界

- 不定义板件记录、封边/钻孔/五金、特征树、CAD/STEP、命令或产物。
- 房间定位只影响场景展示和布局校验；下游板件仍使用柜体局部 `CabinetLayout`，不得把房间世界坐标混入板件尺寸。
- 只将上述实时字段传递给板件规划；不得把未实现的组织要求描述成已完成布局。
