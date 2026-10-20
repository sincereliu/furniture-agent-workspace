# 网页展示边界

本模块位于 `domain/modules/web/`。下面说的是浏览器里看见的那几页。

## 本模块拥有

| 干什么 | 文件 |
| --- | --- |
| 房间页、草稿页、只读预览和分享页的 HTML | `furniture_web/room_page.py`，`templates/room_page.html`，`templates/room_page.js` |
| 页面插槽。AI 助手往这里填样式和脚本，本模块不内置助手 | `room_page.PageExtension` |
| 做过的项目名单 | `furniture_web/project_list.py`，`templates/project_list.html` |
| 一台柜子的板件页 HTML | `furniture_web/panel_page.py` |
| 房间和柜子的三维画面 | `furniture_web/static/`，地址仍是 `/layout-view/` |
| 把上面的脚本挂上预览进程 | `furniture_web/integration.py` |

画面脚本先从这个目录取。`layout_solver.js` 和 `layout_drag.js` 不在这里，挂载时再去布局阶段找，所以页面里的地址不用改。

## 留在原处

| 干什么 | 留在 |
| --- | --- |
| 房间页要画的字典 | `furniture_layout.room_page.room_page_payload` |
| 干涉、越界、挡门窗的前端求解 | `furniture_layout/static/layout_solver.js`，与 `placement_check.py` 一起改 |
| 屏幕到毫米的拖动，以及贴回墙面 | `furniture_layout/static/layout_drag.js` |
| 确认时核对的房间 SVG | `furniture_layout/room_svg.py`，`layout_figures.py` |
| 板件页要画的结构、顺纹和贴图摆法 | `furniture_panel_planning.cabinet_panel_page.panel_structure_view` |
| 保存、撤销、编辑租约、进程退出 | `cad-generated/scripts/server.py` 和工作流 |

确认时，布局阶段调用本模块的 `render_viewer`，核对只读页是不是当前几何画出的。单间草稿的 HTML 也由 `room_http` 调用 `render_draft_page`。这两处是布局阶段对网页模块的依赖。网页模块不导入工作流，不写项目。

改摆放规则时改布局阶段的求解脚本。改门窗颜色、相机、微缩场景或板件页样子时改本模块。
