---
name: layout-plan
description: 用于 layout_plan 阶段。当用户说「房间多大」「家具摆在哪」「靠哪面墙」「这面墙铺满」「门窗洞口在哪」「这件不做柜、只占位置」时触发。按房间整理各件外形尺寸和摆放，确认后把可执行柜体的宽、深、高交给板件。柜门、层板、抽屉、背板、踢脚、料厚不在本阶段。
---

# 家具布局规划

阶段：`layout_plan`

**这一阶段只回答一件事：各间房里，每件家具的外形尺寸放在哪。** 交出去的是一版还没确认的布局。确认之后，要做的柜只交出柜类和宽、深、高。

## 人要交什么

- 整理成非空的 `rooms[]`。只有一件家具也要有房间。每间要有 `id`、`width_mm`、`depth_mm`、`height_mm`；缺了先问，不编造。
- 家具写在 `items[]`：`id`、`category`、深度、高度、`placement`。宽度已经说死的，写这台的 `width`，不要改成铺满。`category` 只是给人看的种类。
- 要做成柜的写 `furniture_category: floor_cabinet|wall_cabinet`。`wall_cabinet` 是吊柜。靠墙摆放另写 `host_wall`。只有客户点名某件不做时才写 `manufacture: false`；该件仍参与摆放，确认后不进板件。
- 墙上的门窗写在 `openings[]`，`kind` 为 `door` 或 `window`。
- 摆法用靠墙（`host_wall`）、贴某一头（`against`）、铺满（`fill: true`）或自由摆。吊柜离地写 `origin_z_mm`。字段怎么填、怎么贴合，见 [空间布局规则](references/spatial-layout-rules.md)；写法例子见 [输入示例](references/input-examples.md)。
- 客户没点名家具清单时，先按 [房间场景指南](references/room-scene-guide.md) 列出待确认假设，认可后再调用工具。

## 一步一步做什么

1. **收齐房间和摆法。** 客户已经给出的房间尺寸、家具清单和摆法直接写入。缺房间的宽、深或高时先问，不编造。清单是按场景指南猜的、客户还没点名时，先把假设给客户看，认可后再调用工具。
2. **调用 `furniture_create_project(name, rooms)`。** 运行时换算坐标并检查越界、家具干涉和门窗遮挡。失败就说明冲突，改提案后重试，不自行换墙重排。
3. **展示 `project.current_view`，记下 `project.id`。** 预览页默认自动打开；只有打开失败才给 `preview.url`。
4. **客户认可后再确认。** `furniture_confirm_stage(project_id, stage="layout_plan")`，也可带 `room_id` 逐间确认。所有待审房间都确认后，布局检查点才成立。
5. **客户要改房间或家具。** 调用 `furniture_revise_layout(project_id, rooms)`，再展示新的 `current_view`。
6. **布局确认后，客户要做柜体内部。** 打开 [板件阶段](../panel-plan/SKILL.md)，用已确认的柜类和宽、深、高准备 `stage_input`，再调用 `furniture_run_next`。下一步是否确认或继续，以返回的 `required_tool` 为准，见 [交互工具面](../cad-generated/references/agent-tool-contract.md)。

## 本阶段不做什么

- 柜门、层板、抽屉、背板、踢脚、料厚归 [板件阶段](../panel-plan/SKILL.md)。房间门窗仍写在 `openings[]`。
- 材料、封边、五金、孔和 BOM 归制造阶段。
- 柜体模型归后面的 CAD 阶段。

## 按这句话打开

| 遇到 | 打开 |
| --- | --- |
| 客户没给家具清单 | [房间场景指南](references/room-scene-guide.md) |
| 核对字段、`against` 或 `manufacture: false` 的写法 | [输入示例](references/input-examples.md) |
| 靠墙、铺满、转角，或越界、干涉、遮挡洞口 | [空间布局规则](references/spatial-layout-rules.md) |
| 预览打不开、页面不刷新、重开已有项目 | [预览维护](references/preview-ops.md) |
| 改布局代码，或决定跑哪个测试 | [运行时映射](references/runtime-map.md) |
| 改可执行柜类 | [可执行柜类](references/intake/catalog.yaml) |

日常做布局只打开表里对上的那一行。
