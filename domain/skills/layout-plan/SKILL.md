---
name: layout-plan
description: 独立的功能房间多件包络布局。当用户要设计卧室/客厅等房间、说出家具怎么摆、按房间尺寸布家具、或画出房屋与家具包络时触发。不属于家具生成串联阶段，也不生成柜体板件或柜体 STEP。
---

# 家具布局规划

类型：独立按需步骤

## 工作流

1. 用户要设计功能房间、摆家具或出房间图时运行。房间长宽高不足则追问；不要编造实测尺寸。
2. 把口述整理成 `room + items[]`。客户没给家具清单或尺寸时，按 [房间场景指南](references/room-scene-guide.md) 提出可见假设，等确认。
3. 调用 `plan_room_scene(room, items)`。几何、碰撞和 `wall + fill` 净长由代码计算；规则见 [空间布局规则](references/spatial-layout-rules.md)。
4. 失败则展示冲突并改提案后重跑。成功则展示 SVG/Viewer 并暂停。
5. 场景可保存为「源」并逐次编辑：`POST /api/room-scene/save` 保存（房间 + 多件包络及其摆放请求），`GET /api/room-scene/{scene_id}` 读取重算，`POST /api/room-scene/{scene_id}/edit` 应用一次编辑。只存源，不存派生结果（摆放坐标、footprint、净距、预览都在读取时重算）；存储独立于主流程，不写 `stage_outputs`。
6. 编辑是单 op、原子：`move`（按当前 `mode` 二选一——`wall` 用 `host_wall`/`offset_mm`，`free` 用 `origin_x_mm`/`origin_y_mm`，混给即拒、换模式要显式给 `mode`）、`rotate`、`resize`（`width`/`depth`/`height` 任意子集）。重算与校验通过才落盘，失败整体拒绝。`rotate` 只对 `free` 有定义——`wall` 的旋转由 `host_wall` 派生，要转就在同一个 op 里带 `mode: "free"` 和绕中心算出的自由原点。
7. 可编辑视图 `GET /api/room-scene/{scene_id}/editor`：点包络任意位置选中；拖动改位置，靠墙件沿墙滑动、拖进房间就转成自由摆放，自由件平面移动；选中后拖家具上方的橙色圆点旋转（默认吸附 15°，Shift 精细到 1°）。拖动与旋转都限制在房间内，拖动期间只做本地预览，松手才发一个 op，拒绝时显示原因并回退到服务端状态。空白处拖拽仍转视角。
8. 客户确认后再 `generate_room_cad`，画出房屋和家具外包络。不要走 `furniture_run_next(..., generate_cad=True)`。
9. 某件要做柜体结构时，另开 `design-intent` 六阶段。房间场景不自动开工柜体项目。

## 边界

- 输入只有房间与多件外包络摆放。`category` 是展示名，不进 `DesignIntent`。
- 门数、层板、抽屉、封边、五金、柜体 STEP 不属于本技能。
- 结果不写入主流程 `STAGE_SEQUENCE`、`approved_stages` 或家具 CAD 交付清单。
- 修改摆放时重新运行本技能，不调用 `revise_stage_output()`。
