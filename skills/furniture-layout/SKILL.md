---
name: furniture-layout
description: 用于 layout_planned 阶段。当用户说"几扇门""几层层板""放在房间哪个位置""靠墙还是居中"时触发。在已确认成品外包络内规划客户可见的功能数量，并确定家具在房间中的位置和包络预览，不做结构设计。
---

# 家具布局规划

阶段：`layout_planned`

## 工作流

1. 要求当前 Revision 的 `design_intent` 已确认，只读取类别和成品外包络。
2. 按 [空间布局规则](references/spatial-layout-rules.md) 生成 `CabinetLayout`：保留外包络，并确定当前模板可执行的 `shelf_count/door_count`。
3. 解析房间、门窗、障碍物及沿墙/自由摆放位置；缺失时使用可见标注的默认卧室与沿北墙居中位置。
4. 生成房间坐标、家具占地、六向净距、静态 SVG 和自包含互动 Viewer；校验越界、门窗遮挡和障碍物碰撞。
5. 展示 `stage_outputs.layout_planned` 后暂停。客户可修改功能数量和房间定位；本阶段不生成板厚、背板、踢脚、内部净空或板件。

## 边界

- `CabinetLayout` 只含 `furniture_type/width/depth/height/shelf_count/door_count`；数量不等于完整分区、开口或开启策略。
- 当前运行时尚不表达抽屉、隔板分区、开放格、滑门、挂衣区或设备区；这些输入应在本阶段失败，不得退回意图阶段或静默忽略。
- 局部原点为成品外包络左后下落地角；房间坐标通过 `room_placement.placement` 关联。
- 修改布局用 `revise_stage_output()`，使本阶段及下游失效。
- 精确柜体结构、最终内部净空、背板和踢脚归 `panels_planned`；不输出制造或 CAD 信息。
