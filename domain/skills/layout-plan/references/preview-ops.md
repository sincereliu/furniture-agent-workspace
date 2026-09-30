# 布局预览维护

`furniture_create_project` 成功后在本机打开项目预览页；设置 `FURNITURE_PREVIEW_BROWSER=0` 时不自动打开。只有打开失败时才把 `preview.url` 告诉客户，平时展示 `project.current_view` 即可。

每次 `furniture_revise_layout` 后，已打开的房间页会自行更新包络，不需重开。客户关闭项目列表或房间页后，预览服务随后自行退出；房间页上的「退出」可立即停止。关机后要重看已有项目，在仓库根目录运行 `domain/skills/layout-plan/scripts/open_projects.py`，不要让客户去 CAD 阶段目录找。

项目名单由 `project_list.py` 提供，房间页由 `room_page.py` 和 `templates/room_page.html` 提供。`open_projects.py` 拉起的本机进程是 `cad-generated/scripts/server.py`；单间场景的保存和编辑也在那里。`GET /api/project/{project_id}/preview` 只读 Project Store 的最新布局，不写 `stage_outputs`。房间外壳与项目预览都不是柜体 STEP。

名单读取 `store/<id>/project.json` 时检查可解析性、工程编号、修订、布局格式和结构。无法打开布局页的工程仍列在不可点击的折叠列表里并说明原因；预览路由也会拒绝。工程不会因创建时间久而自动过期，编辑租约到期不影响工程存档。
