# 布局预览维护

预览打不开、页面不刷新、或要重开项目时再读。

`furniture_create_project` 成功后在本机打开项目预览页；设置 `FURNITURE_PREVIEW_BROWSER=0` 时不自动打开。只有打开失败时才把 `preview.url` 告诉客户，平时展示 `project.current_view` 即可。Windows 上这个预览进程由 WMI 创建，调用方那条命令结束时不会把它一起杀掉。已经在跑的服务不会再拉一次。

每次 `furniture_revise_layout` 后，已打开的房间页会自行更新包络，不需重开。布局页订阅 `GET /api/project/{project_id}/layout/events`：`project.json` 或编辑租约变了才通知，版本变了才再读整份布局。客户关闭项目列表或房间页后，预览服务随后自行退出；房间页上的「退出」可立即停止。关机后要重看已有项目，在仓库根目录运行 `domain/skills/layout-plan/scripts/open_projects.py`，不要让客户去 CAD 阶段目录找。要直接打开最近创建、且当前能打开的那一个，运行同目录的 `open_last_project.py`，或双击仓库根目录的 `open_last_project.bat`。

项目名单由 `project_list.py` 提供，房间页由 `room_page.py` 组装 `templates/room_page.html` 与 `templates/room_page.js`。`open_projects.py` 拉起的本机进程是 `cad-generated/scripts/server.py`；单间场景的保存和编辑也在那里。`GET /api/project/{project_id}/preview` 只读 Project Store 的最新布局，不写 `stage_outputs`。房间外壳与项目预览都不是柜体 STEP。

选中一台落地柜或吊柜后，右侧「板件规划」打开 `/api/project/{project_id}/cabinets/{cabinet_id}/panels`。`manufacture: false` 不显示按钮，只写「这件只占位置」。宽、深、高还没回车时按钮停着，并写「先保存外形」。这一页不确认布局、不写板件。

**板件页有两种样子**：这台柜子的板件已经确认过，就画已确认冻结板件的结构——柜体一种浅木纹、门板白色纯色，可点选看尺寸位置、可关掉门板/背板、可拆开、可「透视门板」看内部；还没确认（或冻结板件里没有这台柜）就只画布局里已保存的外形盒子，页面上说明差什么。判据是 Revision 的 `confirmed_panel_sha256`：读 `store/<project-id>/panels/<sha256>.json`，与制造 / CAD 读同一份事实。结构页的 three.js 模块是 `/layout-view/cabinet_structure.js`（`furniture_layout/static/`）。

**这个模块的坐标约定**：柜体是 X 宽 / Y 深（+Y 是门这一面）/ Z 高，世界里 `world = (柜X, 柜Z, -柜Y)`——所以**门那一面在世界 -Z**，「正面」按钮必须站在 -Z；站反了人看到的现象是「门板没画出来」，其实镜头跑到背板后面去了（踩过）。相机距离按画幅比例和八个角现算（`fitDistanceFor`），不是半径乘常数，否则宽柜在窄窗口里会被切掉。地址栏可以指点初始视角：`?view=front|back|left|right|top|iso`，另有 `doors=0` / `back=0` / `wire=1` / `explode=0..100` / `only=wood,white` / `probe=1`（`probe` 把每块板当时的材质与几何贴到页面标题，给无头浏览器核对用）。这一页同样只读：不写 `stage_outputs`、不确认、不生成板件。

名单读取 `store/<id>/project.json` 时检查可解析性、工程编号、修订、布局格式和结构。无法打开布局页的工程仍列在不可点击的折叠列表里并说明原因；预览路由也会拒绝。工程不会因创建时间久而自动过期，编辑租约到期不影响工程存档。
