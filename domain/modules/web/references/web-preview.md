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
| 浏览器布局写入队列、版本和文档响应同步 | `static/layout_persistence.js` |
| 把上面的脚本挂上预览进程 | `furniture_web/integration.py` |

画面脚本先从这个目录取。`layout_solver.js` 和 `layout_drag.js` 不在这里，挂载时再去布局阶段找，所以页面里的地址不用改。

沙发、椅子、茶几和书桌采用整体粗外框、轻内部线的卡通描边。`cartoon_outline.js` 将家具部件投成整体蒙版，在可见整体外侧扩出约 3 CSS 像素的轮廓；墙与其他实体参与遮挡，半透明墙衰减轮廓。内部结构线沿真实棱边描绘，透明度 0.45，沿视线拉近 1 mm；部件不套实体膨胀壳，避免交接处露出错位黑边。选中和碰撞沿用对应轮廓颜色。几何对齐、旋转、蒙版、图层、点选和颜色检查运行 `node domain/modules/web/furniture_web/static/shaped_item_ink_check.mjs`；深度精度检查运行 `node domain/modules/web/furniture_web/static/ink_depth_check.mjs`。

房间墙体淡出时，`opening_markers.js` 保留对应门窗的无填充虚线框：门有地面底边，窗保留窗台高度。轮廓按深度参与遮挡且不写深度、不投影；悬停显示门窗 ID、宽高和窗台高度。`layout_scene.js` 随墙体透明度切换实体与轮廓，提示由 `layout_overlay.js` 显示。几何、淡出和悬停遮挡检查运行 `node domain/modules/web/furniture_web/static/opening_markers_check.mjs`。

`layout_persistence.js` 是浏览器布局文档的同步入口，私有状态不由页面模板直接修改。它按松手顺序串行保存，提交时复制操作坐标、发送时带上上一笔确认的版本和当前租约；助手假设的确认/划掉也走这条队列。拖动、转动视角或保存期间暂存文档，空闲后才交给页面安装；写入和较新的读取使旧响应失效。通知到来时只按需重读；写入拒绝或网络异常后重读权威结果，再释放队列。保存中切换房间会被页面挡住，防止用旧房间快照覆盖本地操作。同墙拖动比较完整位置，不能只凭墙名和高度跳过保存。

模板只负责把交互整理成规范 op、显示元数据/错误和通过 `showDocument()` 安装控制器交出的文档。渲染、碰撞求解和后端落盘各自保留原职责。确定性协议与同步状态由代码执行，不新增 LLM 判断或边界例外。检查直接导入控制器，覆盖延迟/乱序响应、连续保存、外部通知、拒绝恢复、网络失败、决策更新和独立单间：`node domain/modules/web/furniture_web/static/layout_persistence_check.mjs`。

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
