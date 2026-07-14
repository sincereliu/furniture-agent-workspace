# 更新日志

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

## 20260710.1

Skill：告诉 AI 什么时候做什么、读取什么规则
Schema：保存稳定的数据契约
Orchestrator：控制执行顺序和状态
Domain packages：负责尺寸、板件、BOM、五金
CAD Bridge：负责调用外部 CAD

两个脚本文件夹的区别
generated/	STEP、GLB、BOM、Feature Tree、订单与生产数据	默认保留
temp/	临时 CAD Python、调试脚本、迁移脚本、中间文件	任务结束就删除