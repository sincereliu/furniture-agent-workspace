# 布局预览维护

预览打不开、页面不刷新、或要重开项目时再读。

`furniture_create_project` 成功后在本机打开项目预览页；设置 `FURNITURE_PREVIEW_BROWSER=0` 时不自动打开。只有打开失败时才把 `preview.url` 告诉客户，平时展示 `project.current_view` 即可。Windows 上这个预览进程由 WMI 创建，调用方那条命令结束时不会把它一起杀掉。已经在跑的服务不会再拉一次。

每次 `furniture_revise_layout` 后，已打开的房间页会自行更新包络，不需重开。布局页订阅 `GET /api/project/{project_id}/layout/events`：`project.json` 或编辑租约变了才通知，版本变了才再读整份布局。客户关闭项目列表或房间页后，预览服务随后自行退出；房间页上的「退出」可立即停止。关机后要重看已有项目，在仓库根目录运行 `domain/skills/layout-plan/scripts/open_projects.py`，不要让客户去 CAD 阶段目录找。要直接打开最近创建、且当前能打开的那一个，运行同目录的 `open_last_project.py`，或双击仓库根目录的 `open_last_project.bat`。

项目名单由 `project_list.py` 提供，房间页由 `room_page.py` 组装 `templates/room_page.html` 与 `templates/room_page.js`。`open_projects.py` 拉起的本机进程是 `cad-generated/scripts/server.py`；单间场景的保存和编辑也在那里。`GET /api/project/{project_id}/preview` 只读 Project Store 的最新布局，不写 `stage_outputs`。房间外壳与项目预览都不是柜体 STEP。

选中一台落地柜或吊柜后，右侧「板件规划」打开 `/api/project/{project_id}/cabinets/{cabinet_id}/panels`。`manufacture: false` 不显示按钮，只写「这件只占位置」。宽、深、高还没回车时按钮停着，并写「先保存外形」。这一页不确认布局、不写板件。

名单读取 `store/<id>/project.json` 时检查可解析性、工程编号、修订、布局格式和结构。无法打开布局页的工程仍列在不可点击的折叠列表里并说明原因；预览路由也会拒绝。工程不会因创建时间久而自动过期，编辑租约到期不影响工程存档。
