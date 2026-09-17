---
name: layout-plan
description: 用于 layout_plan 阶段，也是家具流水线的入口。当用户要给家里做家具、描述房间和家具怎么摆、或给出柜体外包络时触发。按房间组织家具包络；可执行柜体作为 CAD 单元交给板件阶段。不生成柜体板件或柜体 STEP。
---

# 家具布局规划

阶段：`layout_plan`

**本阶段只回答：客户家里有哪些房间、家具外包络怎么摆、哪些件是要做的柜。** 产物是待确认的多房间布局；板件、材料、制造不在此阶段。

## 工作流

1. 项目是客户全屋家具项目。缺房间长宽高则追问，不要编造实测尺寸。
2. 把口述整理成 `rooms[]`，每间房含 `items[]`。柜体写规范 `furniture_category`（`floor_cabinet` / `wall_cabinet`）；床、沙发等只给展示 `category`，不进板件。客户没给清单时按 [房间场景指南](references/room-scene-guide.md) 提出可见假设，等确认。
3. 调用 `plan_project_layout(rooms)`。几何、碰撞和 `wall + fill` 净长由代码计算；规则见 [空间布局规则](references/spatial-layout-rules.md)。可执行柜类目录见 [家具目录](references/intake/catalog.yaml)。
4. 失败则展示冲突并改提案后重跑。成功则展示房间图并暂停。
5. `confirm_stage(layout_plan)` 把布局冻成 CAD 单元（盒子几何 + 柜类属性）。之后板件只读这份冻结布局。改房间或改外包络用 `revise_layout()`，不要回头改已冻结布局。
6. 某件可执行柜要做结构时，确认布局后 `run_next(panel_plan)`。非柜包络留在房间里占位。

可编辑视图与单次编辑 op 见运行时契约；松手才落盘，碰撞失败整单拒绝。

## 本阶段不做什么

- 门、层板、抽屉、板厚、背板、踢脚 → 板件阶段
- 不要从「靠墙」推断 `wall_cabinet`；靠墙是摆放，上墙才是吊柜
- 制造（材料/饰面/五金…）→ 制造阶段
- 柜体 STEP 走 `furniture_run_next(..., generate_cad=True)`；房间包络 CAD 不是柜体 CAD

## 边界

- 输入是多房间与多件外包络。`category` 是展示名；`furniture_category` 仅可执行柜类，确认后进入 CAD 单元属性。
- 吊柜离地高度就是摆放的 `origin_z_mm`；贴顶由离地+柜高贴房间净高派生，不再单存 `hanging_mode`。
- 结果写入 `STAGE_SEQUENCE` 的 `layout_plan`，冻结后板件只读 CAD 单元。
- 修改布局走 `revise_layout()`，不调用 `revise_stage_output()`。
