# 运行时映射（布局阶段）

核对实现或规划演进时再读。几何口径以[空间布局规则](spatial-layout-rules.md)为准；预览服务的操作见[预览维护](preview-ops.md)。最后一列「代码归类」供边界审计使用。

## 全屋摆放和单间

两条路用同一套换算和摆放检查，都要求显式房间尺寸。项目入口只接受非空的 `rooms[]`；家具位于所属房间的 `items[]`。

| 干什么 | 从哪进 | 过不了会怎样 | 存在哪 |
| --- | --- | --- | --- |
| 建一整套房子的摆放 | `layout_entry.plan_project_layout` / `ProjectLayout.from_source` | 越界、干涉或遮挡洞口就不建项目 | Project Store；确认后冻成给板件的盒子 |
| 建单独一间 | `layout_entry.plan_room_scene` | 同一套 `validation.admit_scene` | `scene_store` → `generated/room-scenes/`；这间不进六阶段 |

下游板件只读已确认的 `LayoutUnit`（`furniture_category` 为 `floor_cabinet` / `wall_cabinet`，且该件不是 `manufacture: false`）。客户点名不制造的包络留在房间里，不是 `LayoutUnit`。`room_shell.py` 写的房间外壳 STEP 不是柜体模型。

**靠墙包络**：写了 `placement.against` 的固定柜子先占声明的那一头（`{kind: wall}` 贴到侧面的墙，`{kind: item, id: ...}` 贴着指定家具）。输入与输出只使用显式对象，内部使用 `AgainstTarget`。其余固定宽度的按顺序贴上最早放得下的空段。`placement.fill` 没写 `against` 时占最长空段，写了就占贴着那一头的空段；id 不变，不按门宽拆开。请求不写沿墙位置。`to_source()` 不把这次算出的起点写进下一次请求，但留下 `against`。口径见[空间布局规则](spatial-layout-rules.md)。

板件实际只依赖 `LayoutUnit` 的五个字段：`id`、`furniture_category`、`width`、`depth`、`height`。这五个不变，板件与制造的内容就不变，可以跨 Revision 继承（见编排层 [修订继承设计](../../cad-generated/references/revision-inheritance-design.md)）。沿墙铺满那件的 `width` 由该墙空段算出，改房间就会改它，所以这种件永远算变了，必须重算。

确认时 `layout_figures.check_layout_figures` / `check_room_figures` 再核每个房间的图是不是由当前几何画出的。建项目前的 `validation.admit_scene` 不画 SVG。

## 各文件干什么

