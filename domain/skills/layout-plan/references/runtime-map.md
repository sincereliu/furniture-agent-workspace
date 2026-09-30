# 运行时映射（布局阶段）

核对实现或规划演进时再读。几何口径以 [空间布局规则](spatial-layout-rules.md) 为准；卧室/客厅清单只是 LLM 假设，见 [房间场景指南](room-scene-guide.md)。

各文件先看它干什么。最后一列「代码归类」是给边界审计用的，看功能看前两列。

## 谁给意图，谁换毫米

代码**不会**按「这是卧室」自动排床和衣柜。房间类型不是算法输入。

- 人 / LLM 给出每件的外形尺寸和摆法：靠哪面墙、从哪开始、要不要沿墙铺满，或自由坐标。
- 换成毫米坐标的是 `placement.py`：原点、转角、沿墙铺满的实宽、足迹、净距。
- 检查能不能站住的是 `placement_check.py`：越界、外形干涉、遮挡门窗洞口。失败整单拒绝，**不换墙重排**。要改位置，改提案或在房间页里拖，再走同一条算路。

## 算路

读意图 → 换成毫米坐标（`wall` / `free` / `fill`）→ 摆放检查 → 通过了再画房间的图。

`fill` 件等所有固定件摆完再算：先扣同高度上门窗、贴墙障碍、已摆家具，未给偏移取最长空段，给了则从该点铺到该空段终点。空段没有就失败。

三种摆法的公式见 [空间布局规则](spatial-layout-rules.md)。贴边接触不算干涉；外形尺寸发生正体积相交、越出房间、遮挡门窗洞口才拒绝。

## 全屋摆放和单间

两条路用同一套换算和摆放检查。

| 干什么 | 从哪进 | 过不了会怎样 | 存在哪 |
| --- | --- | --- | --- |
| 建一整套房子的摆放 | `layout_entry.plan_project_layout` / `ProjectLayout.from_source` | 越界、干涉或遮挡洞口就不建项目 | Project Store；确认后冻成给板件的盒子 |
| 建单独一间 | `layout_entry.plan_room_scene` | 同一套 `validation.admit_scene` | `scene_store` → `generated/room-scenes/`；这间不进六阶段 |

浏览器里的项目名单是 `project_list.py`，房间页是 `room_page.py`（模板在 `templates/room_page.html`）。开机后手动打开名单，运行本阶段的 `scripts/open_projects.py`。它拉起的本机进程仍是 `cad-generated/scripts/server.py`（单间的保存和编辑都在那里）。这个进程不进六阶段，也不是柜体 CAD。同一服务上的 `GET /api/project/{project_id}/preview` 只读 Project Store 里的最新摆放，不写 `stage_outputs`。柜体 STEP 仍走确认之后的 `furniture_run_next(..., generate_cad=True)`。

项目名单读取 `store/<id>/project.json` 时检查能否解析、工程编号是否匹配、有无修订、最新版布局格式是否受支持，以及布局结构是否有效。当前布局页无法打开的工程仍显示在不可点击的折叠列表里，并说明原因；预览路由也拒绝不可用工程。工程不会因创建时间久而自动过期；编辑租约的到期与工程存档无关。

下游板件只读已确认的 `LayoutUnit`（`furniture_category` 为 `floor_cabinet` / `wall_cabinet`，且该件不是 `manufacture: false`）。客户点名不制造的包络留在房间里，不是 `LayoutUnit`。`room_shell.py` 写的房间外壳 STEP 不是柜体模型。

板件实际只依赖 `LayoutUnit` 的五个字段：`id`、`furniture_category`、`width`、`depth`、`height`。这五个不变，板件与制造的内容就不变，可以跨 Revision 继承（见编排层 [修订继承设计](../../cad-generated/references/revision-inheritance-design.md)）。沿墙铺满那件的 `width` 由该墙空段算出，改房间就会改它，所以这种件永远算变了，必须重算。

确认时 `layout_figures.check_layout_figures` / `check_room_figures` 再核每个房间的图是不是由当前几何画出的。建项目前的 `validation.admit_scene` 不画 SVG。

## 各文件干什么

| 干什么 | 文件 | 代码归类 |
| --- | --- | --- |
| 房间、门窗、家具盒子的数据结构 | `scene.py` | schema |
| 把靠墙、自由摆、沿墙铺满换成毫米坐标 | `placement.py` | calculation |
| 检查盒子出不出房间、互相干涉不干涉、挡不挡门窗 | `placement_check.py` | calculation |
| 上面几项有一项不过，就不建项目。不核对配进去的那张 SVG | `validation.py` | validation |
| 一整套房子的摆放。确认后冻出给板件的盒子：宽、深、高和柜类。这里不画房间页，也不写房间外壳 | `project_layout.py` | schema |
| 给这套摆放配上每个房间的图，确认时核对图是不是刚算出来的 | `layout_figures.py` | calculation |
| 配进去的那张 SVG | `room_svg.py` | calculation |
| 配进去的那份只读页面。它存在项目里，不是浏览器里正在打开的那一页 | `stored_room_page.py` | calculation |
| 浏览器里打开的房间页。可拖、只读预览、分享都是这一页。Python 读 `templates/room_page.html` 填上当前房间。原点三轴、光标坐标、房间药丸、`?room=`、页眉牌子都在模板里。模板里的拖动检查必须与 `placement_check.py` 同步 | `room_page.py` | calculation |
| 做过的项目名单 | `project_list.py` | calculation |
| 把预览页打开，并准备这一页要读的数据 | `open_preview.py` | side_effect |
| 房间页上的三维盒子 | `static/layout_scene.js` | calculation |
| 房间的东、南、上怎么画到屏幕上 | `static/layout_frame.js` | calculation |
| 房间轴、家具尺寸线和标签锚点；全部用房间坐标计算 | `static/layout_annotations.js` | calculation |
| 记下移动、旋转或改尺寸，这一步先不算。全屋和单间共用这一套字段 | `scene_edit.py` | schema |
| 把这次改动算进某一间，算出一版还没确认的摆放。版本号和落盘不在这里 | `project_edit.py` | calculation |
| 三个入口：建全屋摆放（`plan_project_layout`）、建单间（`plan_room_scene`）、写房间外壳（`write_room_shell`） | `layout_entry.py` | structured_protocol |
| 单间的保存、编辑，以及要房间外壳 | `room_http.py` | structured_protocol |
| 单间只存客户原来写的那份，打开时再算 | `scene_store.py` | side_effect |
| 房间外壳的 STEP：地、墙、门窗洞。不是柜体模型 | `room_shell.py` | side_effect |

房间页上拖动只是本地先画，松手后后端再换算并检查。改 `placement_check.py` 必须同步改 `templates/room_page.html` 里的脚本。

预览几何与标签锚点统一使用房间坐标 `[x, y, z]`（宽、深、高，毫米）。进入 Three.js 时调用 `layout_frame.roomToThree()`，相机回读与拾取返回时调用 `threeToRoom()`；不在调用方手写换序。屏幕像素坐标与 Three.js 原生网格旋转仍由渲染层计算。固定轴和边线随场景内容构建，相机移动时只更新投影与墙面显示。

未落地与待议需求见 [backlog](backlog.md)。改坐标、摆放检查或房间页时不必读。
