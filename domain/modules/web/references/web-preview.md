# 页面与模块边界

路径相对 `domain/modules/web/`。本文件维护职责与接口；效果要求在 [视觉规范](visual-style.md)，命令与覆盖在 [检查方法](testing.md)，未完成问题在 [统一待办](../../../../backlog/web.md)。

## 页面与控制器

| 入口 | 拥有的职责 |
| --- | --- |
| `furniture_web/room_page.py`、`templates/room_page.html` | 草稿、项目、只读与分享页的 HTML、服务端权限和规范配置 |
| `templates/room_page.js` | 读取配置与场景，调用页面入口，安装可信扩展 |
| `static/pages/room/index.js` | 组装控制器、唯一画布同步入口、候选提交和写入结果提示 |
| `pages/room/camera.js` | 视角预设、过渡、缩放、投影、标注开关和画布尺寸变化 |
| `pages/room/gestures.js` | 指针/键盘桥接，持有布局阶段创建的私有拖动事务；取消则丢弃候选 |
| `pages/room/details.js` | 家具列表、属性面板、数值微调与板件入口；调用阶段求解器 |
| `pages/room/navigation.js` | 房间集合、切换、深链与文档安装；切换前检查同步控制器是否忙碌 |
| `pages/room/layout_persistence.js` | 版本、串行请求队列、迟到响应失效、通知重读与失败恢复 |
| `pages/room/lease.js` | 租约凭据、申请/收回/闲置让出、事件连接和页面关闭恢复 |
| `pages/room/activity.js` | 工作副本记录、助手假设面板；确认/划掉走相同写入队列 |
| `pages/room/layout_payload.js`、`item_hints.js`、`markup.js` | 规范数据到画布模型的转换、页面提示与 HTML 转义 |
| `shared/reactivity.js` | 轻量响应式信号与组件引导 |
| `furniture_web/panel_page.py`、`static/pages/panels/index.js` | 冻结板件页组装、选择、展示开关与页面事件 |
| `pages/panels/sidebar.js`、`labels.js` | 板件列表、详情、汇总与字段标签 |
| `pages/panels/editor.js` | 暂存顺纹/铰链修改、预览投影与一次保存；不自行规划板件 |
| `furniture_web/home_page.py`、`project_list.py`、对应模板 | 工作台首页与项目列表 |

表中 `pages/` 和下表的 `render/` 均位于 `furniture_web/static/`。

页面配置只在初始化时传入，动态文档经同步控制器交给导航安装。拖动事务、租约与板件修改各由相应控制器持有，通过方法和回调协作，不由外部直接改写模块内变量。

同步控制器按松手顺序写入，操作入队时复制坐标，发送时使用上一笔确认的版本和当前租约。交互/保存期间暂存文档，较新写入/读取使旧响应失效。失败后重读权威结果；重读失败时只回退仍属于该次操作的候选。外形保存期间禁止用旧尺寸开始位置手势。

可编辑项目页先申请租约，再以取得的锁号订阅事件。并发申请合为一次；关闭后停止重抢，从浏览器缓存返回时恢复连接。服务端仍拥有写权限、租约准入和落盘。

可信 `PageExtension` 通过 `pageHost.onProjectUpdated()` 和 `pageHost.onStatusToast()` 接入，不读写页面内部状态。模块不内置 AI 助手。

## 三维渲染

| 模块 | 拥有的职责 |
| --- | --- |
| `render/room/layout_scene.js` | 视口组装、场景同步、墙体淡出、点选与生命周期 |
| `render/room/layout_frame.js`、`layout_camera.js` | 房间/Three.js 坐标与确定性相机计算 |
| `render/room/layout_meshes.js` | 舞台/家具网格组装与 GPU 资源释放 |
| `render/room/layout_annotations.js`、`layout_labels.js`、`layout_overlay.js` | 锚点、标签投影、提示与素材署名 |
| `render/room/wall_*.js`、`opening_*.js` | 真实墙块/洞口、墙面显示、门窗实体及淡出后的轮廓 |
| `render/room/room_lighting.js` | 室内光、隐藏房顶、视角独立遮光壳与投影深度材质 |
| `render/furniture/` | 桌椅、茶几与沙发的预览几何；尺寸边界与曲面分开，共用真实边缘 |
| `render/outline/outline_style.js` | 共享线宽、方向轻重、内部线透明度、棱边角度与交互颜色 |
| `render/outline/layout_ink.js`、`ink_depth.js` | 家具细线/场景边线入口，贴面线条的深度偏移 |
| `render/outline/cartoon_outline.js` | 颜色/身份蒙版、投影线宽、遮挡合成和渲染状态恢复 |
| `render/outline/wall_contact.js` | 真实墙块/有限地板求交、细线裁切和颜色蒙版裁边 |
| `render/environment/` | 卡通材质、共享天空纹理、庭院与树带；不参与家具蒙版或交互 |
| `render/panels/scene.js`、`camera.js`、`materials.js` | 冻结板件网格、开门/拆解、拾取、取景与程序木纹 |

每帧描边为 `prepare(roots, camera)` → 主场景渲染 → `draw(roots, camera)`，准备数据只消费一次。家具身份按整件共享，颜色蒙版可以裁接触，身份蒙版不裁空。代理借用原几何，专有材质与代理由描边模块清理，原几何由场景清理。

`addFurnitureInk(mesh, {itemId, color})` 注册身份并创建细线；`addStageInk(mesh, color, thickness)` 仅处理墙体/地台边线。接触按真实部件边缘、包边、三角面和 0.5 mm 公差判断，不能按足迹或摆放模式关闭整面描边。

照明遮光壳独立于可见墙淡出；主画面使用对数深度，透视阴影用专有 `MeshDepthMaterial` 写投影深度。房间/洞口重建时释放照明与遮光资源，家具同步后更新阴影，换视角复用阴影贴图。

天空从同源 `images/milky-way-eso0932a.jpg` 加载并用 `createImageBitmap` 解码，完成后重绘，不作为室内环境光。室外组随房间重建释放纹理、几何、材质与实例缓冲。素材许可和校验值维护在 [素材说明](../furniture_web/static/images/README.md)。

## 服务与阶段边界

`integration.py` 将正式静态目录挂在 `/layout-view/`，并从布局阶段提供 `layout_solver.js`、`layout_drag.js`、`layout_interaction.js`。检查页只由临时测试服务的 `/web-checks/` 提供。

| 数据或规则 | 所有者 |
| --- | --- |
| 场景字典、确认用 SVG | 布局阶段 `room_page_payload`、`room_svg.py`、`layout_figures.py` |
| 摆放、碰撞、净距、against/fill | 布局阶段 `placement_check.py`、`placement.py`、`layout_solver.js` |
| 屏幕到毫米、贴回墙面 | 布局阶段 `layout_drag.js` |
| 拖动事务、候选、完整 `set_pose` 编码 | 布局阶段 `layout_interaction.js` |
| 冻结板件、顺纹轴、六面 UV、铰链准入 | 板件阶段 `cabinet_panel_page.py` 与板件规划 |
| 保存、撤销、租约、进程退出 | CAD 编排服务与工作流 |

Web 运行时保留确定性展示计算、状态、结构化协议和资源副作用；家具规划、制造默认值与自然语言判断仍由相应阶段或 LLM 负责。
