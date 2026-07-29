# 制造规则

回答“应如何制造？”；位于板件后，只负责材料、工艺和 BOM 策略。

## 需确定的策略

- 材料：类别、等级、厚度、纹理、可见面、饰面。
- 封边：边、厚度及余量状态；连接：螺钉、木榫、偏心件、槽/企口、胶合等。
- 五金：铰链、滑轨、拉手、层板托、固定、防倾倒及荷载。
- 公差/净空：门缝、安装/设备缝隙、地墙不平和安全余量。
- BOM：整份方案记录 `readiness`；`preliminary` 为软件暂定，`accepted` 表示用户/设计方接受方案但仍需工艺核对，`factory_ready` 只在工厂明确确认后使用。

## 三合一打孔规则

- 竖板（侧板/隔板）预埋螺母在高度方向按系统 32 排钻分布（首/末孔 64mm，间距≤512mm），深度方向前后双排（`[first_hole_mm, depth - last_hole_mm]`）。
- 横板（顶板/底板/固定层板）连接杆在深度方向同样前后双排；偏心轮深度方向双排用 `center_offset_from_edge`（默认 33.5mm）。
- 所有孔位由 `Connector.generate_holes()` 生成 `HoleSpec`，标记 `is_face_hole=True`（板面钻孔）或 `False`（板边钻孔）。

## 铰链打孔规则

- 铰链数量按门板高度分 5 档（≤480→2, ≤980→2, ≤1500→3, ≤2100→4, ≤2750→5）。
- 铰链杯孔 Y1 = `edge_offset_mm + cup_diameter/2`，为杯孔中心到门边的距离（国产全盖 5+17.5=22.5mm）。
- 杯孔从门板内侧钻入，方向 = `panel.inner_face`。

## 背板槽加工契约

- 入槽背板为左右侧板、顶/底板生成 4 条独立 `cut_box`；槽深 `groove_depth`，槽宽 `back_thickness + groove_clearance`。
- 每条含稳定 ID、目标、全局最小角点、正数尺寸和说明，且完全位于目标包络；本阶段不调用 CAD API。

## 背板安装制造契约

| 模式 | 背板封边 | 连接与孔位 | 五金 BOM |
|------|----------|------------|----------|
| `groove` | 不封边 | 四边槽；有背拉条时，左右侧板通孔与拉条端部预孔必须成对 | 背拉条端部沉头木螺钉 |
| `insert` | 四边同色 | 背板四边布置三合一；每个连接点必须同时有背板偏心轮孔、连接杆通道和柜体预埋螺母孔 | 内嵌背板专用三合一套件 |
| `cover` | 四边同色 | 沿左右侧板、顶板、底板周边布置；每颗螺钉必须同时有背板通孔和柜体预孔 | 外盖背板沉头木螺钉 |

- 板件记录保留有效 `back_mount`，不得由厚度/备注反推。
- 成对孔由 `Connector.generate_holes_for_panels()` 基于完整装配生成，不伪装成单板规则；背拉条四边封边。
- `hardware_catalog.yaml` 的外盖 `4×30mm`、背拉条 `4×40mm` 螺钉及 `hardware_rules.yaml` 孔距/预孔均为软件暂定值，不代表工厂批准；因此自动规划始终从 `readiness=preliminary` 开始。
- 五金数量等于主连接孔数量；同一连接的配合孔数量一致。

## 六面钻 XML 导出

- `export_six_side_drill.py` 从 `drilled-holes.json` 反推板件和孔位，生成 `KDTPanelFormat` XML。
- 机床坐标 X=PanelLength, Y=PanelWidth, Z=PanelThickness。
- TypeNo 由 `HoleSpec.is_face_hole` 决定，不再从世界坐标推导。
- 板件轮廓 `PanelOutline` 按逆时针列出顶点：`(0, PanelWidth) → (0, 0) → (PanelLength, 0) → (PanelLength, PanelWidth)` 加闭合点。
- `devices/six_side_drill_guigui.yaml` 按面板类型配置 `sixd_x_from_box`/`sixd_y_from_box` 和孔位坐标映射键。

## 边界

- 不创建/修改板件、布局、特征树或 CAD/STEP，不定义命令和产物路径。
