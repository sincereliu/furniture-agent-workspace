# 网页展示边界

本模块位于 `domain/modules/web/`。下面说的是浏览器里看见的那几页。

三维画面的风格、描边层次及验收参考见 [三维预览视觉规范](visual-style.md)。修改或重构渲染代码时一并遵守。

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

画面脚本先从这个目录取。`layout_solver.js`、`layout_drag.js` 和 `layout_interaction.js` 不在这里，挂载时再去布局阶段找，所以页面里的地址不用改。

卡通描边由 `layout_scene.js` 调用 `cartoon_outline.js`。`layout_ink.js` 提供两个明确入口：`addFurnitureInk(mesh, {itemId, color})` 注册整件身份/颜色并创建内部细线，家具不再接收无效的毫米厚度参数；`addStageInk(mesh, color, thickness)` 绘制墙体、地台等场景边线，厚度只用于实体膨胀壳。`outline_style.js` 集中保存家具投影线宽、方向轻重、内部线透明度、棱边角度和交互颜色，`layout_meshes.js` 的家具构建器调用家具入口，场景构建器调用场景入口。

`cartoon_outline.js` 拥有颜色/身份蒙版、遮挡计算及渲染状态恢复；按原网格复用蒙版代理，移除家具时清理代理和专有材质，借用的几何仍由原场景释放。视觉细则、参数、参考图和检查入口统一维护在 [三维预览视觉规范](visual-style.md)，本文件只记录模块职责。

房间内生产家具的棱柱和现成家具的部件都进入同一套整体蒙版，内部只画轻棱边。`cartoon_outline.js` 根据整件家具的投影尺寸、镜头和画布计算线宽，再按屏幕轮廓朝向平滑调节轻重；这些确定性显示计算不依据 `manufacture` 分配描边样式。

`wall_contact.js` 从实际墙块与家具棱边、软包包边及软包三角曲面计算接触，预先裁掉细线，并给颜色蒙版提供贴墙裁边数据；它负责可见性，不另设线宽或风格。细线与贴墙模块共用 `furniture_edges.js`，沙发曲面和包边由 `sofa_upholstery.js` 在部件尺寸边界内生成。每帧顺序为 `prepare(roots, camera)` → 主场景渲染 → `draw(roots, camera)`：准备只执行一次，`draw()` 消费本帧接触数据，漏掉准备或重复消费会明确报错，避免沿用上一帧状态。这些计算只影响预览，不更改摆放、足迹或制造数据。

房间墙体淡出时，`opening_markers.js` 保留对应门窗的无填充虚线框：门有地面底边，窗保留窗台高度。轮廓按深度参与遮挡且不写深度、不投影；悬停显示门窗 ID、宽高和窗台高度。`layout_scene.js` 随墙体透明度切换实体与轮廓，提示由 `layout_overlay.js` 显示。几何、淡出和悬停遮挡检查运行 `node domain/modules/web/furniture_web/static/opening_markers_check.mjs`。

`layout_persistence.js` 是浏览器布局文档的同步入口，私有状态不由页面模板直接修改。它按松手顺序串行保存，提交时复制操作坐标、发送时带上上一笔确认的版本和当前租约；助手假设的确认/划掉也走这条队列。拖动、转动视角或保存期间暂存文档，空闲后才交给页面安装；写入和较新的读取使旧响应失效。通知到来时只按需重读；写入拒绝或网络异常后重读权威结果，再释放队列。保存中切换房间会被页面挡住，防止用旧房间快照覆盖本地操作。同墙拖动比较完整位置，不能只凭墙名和高度跳过保存。

`layout_interaction.js` 属于布局阶段，拥有一次手势的开始、更新、结束和取消。事务复制操作前位置并维护私有候选；页面只提供指针、相机比例及墙面投影方向。画布和属性栏读取候选，松手后提交其完整变换；Escape、pointercancel、丢失捕获或画布尺寸变化丢弃候选。贴墙时同时更新屏幕起点和房间原点，保持后续离墙连续。加载文档只转换数据形状，不改摆放模式。

移动、旋转和高度交互都使用布局模块的 `poseOperation()`，以 `set_pose` 携带明确模式、完整三轴原点和朝向；靠墙时另带墙名。后端验证已摆放几何，不将手工位置重新解释为沿墙规划。普通数值微调使用相同编码。外形尺寸保存确认前不开始新的位置手势，避免用旧尺寸求解而服务端按新尺寸准入。编辑被拒或网络失败时安装权威重读结果；重读也失败时，仅回退仍属于该操作的候选，避免覆盖后续编辑。

模板只负责把交互整理成规范 op、显示元数据/错误和通过 `showDocument()` 安装控制器交出的文档。渲染、碰撞求解和后端落盘各自保留原职责。确定性协议与同步状态由代码执行，不新增 LLM 判断或边界例外。检查直接导入控制器，覆盖延迟/乱序响应、连续保存、外部通知、拒绝恢复、网络失败、决策更新和独立单间：`node domain/modules/web/furniture_web/static/layout_persistence_check.mjs`。

## 留在原处

| 干什么 | 留在 |
| --- | --- |
| 房间页要画的字典 | `furniture_layout.room_page.room_page_payload` |
| 干涉、越界、挡门窗、against 接触与 fill 空段的前端求解 | `furniture_layout/static/layout_solver.js`，与 `placement_check.py`、`placement.py` 一起改 |
| 屏幕到毫米的拖动，以及贴回墙面 | `furniture_layout/static/layout_drag.js` |
| 拖动事务、私有候选和完整位置操作编码 | `furniture_layout/static/layout_interaction.js` |
| 确认时核对的房间 SVG | `furniture_layout/room_svg.py`，`layout_figures.py` |
| 板件页要画的结构、顺纹和贴图摆法 | `furniture_panel_planning.cabinet_panel_page.panel_structure_view` |
| 保存、撤销、编辑租约、进程退出 | `cad-generated/scripts/server.py` 和工作流 |

确认时，布局阶段调用本模块的 `render_viewer`，核对只读页是不是当前几何画出的。单间草稿的 HTML 也由 `room_http` 调用 `render_draft_page`。这两处是布局阶段对网页模块的依赖。网页模块不导入工作流，不写项目。

改摆放规则时改布局阶段的求解脚本。改门窗颜色、相机、微缩场景或板件页样子时改本模块。

## 拖动闭环检查

`node domain/stages/layout-plan/scripts/furniture_layout/static/interaction_check.mjs` 检查四面墙的离墙、横移、贴回和再次离墙、活动家具、取消及完整变换编码。

`test_drag_transaction_roundtrip.py` 执行实际 JS 手势，并将输出交给真实项目和独立房间编辑入口，检查准入、保存、重读及撤销。运行：`.venv/Scripts/python.exe -m unittest discover -s domain/stages/cad-generated/scripts/tests -p test_drag_transaction_roundtrip.py`。

真实页面检查在沙箱外执行：`.venv/Scripts/python.exe domain/modules/web/scripts/check_drag.py --output temp/drag-checks/transaction.png`。脚本使用临时目录和临时本机服务，运行真实 Chromium 指针事件及 HTTP 编辑，核对预览、保存和重开后的原点、朝向、足迹与净距；另查 Escape、pointercancel、网络失败恢复、迟到响应不会覆盖下一次拖动，以及外形保存期间不会用旧尺寸开始拖动。against/fill 约束分别核对无效离墙和旋转不发送编辑、高度停在可保存边界并可重开，以及不同高度带的 fill 不误锁移动。完成后清理测试服务，不读写用户项目。
