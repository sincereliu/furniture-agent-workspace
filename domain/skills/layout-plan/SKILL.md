---
name: layout-plan
description: 用于 layout_plan 阶段，也是家具流水线的入口。当用户要给家里做家具、描述房间和家具怎么摆、或给出柜体外形尺寸时触发。按房间组织各件外形尺寸；可执行柜体作为 CAD 单元交给板件阶段。不生成柜体板件或柜体 STEP。
---

# 家具布局规划

阶段：`layout_plan`

**这一阶段只回答三件事：家里有哪些房间、每件家具的盒子摆在哪、哪些盒子以后要做成柜。** 交出去的是一版还没确认的全屋摆放。柜门、层板、材料、柜体模型都不在这里做。

## 人要交什么

客户的话整理成 `rooms[]`。每间房要有长、宽、高，单位毫米。缺了就问，不要编。

每件家具是一个盒子，写在这间房的 `items[]` 里：

- `category`：给人看的种类，例如 `bed`、`sofa`、`wardrobe`、`bookcase`。种类不决定这件做不做。
- `furniture_category`：要做成柜的件都写。允许的值只有 `floor_cabinet`（落地柜）和 `wall_cabinet`（吊在墙上的柜）。靠墙摆仍然不写 `wall_cabinet`。
- `manufacture`：只有客户点名某一件不需要制造时写 `false`。这件的包络仍留下，用来和要制造的家具一起摆。没写就是要制造。不制造只来自客户对这一件的点名，不来自种类。
- 这间房墙上的门和窗写在 `openings[]`，`kind` 为 `door` 或 `window`。摆盒子时要躲开它们。

每件怎么摆，写在它的 `placement` 里，三选一。换算公式在 [空间布局规则](references/spatial-layout-rules.md)：

- 靠墙：`mode: wall`，写背面贴哪面墙（`host_wall`）、沿墙从哪开始（`offset_mm`）。
- 自由：`mode: free`，直接写房间里的坐标。
- 沿墙铺满：靠墙再加 `fill: true`。可以不写 `width`，宽度由这面墙剩下的空段算出来。

吊柜离地写 `placement.origin_z_mm`。客户没点名有哪些家具时，按 [房间场景指南](references/room-scene-guide.md) 列出假设，等客户点头再调用工具。

最小例子：一间卧室，一个要做的书柜靠北墙，一个要做的衣柜沿西墙铺满。

```yaml
rooms:
  - id: bedroom
    width_mm: 3600
    depth_mm: 4200
    height_mm: 2800
    openings:
      - id: door-1
        kind: door
        wall: south
        offset_mm: 400
        width_mm: 900
        height_mm: 2100
    items:
      - id: bookcase
        category: bookcase
        furniture_category: floor_cabinet
        width: 1200
        depth: 400
        height: 2100
        placement:
          mode: wall
          host_wall: north
          offset_mm: 900
      - id: wardrobe
        category: wardrobe
        furniture_category: floor_cabinet
        depth: 600
        height: 2400
        placement:
          mode: wall
          host_wall: west
          fill: true
```

客户说房间里已经有一件、不用做时，给那一件加上 `manufacture: false`。下面这只书柜仍占位置，确认后不进板件：

```yaml
- id: bookcase
  category: bookcase
  furniture_category: floor_cabinet
  manufacture: false
  width: 900
  depth: 350
  height: 2100
  placement:
    mode: wall
    host_wall: east
    offset_mm: 200
```

只有一件柜、还没有房间时，可以不写 `rooms[]`，只给 `furniture_category`、宽深高，以及可选的离地 `origin_z_mm`。这是开工捷径。有房间就用上面的 `rooms[]`。

## 一步一步做什么

按编号往下做。第 4 步是第 3 步失败时的回头路。第 7 步是确认之后客户要改房间。

1. **收齐房间尺寸。** 长、宽、高缺一个就停下来问。不要用常见户型填上。
2. **收成上面的 `rooms[]`。** 这一步只整理客户的话，还不调用工具。清单是猜的，就先把假设给客户看。
3. **调用 `furniture_create_project`。** 传入项目 `name` 和 `rooms`。代码先把摆法换成毫米坐标，再检查三件事：盒子出不出房间、盒子互相干涉不干涉、遮不遮挡这间房的门窗洞口。三件都过了才建出项目。
4. **失败就改了再调。** 把返回的冲突告诉客户，改那一件的位置或尺寸，再调用一次。代码不会自己换一面墙重排。
5. **成功就停。** 把 `project.current_view`（各房间的图）给客户看，记下 `project.id`。`furniture_create_project` 会在本机打开预览页，不要再把链接交给客户去点。打开失败时才告诉客户 `preview.url`。之后每次 `furniture_revise_layout`，这一页自己换成新的包络，不要再开一次。客户要停掉后台时，让他们点预览页上的「退出」，不要只关标签页。不要接着做柜体内部。
6. **客户认这版摆放，再确认。** 调用 `furniture_confirm_stage(project_id, stage="layout_plan")`。确认后，客户没有点名不制造、并且带 `furniture_category` 的柜子冻成下游只读的盒子：宽、深、高，加上这个柜类。`manufacture: false` 的包络留在房间里，不在这批盒子中。之后做板件只读这批盒子。
7. **客户要改房间或盒子。** 调用 `furniture_revise_layout(project_id, rooms)`，传入改过的 `rooms`。这是另起一版布局。
8. **客户要做某一件柜的内部。** 第 6 步已经确认之后，调用 `furniture_run_next(project_id, stage_input=...)` 进入板件阶段。`stage_input` 按板件阶段准备。客户点名不制造的包络留在房间图里。工具参数见 [交互工具面](../cad-generated/references/agent-tool-contract.md)。

## 本阶段不做什么

- 柜门数量、层板、抽屉、板厚、背板、踢脚：板件阶段。
- 材料、五金：制造阶段。
- 柜体模型：布局确认之后，用 `furniture_run_next(..., generate_cad=True)`。本阶段画出的房间图不是柜体模型。

## 参考导航

- 靠墙、自由摆、沿墙铺满怎么换算，以及什么情况会拒绝：[空间布局规则](references/spatial-layout-rules.md)
- 全屋项目和独立房间两条出口、各文件做什么：[运行时映射](references/runtime-map.md)
- 客户没给清单时的待确认假设：[房间场景指南](references/room-scene-guide.md)
- 可执行柜类：[可执行柜类](references/intake/catalog.yaml)
- 未落地需求与待议项（门洞编辑、view/editor 互跳、代码是否共用等）：[backlog](references/backlog.md)，日常实现不必读
