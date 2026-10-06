---
name: layout-plan
description: 用于 layout_plan 阶段，也是家具流水线的入口。当用户要给家里做家具、描述房间和家具怎么摆、或给出柜体外形尺寸时触发。按房间组织各件外形尺寸；可执行柜体作为 CAD 单元交给板件阶段。不生成柜体板件或柜体 STEP。
---

# 家具布局规划

阶段：`layout_plan`

本阶段整理房间、家具包络和摆放，交付待确认的布局；柜门、层板、材料和柜体模型留给下游阶段。

## 输入

- 项目统一整理成非空的 `rooms[]`，只有一件家具也要提供所属房间。每间房必须有 `id`、`width_mm`、`depth_mm`、`height_mm`；缺尺寸就问，不编造。家具写在该房间的 `items[]`，墙上的门窗写在 `openings[]`（`kind: door|window`）。
- 每件家具给 `id`、`category`、深度、高度和 `placement`；固定宽度的件还要给 `width`。`category` 是给人看的种类，不决定是否制造。
- 要做成柜的件写 `furniture_category: floor_cabinet|wall_cabinet`。`wall_cabinet` 表示吊柜，不表示靠墙摆放。只有客户点名某件不需要制造时才写 `manufacture: false`；该件仍参与摆放，但不进入板件阶段。
- `placement.mode` 只有 `wall` 和 `free`。靠墙写 `host_wall`：同一面墙上的包络按顺序贴合，每台占最早放得下的那段空墙的起点；`fill: true` 占剩下最长的一段，宽度可省。自由摆写局部原点坐标和转角。沿墙偏移不在这一阶段。吊柜离地写 `placement.origin_z_mm`。坐标、点序和拒绝条件见[空间布局规则](references/spatial-layout-rules.md)。
- 客户已经说清某一台的宽度时，直接给这台的 `width`，不要铺满。
- 客户没点名家具清单时，按[房间场景指南](references/room-scene-guide.md)列出待确认假设，得到客户认可后再调用工具。

输入写法见[示例](references/input-examples.md)。

## 操作流程

1. 整理客户给出的尺寸、家具和摆法；缺房间尺寸先问，猜测的清单先请客户确认。
2. 调用 `furniture_create_project(name, rooms)`。运行时换算坐标并检查越界、家具干涉和门窗遮挡；失败时说明冲突，修改提案后重试，不自行换墙重排。
3. 成功后展示 `project.current_view`，记下 `project.id`，等待客户审看。预览页默认自动打开；只有打开失败才给 `preview.url`。预览服务的操作见[预览维护](references/preview-ops.md)。
4. 客户认可后调用 `furniture_confirm_stage(project_id, stage="layout_plan")`；也可带 `room_id` 逐间确认，所有待审房间都确认后布局检查点才成立。已确认且未标记 `manufacture: false` 的柜体包络成为下游只读单元。
5. 客户要改房间或家具，调用 `furniture_revise_layout(project_id, rooms)`，再展示新版 `current_view` 等待确认。
6. 布局确认后，客户要做柜体内部时才按[板件阶段](../panel-plan/SKILL.md)准备 `stage_input` 并调用 `furniture_run_next`。每次成功调用后按 `required_tool` / `allowed_tools` 停在当前检查点；工具参数见[交互工具面](../cad-generated/references/agent-tool-contract.md)。

## 按需阅读

- 改坐标、靠墙/自由摆、`fill` 或摆放检查：[空间布局规则](references/spatial-layout-rules.md)；定位实现文件与测试：[运行时映射](references/runtime-map.md)。
- 改输入示例：[输入示例](references/input-examples.md)；客户没给清单：[房间场景指南](references/room-scene-guide.md)。
- 排查房间页、预览服务或重开项目：[预览维护](references/preview-ops.md)。
- 改可执行柜类：[可执行柜类](references/intake/catalog.yaml)。未落地需求才读 [backlog](references/backlog.md)。
