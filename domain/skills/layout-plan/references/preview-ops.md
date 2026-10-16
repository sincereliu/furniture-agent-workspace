# 布局预览维护

预览打不开、页面不刷新、或要重开项目时再读。

`furniture_create_project` 成功后在本机打开项目预览页；设置 `FURNITURE_PREVIEW_BROWSER=0` 时不自动打开。只有打开失败时才把 `preview.url` 告诉客户，平时展示 `project.current_view` 即可。Windows 上这个预览进程由 WMI 创建，调用方那条命令结束时不会把它一起杀掉。已经在跑的服务不会再拉一次。

每次 `furniture_revise_layout` 后，已打开的房间页会自行更新包络，不需重开。布局页订阅 `GET /api/project/{project_id}/layout/events`：`project.json` 或编辑租约变了才通知，版本变了才再读整份布局。客户关闭项目列表或房间页后，预览服务随后自行退出；房间页上的「退出」可立即停止。关机后要重看已有项目，在仓库根目录运行 `domain/skills/layout-plan/scripts/open_projects.py`，不要让客户去 CAD 阶段目录找。要直接打开最近创建、且当前能打开的那一个，运行同目录的 `open_last_project.py`，或双击仓库根目录的 `open_last_project.bat`。

项目名单由 `project_list.py` 提供，房间页由 `room_page.py` 组装 `templates/room_page.html` 与 `templates/room_page.js`。`open_projects.py` 拉起的本机进程是 `cad-generated/scripts/server.py`；单间场景的保存和编辑也在那里。`GET /api/project/{project_id}/preview` 只读 Project Store 的最新布局，不写 `stage_outputs`。房间外壳与项目预览都不是柜体 STEP。

选中一台落地柜或吊柜后，右侧「板件规划」打开 `/api/project/{project_id}/cabinets/{cabinet_id}/panels`。`manufacture: false` 不显示按钮，只写「这件只占位置」。宽、深、高还没回车时按钮停着，并写「先保存外形」。这一页不确认布局、不写板件。

**板件页有两种样子**：这台柜子的板件已经确认过，就画已确认冻结板件的结构——柜体一种浅木纹、门板白色纯色，可点选看尺寸位置、可关掉门板/背板、可拆开、可「透视门板」看内部；还没确认（或冻结板件里没有这台柜）就只画布局里已保存的外形盒子，页面上说明差什么。判据是 Revision 的 `confirmed_panel_sha256`：读 `store/<project-id>/panels/<sha256>.json`，与制造 / CAD 读同一份事实。结构页的 three.js 模块是 `/layout-view/cabinet_structure.js`（`furniture_layout/static/`）。

**这个模块的坐标约定**：柜体是 X 宽 / Y 深（+Y 是门这一面）/ Z 高，世界里 `world = (柜X, 柜Z, -柜Y)`——所以**门那一面在世界 -Z**，「正面」按钮必须站在 -Z；站反了人看到的现象是「门板没画出来」，其实镜头跑到背板后面去了（踩过）。相机距离按画幅比例和八个角现算（`fitDistanceFor`），不是半径乘常数，否则宽柜在窄窗口里会被切掉。地址栏可以指点初始视角：`?view=front|back|left|right|top|iso`，另有 `doors=0` / `back=0` / `wire=1` / `explode=0..100` / `only=wood,white` / `probe=1`（`probe` 把每块板当时的材质、几何和实际贴图旋转/重复次数贴到页面标题，给无头浏览器核对用）。这一页只读板件本身：不写 `stage_outputs`、不确认、不生成板件；**唯一能写的**是「保存并冻结」（见下）。

**顺纹方向的换算**在板件阶段（`cabinet_panel_page.py` 的 `_grain_uv()`）：木纹画在贴图的横向上，所以按「这个面的横向是不是顺纹轴」**逐个面**决定转不转——同一个「沿高」在侧板大面（`px`）上不转、在背板大面（`py`）上要转 90°，用一个全局值必然顾此失彼。这个模块只按投影给的 `grain.faces` 摆每块板六个面的旋转与重复次数，**不自己判断哪块板该朝哪**；换方向时也只按投影给的 `grain_axes` / `grain_cycle_mm` 重算，不另写一份规则。

模块里的 `panel.*` 字段名以投影为准（板件种类是 `panel_type`，装配是 `assembly`），别再读 payload 里没有的字段：`panel.group` 就是这么写出来的，门板 / 背板开关和透视一度全接在 `undefined` 上。

**改顺纹方向（这一页唯一能写的东西）**：`grain_axis` 是**板件自己的属性**（`x` 沿宽 / `y` 沿深 / `z` 沿高 / `none` 不限），默认值由板件类型在 `furniture_panel_planning/grain_rules.py` 给，随板件一起进冻结文件。页面上**在 3D 里点一块板只是选中**（不改任何东西），改纹理要在右侧详情里**点「顺纹方向」那一行**：那一下文字和画面同时变成另一种（**竖纹 ⇄ 横纹**，可反复点；竖纹 = 顺这块板大面的长边、横纹 = 顺短边，判据见 `grainPlaneAxes()`）。改过的先攒着，点一次**「保存并冻结」**才提交，走 `POST /api/project/{id}/cabinets/{id}/grain`：`revise_stage_output(panel_plan)` 追加新 Revision 后立刻重新确认，冻成新的 `<sha256>.json`。**代价是下游（制造 / BOM / CAD / 交付）全部作废**——顺纹变了它们本来就该重算，页面上那句提示就是这个意思。

**改数据不能和"点选"共用一个动作**：点板件只选中（点选是最常用的动作，顺手改数据太容易误伤——加过一版"点板件就翻纹理"，又拆了）。切换只能挂在详情那一行上，而且**只挂一处**：两处都能点的话，点一次板件再点一次那一行就是翻两次，看着像"点了没反应"。**高亮不许把贴图摘掉**：选中 / 悬停只加自发光 + 换描边颜色，`map` 一直挂着——原来是把 `map` 设成 `null` 整块涂纯色，于是点完看到的是纯蓝，现象成了"只有文字变了、纹理没变"。那块「待保存的改动 + 保存并冻结」**不是顺纹专用的**：以后别的板件属性也从这里改、一起冻结，所以按钮和标题都不许写死成"保存顺纹"；也**没有放弃按钮**——再点一次就切回去了。还有一个坑：切换要能**反复点**，所以 `applyGrainAxis()` **不许**改写 `panel.grain.axis`（那是"改之前"的依据，覆盖掉就变成"只能切一次"），当前方向一律由 `grainAxisOf()` 决定。

**木纹是现画的，不是贴图**（`paintGrain()`）。外观是**固定常量**（`GRAIN_TONE` / `GRAIN_LINES` / `GRAIN_WIDTH` …），页面上**没有**调节入口——预设、深浅、粗细那些只能看效果，对下单没用，加过一版又拆了。用**固定种子**（`GRAIN_SEED`）而不是 `Math.random()`，所以每次刷新画出的纹理完全一样，两次截图才对得上。改纹理方向（线的轴）之前先看 `_FACE_AXES` 的说明并在页面上量一遍：侧板与背板该是竖纹，顶底板 / 层板 / 踢脚板该是横纹。

名单读取 `store/<id>/project.json` 时检查可解析性、工程编号、修订、布局格式和结构。无法打开布局页的工程仍列在不可点击的折叠列表里并说明原因；预览路由也会拒绝。工程不会因创建时间久而自动过期，编辑租约到期不影响工程存档。
