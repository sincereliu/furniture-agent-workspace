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
5. 客户确认后再 `generate_room_cad`，画出房屋和家具外包络。不要走 `furniture_run_next(..., generate_cad=True)`。
6. 某件要做柜体结构时，另开 `design-intent` 六阶段。房间场景不自动开工柜体项目。

## 边界

- 输入只有房间与多件外包络摆放。`category` 是展示名，不进 `DesignIntent`。
- 门数、层板、抽屉、封边、五金、柜体 STEP 不属于本技能。
- 结果不写入主流程 `STAGE_SEQUENCE`、`approved_stages` 或家具 CAD 交付清单。
- 修改摆放时重新运行本技能，不调用 `revise_stage_output()`。
