# 设计意图采集规则

回答“要制作什么家具？”；位于布局、板件、制造、特征树和执行之前。

## 捕获内容

- `furniture_type` 类别；`purpose` 用途/优先级。扁平 CLI/API 请求才使用 `type`，进入 `DesignIntent` 后统一为 `furniture_type`。
- `overall_size`：成品外包络 `width_mm/depth_mm/height_mm`，未知为 `null`。
- `layout`：门、隔间、层板、抽屉、挂衣区等用户层组织。
- `appearance` 风格/饰面；`structure` 高层结构偏好。
- `constraints`：房间、人体工学、安全、安装、制造和材料要求。
- `assumptions` 暂定默认；`unresolved` 待确认决策。假设写在受影响字段旁。

## 尺寸约定

- `width_mm/depth_mm/height_mm` 分别为 X 左→右、Y 后→前、Z 向上的跨度；除非另标净空、柜体或洞口，均指成品外包络。
- 三个未标注尺寸暂按 `W×D×H`，显式记录；语境冲突时修正。

## 背板安装意图

- `back_mount`：`groove` 四边入槽、`insert` 内嵌、`cover` 外盖、`auto`。`auto` 在背板薄于柜体板时取 `groove`，否则取 `insert`；确认时展示结果。
- `groove_depth/groove_clearance/back_rail_height` 仅对有效 `groove` 生效，其他模式不受其阻塞。
- 只确认偏好/参数，不计算背板尺寸、背拉条、连接件或孔位。

## 边界

- 草稿可保留 `null`，但确认前 `width_mm/depth_mm/height_mm` 必须全部为正数，且 `unresolved` 必须为空。
- 当前固定柜体运行时只执行 `layout.shelf_count/n_doors/toe_kick_height`；抽屉、隔板分区、滑门、开放格等要求须保留为未决项，不得在确认时静默丢弃。
- 类别无匹配时只输出 fallback 草稿；当前运行时不会确认该类别或进入布局。
- 在板件前停止；不得添加板件/坐标/裁切尺寸/五金/制造策略/特征树/CAD 调用或输出路径。
- 对交互式设计讨论，除非用户要求规划或端到端生成，否则在意图阶段停止。

## 类别特定决策

- 地柜：柜体/背板、踢脚或底座、门、层板/隔板、安装和厚度。
- 吊柜：柜体/背板、门、层板/隔板、墙体固定、基层、净空和厚度；无踢脚。
- 其他：只捕获通用意图，由流水线判断可执行性。