| 干什么 | 文件 | 代码归类 |
| --- | --- | --- |
| 房间、门窗、家具盒子的数据结构 | `scene.py` | schema |
| 只读取规范字段；拒绝未知字段、非法布尔值和非有限数值 | `input_fields.py` | schema / validation |
| 全屋、单间和编辑共用的规划入口：解析 → 摆放 → 几何准入 | `scene_planning.py` | calculation / validation |
| 把靠墙、自由摆、沿墙铺满换成毫米坐标 | `placement.py` | calculation |
| 检查盒子出不出房间、互相干涉不干涉、挡不挡门窗 | `placement_check.py` | calculation |
| 上面几项有一项不过，就不建项目。不核对配进去的那张 SVG | `validation.py` | validation |
| 一整套房子的摆放。确认后冻出给板件的盒子：宽、深、高和柜类。这里不画房间页，也不写房间外壳 | `project_layout.py` | schema |
| 给这套摆放配上每个房间的图，确认时核对图是不是刚算出来的 | `layout_figures.py` | calculation |
| 配进去的那张 SVG | `room_svg.py` | calculation |
| 保存的只读预览、单间草稿、项目预览和分享共用一个模板。Python 读 `templates/room_page.html` 填上当前房间。原点三轴、光标坐标、房间药丸、`?room=`、页眉牌子都在模板里。前端拖动检查在 `static/layout_solver.js`，必须与 `placement_check.py` 同步 | `room_page.py` | calculation |
| 做过的项目名单 | `project_list.py` | calculation |
| 把预览页打开，并准备这一页要读的数据 | `open_preview.py` | side_effect |
| 布局页订阅项目文件和编辑租约。变了才通知，版本变了才重读整份布局 | `layout_events.py` | structured_protocol / side_effect |
| 从最新布局取出一台已保存外形，供板件页使用。不要求整份布局已确认 | `cabinet_entry.py` | validation |
| 房间页三维视口组装、相机控制、射线拾取与句柄同步 | `static/layout_scene.js` | calculation |
| 日间工作室天空球、建筑微缩底座、卡通光照材质与缓存化地砖/台面贴图 | `static/layout_diorama.js` | calculation |
| 文字标签 DOM 层、SVG 引线与左下角坐标轴角标 | `static/layout_overlay.js` | calculation |
| 围墙/地板台子、家具棱柱、沙发/茶几网格、旋转环与尺寸标注线 | `static/layout_meshes.js` | calculation |
| 前端碰撞、越界、门窗遮挡、四向净距与整数毫米二分拖拽求解（对应 `placement_check.py`） | `static/layout_solver.js` | calculation |
| 正视图预设、基准取景距离、立面竖直平面比例与旋转方向符号 | `static/layout_camera.js` | calculation |
| 预览围墙的厚度、转角和门窗洞，房间坐标 | `static/wall_solid.js` | calculation |
| 不进生产的沙发在预览里的靠背、扶手和坐垫。要做成柜的沙发仍是盒子 | `static/sofa_solid.js` | calculation |
| 不进生产的茶几在预览里的桌面、腿和层板。要做成柜的茶几仍是盒子 | `static/coffee_table_solid.js` | calculation |
| 预览边线沿视线拉近 1 毫米，贴墙时仍画在墙前面 | `static/ink_depth.js` | calculation |
| 页面入口将规范布局输出一次转换为画布模型；渲染层只读取该模型 | `static/layout_payload.js` | calculation |
| 房间的东、南、上怎么画到屏幕上 | `static/layout_frame.js` | calculation |
| 房间轴、家具尺寸线和标签锚点；全部用房间坐标计算 | `static/layout_annotations.js` | calculation |
| 屏幕标注矩形避让、画布边界与稳定偏移 | `static/layout_labels.js` | calculation |
| 拖动换算（屏幕像素 → 房间毫米）与"贴回墙面" | `static/layout_drag.js` | calculation |
| 布局页离线免构建 Angular Standalone 组件与响应式 Signals 运行时 | `static/layout_angular.js` | structured_protocol / side_effect |
| 可选页面扩展的样式、按钮、侧栏、弹窗和启动代码插槽；不内置 AI 内容 | `room_page.PageExtension` / `templates/` | structured_protocol |
| 记下移动、旋转或改尺寸，这一步先不算。全屋和单间共用这一套字段 | `scene_edit.py` | schema |
| 把这次改动算进某一间，算出一版还没确认的摆放。版本号和落盘不在这里 | `project_edit.py` | calculation |
| 三个入口：建全屋摆放（`plan_project_layout`）、建单间（`plan_room_scene`）、写房间外壳（`write_room_shell`） | `layout_entry.py` | structured_protocol |
| 单间的保存、编辑，以及要房间外壳 | `room_http.py` | structured_protocol |
| 单间只存客户原来写的那份，打开时再算 | `scene_store.py` | side_effect |
| 房间外壳的 STEP：地、墙、门窗洞。不是柜体模型 | `room_shell.py` | side_effect |

页面结构在 `templates/room_page.html`，交互胶水在 `templates/room_page.js`，碰撞与拖拽求解在 `static/layout_solver.js`，相机取景辅助在 `static/layout_camera.js`。`room_page.py` 读入两份模板后填充参数，保存预览与实时页面使用同一份组装结果；模板不作为静态资源直接发布。

页面 AI 助手是独立可选功能，界面与脚本归 `cad-generated/scripts/furniture_chat/`，模型连接归 `furniture_ai/`。
布局页不导入这些包，不默认生成扩展。宿主仅为本机可编辑项目页传入 `PageExtension`；只读与分享页会丢弃扩展。
扩展可通过两个只面向展示的回调刷新项目或显示状态，不直接读写布局对象。关闭方法和维护入口见 [AI 接入层维护](../../cad-generated/references/ai-integration.md)。

房间页上拖动只是本地先画，松手后后端再换算并检查。改 `placement_check.py` 必须同步改 `static/layout_solver.js`。

数据链路为 `规范请求 → scene_planning.plan_scene → RoomScene → layout_figures / room_page`。项目读取只接受带明确 `schema_version` 的当前检查点；房间源与已摆放输出是两份明确契约。编辑通过 `PlacedItem.to_source()` 去掉派生字段，重算后才交给项目编排层保存。没有历史字段别名、自动推断摆放模式、扁平房间输出或旧预览页面分支。

