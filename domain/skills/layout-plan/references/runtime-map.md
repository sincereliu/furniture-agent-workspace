# 运行时映射（布局阶段）

核对实现或规划演进时再读。几何口径以[空间布局规则](spatial-layout-rules.md)为准；预览服务的操作见[预览维护](preview-ops.md)。最后一列「代码归类」供边界审计使用。

## 全屋摆放和单间

两条路用同一套换算和摆放检查，都要求显式房间尺寸。项目入口只接受非空的 `rooms[]`；家具位于所属房间的 `items[]`。

| 干什么 | 从哪进 | 过不了会怎样 | 存在哪 |
| --- | --- | --- | --- |
| 建一整套房子的摆放 | `layout_entry.plan_project_layout` / `ProjectLayout.from_source` | 越界、干涉或遮挡洞口就不建项目 | Project Store；确认后冻成给板件的盒子 |
| 建单独一间 | `layout_entry.plan_room_scene` | 同一套 `validation.admit_scene` | `scene_store` → `generated/room-scenes/`；这间不进六阶段 |

下游板件只读已确认的 `LayoutUnit`（`furniture_category` 为 `floor_cabinet` / `wall_cabinet`，且该件不是 `manufacture: false`）。客户点名不制造的包络留在房间里，不是 `LayoutUnit`。`room_shell.py` 写的房间外壳 STEP 不是柜体模型。

**沿墙铺满**（`placement.fill` + `kind`）：这段空墙由 `space_split.unit_widths` 按[工艺目录](craft-catalog.yaml)里该柜类的门宽上限拆成一台或几台，沿墙接开，宽度加起来等于这段空墙。没有铺满的输入不读目录。口径见[沿墙铺满](space-split-design.md)。

板件实际只依赖 `LayoutUnit` 的五个字段：`id`、`furniture_category`、`width`、`depth`、`height`。这五个不变，板件与制造的内容就不变，可以跨 Revision 继承（见编排层 [修订继承设计](../../cad-generated/references/revision-inheritance-design.md)）。沿墙铺满那件的 `width` 由该墙空段算出，改房间就会改它，所以这种件永远算变了，必须重算。

确认时 `layout_figures.check_layout_figures` / `check_room_figures` 再核每个房间的图是不是由当前几何画出的。建项目前的 `validation.admit_scene` 不画 SVG。

## 各文件干什么

| 干什么 | 文件 | 代码归类 |
| --- | --- | --- |
| 房间、门窗、家具盒子的数据结构 | `scene.py` | schema |
| 只读取规范字段；拒绝未知字段、非法布尔值和非有限数值 | `input_fields.py` | schema / validation |
| 车间工艺目录（`craft-catalog.yaml`）的加载与准入：区间、档位、策略；**缺项停问** | `craft_catalog.py` | schema / validation |
| 一段墙长拆成若干台的宽度：每台不超过两扇门上限，加起来等于这段墙 | `space_split.py` | calculation |
| 全屋、单间和编辑共用的规划入口：解析 → 摆放 → 沿墙铺满拆成几台 → 几何准入 | `scene_planning.py` | calculation / validation |
| 把靠墙、自由摆、沿墙铺满换成毫米坐标 | `placement.py` | calculation |
| 检查盒子出不出房间、互相干涉不干涉、挡不挡门窗 | `placement_check.py` | calculation |
| 上面几项有一项不过，就不建项目。不核对配进去的那张 SVG | `validation.py` | validation |
| 一整套房子的摆放。确认后冻出给板件的盒子：宽、深、高和柜类。这里不画房间页，也不写房间外壳 | `project_layout.py` | schema |
| 给这套摆放配上每个房间的图，确认时核对图是不是刚算出来的 | `layout_figures.py` | calculation |
| 配进去的那张 SVG | `room_svg.py` | calculation |
| 保存的只读预览、单间草稿、项目预览和分享共用一个模板。Python 读 `templates/room_page.html` 填上当前房间。原点三轴、光标坐标、房间药丸、`?room=`、页眉牌子都在模板里。`templates/room_page.js` 里的拖动检查必须与 `placement_check.py` 同步 | `room_page.py` | calculation |
| 做过的项目名单 | `project_list.py` | calculation |
| 把预览页打开，并准备这一页要读的数据 | `open_preview.py` | side_effect |
| 房间页上的三维盒子 | `static/layout_scene.js` | calculation |
| 页面入口将规范布局输出一次转换为画布模型；渲染层只读取该模型 | `static/layout_payload.js` | calculation |
| 房间的东、南、上怎么画到屏幕上 | `static/layout_frame.js` | calculation |
| 房间轴、家具尺寸线和标签锚点；全部用房间坐标计算 | `static/layout_annotations.js` | calculation |
| 屏幕标注矩形避让、画布边界与稳定偏移 | `static/layout_labels.js` | calculation |
| 拖动换算（屏幕像素 → 房间毫米）与"贴回墙面" | `static/layout_drag.js` | calculation |
| 记下移动、旋转或改尺寸，这一步先不算。全屋和单间共用这一套字段 | `scene_edit.py` | schema |
| 把这次改动算进某一间，算出一版还没确认的摆放。版本号和落盘不在这里 | `project_edit.py` | calculation |
| 三个入口：建全屋摆放（`plan_project_layout`）、建单间（`plan_room_scene`）、写房间外壳（`write_room_shell`） | `layout_entry.py` | structured_protocol |
| 单间的保存、编辑，以及要房间外壳 | `room_http.py` | structured_protocol |
| 单间只存客户原来写的那份，打开时再算 | `scene_store.py` | side_effect |
| 房间外壳的 STEP：地、墙、门窗洞。不是柜体模型 | `room_shell.py` | side_effect |

页面结构在 `templates/room_page.html`，交互脚本在 `templates/room_page.js`。`room_page.py` 读入两份模板后填充参数，保存预览与实时页面使用同一份组装结果；模板不作为静态资源直接发布。

房间页上拖动只是本地先画，松手后后端再换算并检查。改 `placement_check.py` 必须同步改 `templates/room_page.js` 里的脚本。

数据链路为 `规范请求 → scene_planning.plan_scene → RoomScene → layout_figures / room_page`。项目读取只接受带明确 `schema_version` 的当前检查点；房间源与已摆放输出是两份明确契约。编辑通过 `PlacedItem.to_source()` 去掉派生字段，重算后才交给项目编排层保存。没有历史字段别名、自动推断摆放模式、扁平房间输出或旧预览页面分支。

预览几何与标签锚点统一使用房间坐标 `[x, y, z]`（宽、深、高，毫米）。进入 Three.js 时调用 `layout_frame.roomToThree()`，相机回读与拾取返回时调用 `threeToRoom()`；不在调用方手写换序。屏幕像素坐标与 Three.js 原生网格旋转仍由渲染层计算。固定轴和边线随场景内容构建，相机移动时只更新投影与墙面显示。

[房间坐标行为测试](../../cad-generated/scripts/tests/test_room_coordinate_contract.py) 固定局部原点、足迹点序、正负转角、四面靠墙的正面方向、离地高度以及对称包络的序列化。通过 `run_tests.py -p test_room_coordinate_contract.py` 单独选择。前端的 [frame_check.mjs](../scripts/furniture_layout/static/frame_check.mjs) 检查三轴映射和标注；立方体占用空间相同但点序不同，也必须保留各自局部宽深方向。在仓库根目录运行 `node domain/skills/layout-plan/scripts/furniture_layout/static/frame_check.mjs`。

未落地与待议需求见 [backlog](backlog.md)。改坐标、摆放检查或房间页时不必读。
