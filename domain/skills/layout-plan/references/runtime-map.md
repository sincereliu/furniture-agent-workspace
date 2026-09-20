# 运行时映射（布局阶段）

核对实现或规划演进时再读。几何口径以 [空间布局规则](spatial-layout-rules.md) 为准；卧室/客厅清单只是 LLM 假设，见 [房间场景指南](room-scene-guide.md)。

## 谁给意图，谁换毫米

代码**不会**按「这是卧室」自动排床和衣柜。房间类型不是算法输入。

- 人 / LLM 给出每件的外包络和摆法意图：靠哪面墙、从哪开始、要不要沿墙铺满，或自由坐标。
- `placement.py` 把这句话换成房间毫米（原点、转角、fill 实宽、足迹、净距）。
- `collision.py` 只回答能不能站住。失败整单拒绝，**不换墙重排**。要改位置，改提案或在编辑器里拖，再走同一条算路。

## 算路

读意图 → 换毫米（`wall` / `free` / `fill`）→ 碰撞准入 → 通过了再画预览。

`fill` 件等所有固定件摆完再算：先扣同高度上门窗、贴墙障碍、已摆家具，未给偏移取最长空段，给了则从该点铺到该空段终点。空段没有就失败。

三种摆法的公式见 [空间布局规则](spatial-layout-rules.md)。贴边接触不算撞；正体积相交、出房间、挡门窗才拒绝。

## 两个出口，同一内核

| 表面 | 入口 | 规划时准入 | 持久化 |
| --- | --- | --- | --- |
| 全屋 `layout_plan` | `pipeline.plan_project_layout` / `ProjectLayout.from_source` | 越界或碰撞则不创建项目 | Project Store；确认后冻成 CAD 单元 |
| 独立房间场景 | `pipeline.plan_room_scene` | 同一套 `admit_scene` | `scene_store` → `generated/room-scenes/`；**不是**阶段检查点 |

独立房间 HTTP（`cad-generated/scripts/server.py`）只服务场景编辑与房间包络 CAD，不进入 `STAGE_SEQUENCE`。柜体 STEP 仍走确认布局后的 `furniture_run_next(..., generate_cad=True)`。

下游板件只读已确认的 `LayoutUnit`（`furniture_category` 为 `floor_cabinet` / `wall_cabinet`）。房间 STEP 不是柜体 CAD。

冻结/确认时 `validate_project_layout` / `validate_room_scene` 再核 preview/viewer 是否由当前几何重建。规划准入不画 SVG。

## 模块

| 模块 | 职责 | 边界理由 |
| --- | --- | --- |
| `pipeline.py` | `plan_project_layout`、`plan_room_scene`、`generate_room_cad` | structured_protocol |
| `project_layout.py` | 多房间检查点、`LayoutUnit`、工作室单柜捷径 | schema |
| `scene.py` | 房间/件的 schema 与解析 | schema |
| `placement.py` | wall / free / fill 换成毫米 | calculation |
| `collision.py` | 越界、障碍、门窗、互撞 | calculation |
| `validation.py` | `admit_scene`（规划）；dict 上再核预览（冻结） | validation |
| `preview.py` / `viewer.py` | SVG 与只读轨道视图 | calculation |
| `editor.py` | 可编辑 HTML；JS 碰撞必须与 `collision.py` 同步 | calculation |
| `scene_edit.py` | 源上的一次原子 op，本身不算几何 | schema |
| `scene_store.py` | 独立场景只存源，读取时重算 | side_effect |
| `cad.py` | 房间包络树与房间 STEP，不是 `furniture_cad` | side_effect |

编辑器拖动是服务端规则的本地预览，松手后后端再 place + 准入。改 `collision.py` 必须同步改 `editor.py` 里的 JS。