预览几何与标签锚点统一使用房间坐标 `[x, y, z]`（宽、深、高，毫米）。进入 Three.js 时调用 `layout_frame.roomToThree()`，相机回读与拾取返回时调用 `threeToRoom()`；不在调用方手写换序。屏幕像素坐标与 Three.js 原生网格旋转仍由渲染层计算。固定轴和边线随场景内容构建，相机移动时只更新投影与墙面显示。

## 维护时跑哪几个测试

改了布局的哪一块，就只跑下面碰到的那几行。一次改动跨了几行，就跑这几行。不带 `-p` 的 `run_tests.py` 只用于专门的整库回归。

Python 在仓库根目录：

```powershell
.\.venv\Scripts\python.exe domain\skills\cad-generated\scripts\run_tests.py -p <测试文件名>
```

前端检查同样在仓库根目录，把 `<检查脚本>` 换成表里的文件名：

```powershell
node domain/skills/layout-plan/scripts/furniture_layout/static/<检查脚本>
```

| 改了 | 跑 |
| --- | --- |
| `placement.py`、`placement_check.py`：干涉、贴边、门窗遮挡 | `test_room_scene_placement.py` |
| 局部原点、足迹点序、正负转角、四面靠墙正面、离地高度、对称包络序列化 | `test_room_coordinate_contract.py` |
| `static/layout_frame.js`、`static/layout_annotations.js`、`static/layout_payload.js`：三轴映射和标注。占用空间相同但点序不同的立方体，各自保留局部宽深方向 | `frame_check.mjs` |
| `input_fields.py`，以及 `fill`、`against`、HTTP 准入 | `test_layout_input_contract.py` |
| `validation.py`、`layout_figures.py`、`room_svg.py`、`room_shell.py`：建项前准入、铺满宽度、`manufacture`、房间外壳和 SVG | `test_room_layout_preview.py` |
| `scene_edit.py`：移动、旋转、改尺寸 | `test_room_scene_edit.py` |
| `project_edit.py`：项目内改布局、撤销、新修订 | `test_project_layout_edit.py` |
| `room_http.py`：单间保存、读取、房间外壳接口 | `test_room_scene_api.py` |
| `scene_store.py` | `test_room_scene_store.py` |
| 单间草稿页 | `test_room_scene_editor.py` |
| `open_preview.py`、`layout_events.py`、`project_list.py`、项目预览、名单、分享、拖动回写 | `test_project_preview.py` |
| 按房间确认 | `test_room_level_confirmation.py` |
| `static/layout_solver.js` | `solver_check.mjs` |
| `static/layout_drag.js` | `drag_check.mjs` |
| `static/layout_labels.js` | `labels_check.mjs` |
| `static/wall_view.js` | `wall_view_check.mjs` |
| `static/wall_solid.js` | `wall_solid_check.mjs` |
| `static/sofa_solid.js` | `sofa_solid_check.mjs` |
| `static/coffee_table_solid.js` | `coffee_table_check.mjs` |
| `static/ink_depth.js`、`static/layout_scene.js` 的边线深度 | `ink_depth_check.mjs` |
| `cabinet_entry.py` | `test_cabinet_panel_page.py` |
| `static/layout_scene.js`、`static/layout_diorama.js`、`static/layout_overlay.js`、`static/layout_meshes.js` | `test_project_preview.py` |

`scene.py`、`scene_planning.py`、`layout_entry.py`、`project_layout.py`、`room_page.py` 和 `templates/` 被上面多行用到。改它们时，跑它实际喂到的那些行。`scene.py` 的家具 id 规则还有板件阶段的对照，再加 `test_skill_architecture.py`。`static/layout_solver.js` 里的拖动检查要和 `placement_check.py` 一起改，这时 `solver_check.mjs`、摆放检查和项目预览三行都跑。

这些测试会引用布局类型，测的是别的面：`test_agent_tools.py`（工具面）、`test_decision_log.py`（决策记录）、`test_edit_lease.py`（编辑租约）、`test_revision_inheritance.py`（修订继承）、`test_entrypoint_architecture.py`（入口装配）。改摆放几何时不把它们算进这一次。

未落地需求在 `backlog/layout-plan.md`，不在本技能里。改坐标、摆放检查或房间页时不必读。
